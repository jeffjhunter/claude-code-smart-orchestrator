#!/usr/bin/env python3
"""Verify a direct-model Claude Code preflight from a stream-json trace."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_runtime_trace import (  # Reuse the hardened trace/model primitives.
    _model_family,
    _model_matches,
    load_events,
)


def _walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    """Yield every object in a parsed event without interpreting text as JSON."""

    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _tool_activity_blocks(
    events: list[dict[str, Any]],
) -> list[tuple[int, dict[str, Any]]]:
    blocks: list[tuple[int, dict[str, Any]]] = []
    for event_index, event in enumerate(events):
        for value in _walk_dicts(event):
            block_type = value.get("type")
            if isinstance(block_type, str) and (
                block_type in {"tool_use", "tool_result"}
                or block_type.endswith("_tool_use")
                or block_type.endswith("_tool_result")
            ):
                blocks.append((event_index, value))
    return blocks


def _is_subagent_scoped(event: dict[str, Any]) -> bool:
    if event.get("parent_tool_use_id") not in (None, ""):
        return True
    if event.get("subagent_type") not in (None, ""):
        return True
    origin = event.get("origin")
    return (
        isinstance(origin, dict)
        and origin.get("kind") == "task-notification"
    )


def verify_events(
    events: list[dict[str, Any]], expected_model: str, expected_result: str
) -> tuple[list[str], str | None]:
    """Validate direct execution evidence and return errors plus observed model."""

    errors: list[str] = []
    if not isinstance(expected_result, str) or not expected_result.strip():
        errors.append("expected result must be a non-empty string")

    session_ids: list[str] = []
    for event_index, event in enumerate(events):
        session_id = event.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            errors.append(f"event {event_index + 1} has no non-empty session_id")
        else:
            session_ids.append(session_id)
    unique_sessions = sorted(set(session_ids))
    if len(unique_sessions) != 1:
        errors.append(
            f"expected exactly one session_id, found {len(unique_sessions)}"
        )

    tool_activity = _tool_activity_blocks(events)
    tool_blocks = [
        (event_index, block)
        for event_index, block in tool_activity
        if str(block.get("type")).endswith("tool_use")
    ]
    tool_result_blocks = [
        (event_index, block)
        for event_index, block in tool_activity
        if str(block.get("type")).endswith("tool_result")
    ]
    agent_blocks = [
        (event_index, block)
        for event_index, block in tool_blocks
        if block.get("name") == "Agent"
    ]
    if agent_blocks:
        errors.append(
            f"direct preflight contains Agent tool calls: found {len(agent_blocks)}"
        )
    if tool_blocks:
        errors.append(
            "direct preflight must contain no tool_use blocks, "
            f"found {len(tool_blocks)}"
        )
    if tool_result_blocks:
        errors.append(
            "direct preflight must contain no tool_result blocks, "
            f"found {len(tool_result_blocks)}"
        )

    task_events = [
        (event_index, event)
        for event_index, event in enumerate(events)
        if isinstance(event.get("subtype"), str)
        and event["subtype"].startswith("task_")
    ]
    if task_events:
        errors.append(
            "direct preflight must contain no task_* lifecycle events, "
            f"found {len(task_events)}"
        )

    scoped_events = [
        event_index
        for event_index, event in enumerate(events)
        if _is_subagent_scoped(event)
    ]
    if scoped_events:
        rendered = ", ".join(str(index + 1) for index in scoped_events)
        errors.append(
            "direct preflight contains subagent-scoped events at event(s) "
            + rendered
        )

    model_evidence: list[tuple[int, str]] = []
    assistant_texts: list[str] = []
    assistant_event_count = 0
    for event_index, event in enumerate(events):
        if event.get("type") != "assistant":
            continue
        assistant_event_count += 1
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            errors.append(
                f"event {event_index + 1} is not a well-formed assistant message"
            )
            continue
        model = message.get("model")
        if not isinstance(model, str) or not model.strip():
            errors.append(
                f"event {event_index + 1} has no non-empty assistant message.model"
            )
            continue
        model_evidence.append((event_index, model.strip()))
        content = message.get("content")
        if not isinstance(content, list):
            errors.append(
                f"event {event_index + 1} assistant content is not a list"
            )
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    assistant_texts.append(text)

    if len(assistant_texts) != 1:
        errors.append(
            "expected exactly one direct assistant text block, "
            f"found {len(assistant_texts)}"
        )
    elif assistant_texts[0] != expected_result:
        errors.append(
            "direct assistant text does not exactly match the expected result"
        )

    if assistant_event_count == 0:
        errors.append("trace contains no assistant events")

    unique_models = sorted(
        {model for _, model in model_evidence}, key=str.casefold
    )
    if not model_evidence:
        errors.append("trace contains no assistant message.model evidence")
        observed_model = None
        model_event_index = None
    elif len(unique_models) != 1:
        errors.append(
            "ambiguous assistant model evidence: " + ", ".join(unique_models)
        )
        observed_model = None
        model_event_index = None
    else:
        observed_model = unique_models[0]
        model_event_index = max(index for index, _ in model_evidence)
        if _model_family(observed_model) is None:
            errors.append(
                f"observed model {observed_model!r} has no unambiguous known family"
            )
        if not _model_matches(observed_model, expected_model):
            errors.append(
                f"observed model {observed_model!r} does not match "
                f"expected {expected_model!r}"
            )

    results = [
        (event_index, event)
        for event_index, event in enumerate(events)
        if event.get("type") == "result"
    ]
    if len(results) != 1:
        errors.append(
            f"expected exactly one final result event, found {len(results)}"
        )
    else:
        result_index, result = results[0]
        if result.get("subtype") != "success":
            errors.append("final result subtype is not 'success'")
        if result.get("is_error") is not False:
            errors.append("final result is_error is not exactly false")
        result_text = result.get("result")
        if not isinstance(result_text, str):
            errors.append("final result text is not a string")
        elif not result_text.strip():
            errors.append("final result text is empty")
        elif result_text != expected_result:
            errors.append(
                f"final result text does not exactly match {expected_result!r}"
            )
        if model_event_index is not None and result_index <= model_event_index:
            errors.append("final result appears before assistant model evidence")

    return errors, observed_model


def verify_trace(
    path: Path, expected_model: str, expected_result: str
) -> tuple[list[str], str | None, int]:
    events, errors = load_events(path)
    if errors:
        return errors, None, len(events)
    verification_errors, observed_model = verify_events(
        events, expected_model, expected_result
    )
    return verification_errors, observed_model, len(events)


def _print_limitation() -> None:
    print("LIMITATION")
    print("- this is observed trace evidence, not cryptographic proof of execution")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="Claude Code stream-json JSONL file")
    parser.add_argument(
        "--expected-model",
        required=True,
        help=(
            "expected model alias/family (opus, sonnet, haiku, fable) or exact "
            "resolved model id"
        ),
    )
    parser.add_argument(
        "--expected-result",
        required=True,
        help="exact final result text, including case and whitespace",
    )
    args = parser.parse_args(argv)

    if not args.expected_model.strip():
        print("DIRECT TRACE FAIL")
        print("- expected model must not be empty")
        _print_limitation()
        return 1
    if not args.expected_result.strip():
        print("DIRECT TRACE FAIL")
        print("- expected result must not be empty")
        _print_limitation()
        return 1

    errors, observed_model, event_count = verify_trace(
        args.trace, args.expected_model, args.expected_result
    )
    if errors:
        print("DIRECT TRACE FAIL")
        for error in errors:
            print(f"- {error}")
        _print_limitation()
        return 1

    print("DIRECT TRACE PASS")
    print(f"- parsed {event_count} JSON events from one session")
    print(f"- observed direct assistant message.model: {observed_model}")
    print(f"- final result exactly matched {args.expected_result!r}")
    _print_limitation()
    return 0


if __name__ == "__main__":
    sys.exit(main())
