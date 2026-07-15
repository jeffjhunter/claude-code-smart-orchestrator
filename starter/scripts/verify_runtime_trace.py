#!/usr/bin/env python3
"""Verify observed Claude Code Agent/model evidence in a stream-json trace."""

from __future__ import annotations

import argparse
import codecs
import json
from pathlib import Path
import re
import sys
from typing import Any


MODEL_FAMILIES = ("opus", "sonnet", "haiku")


def _decode_trace(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16")
    return data.decode("utf-8")


def load_events(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        text = _decode_trace(path)
    except FileNotFoundError:
        return [], ["trace file does not exist"]
    except IsADirectoryError:
        return [], ["trace path is a directory, not a file"]
    except UnicodeDecodeError:
        return [], ["trace must be UTF-8 or BOM-marked UTF-16"]
    except OSError as exc:
        return [], [f"trace could not be read ({exc.__class__.__name__})"]

    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"line {line_number}: malformed JSON")
            continue
        if not isinstance(event, dict):
            errors.append(f"line {line_number}: event must be a JSON object")
            continue
        events.append(event)
    if not events and not errors:
        errors.append("trace contains no JSON events")
    return events, errors


def _agent_calls(
    events: list[dict[str, Any]],
) -> list[tuple[int, str, str, dict[str, Any]]]:
    calls: list[tuple[int, str, str, dict[str, Any]]] = []
    for event_index, event in enumerate(events):
        if event.get("type") != "assistant":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use" or block.get("name") != "Agent":
                continue
            tool_id = block.get("id")
            raw_inputs = block.get("input")
            inputs = raw_inputs if isinstance(raw_inputs, dict) else {}
            subagent_type = inputs.get("subagent_type")
            if isinstance(tool_id, str) and tool_id and isinstance(subagent_type, str):
                calls.append((event_index, tool_id, subagent_type, inputs))
            else:
                calls.append((event_index, "", "", inputs))
    return calls


def _model_family(model: str) -> str | None:
    lowered = model.casefold()
    if lowered in MODEL_FAMILIES:
        return lowered
    supported_prefix = lowered.startswith("claude-") or bool(
        re.match(r"^(?:(?:[a-z]{2}|global)\.)?anthropic\.claude-", lowered)
    )
    if not supported_prefix:
        return None
    matches = [
        family
        for family in MODEL_FAMILIES
        if re.search(rf"(?:^|[-_]){re.escape(family)}(?:$|[-_])", lowered)
    ]
    return matches[0] if len(matches) == 1 else None


def _model_matches(observed: str, expected: str) -> bool:
    observed_lower = observed.casefold()
    expected_lower = expected.casefold()
    if expected_lower in MODEL_FAMILIES:
        return _model_family(observed_lower) == expected_lower
    return observed_lower == expected_lower


def verify_events(
    events: list[dict[str, Any]], expected_agent: str, expected_model: str
) -> tuple[list[str], str | None]:
    errors: list[str] = []
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

    calls = _agent_calls(events)
    if len(calls) != 1:
        errors.append(f"expected exactly one Agent tool call, found {len(calls)}")
        return errors, None

    call_index, tool_id, subagent_type, call_inputs = calls[0]
    if not tool_id or not subagent_type:
        errors.append("Agent tool call has malformed id or subagent_type")
        return errors, None
    if subagent_type != expected_agent:
        errors.append(
            f"Agent tool call selected {subagent_type!r}, expected {expected_agent!r}"
        )
    if call_inputs.get("model") not in (None, ""):
        errors.append("Agent tool call contains a per-call model override")

    task_events = [
        (index, event)
        for index, event in enumerate(events)
        if event.get("type") == "system"
        and isinstance(event.get("subtype"), str)
        and event["subtype"].startswith("task_")
    ]
    supported_task_subtypes = {
        "task_started",
        "task_progress",
        "task_notification",
    }
    for event_index, event in task_events:
        subtype = event["subtype"]
        if subtype not in supported_task_subtypes:
            errors.append(
                f"event {event_index + 1} has unsupported task lifecycle subtype "
                f"{subtype!r}"
            )

    starts = [
        (index, event)
        for index, event in task_events
        if event.get("subtype") == "task_started"
    ]
    if len(starts) != 1:
        errors.append(
            f"expected exactly one task_started event, found {len(starts)}"
        )
        task_start_index = None
        task_id = None
    else:
        task_start_index, task_start = starts[0]
        task_id = task_start.get("task_id")
        if task_start.get("subagent_type") != expected_agent:
            errors.append("linked task_started event names the wrong subagent")
        if not isinstance(task_id, str) or not task_id:
            errors.append("linked task_started event has no task_id")
            task_id = None

    notifications = [
        (index, event)
        for index, event in task_events
        if event.get("subtype") == "task_notification"
    ]
    if len(notifications) != 1:
        errors.append(
            "expected exactly one terminal task_notification event, "
            f"found {len(notifications)}"
        )
        task_notification_index = None
    else:
        task_notification_index, task_notification = notifications[0]
        if task_notification.get("status") != "completed":
            errors.append(
                "linked task_notification status is not 'completed': "
                f"{task_notification.get('status')!r}"
            )

    for event_index, event in task_events:
        subtype = event["subtype"]
        if event.get("tool_use_id") != tool_id:
            errors.append(
                f"event {event_index + 1} {subtype} does not link to the sole "
                "Agent tool call"
            )
        if task_id is not None and event.get("task_id") != task_id:
            errors.append(
                f"event {event_index + 1} {subtype} does not belong to the sole "
                "started task"
            )
        event_agent = event.get("subagent_type")
        if subtype in {"task_started", "task_progress"}:
            if event_agent != expected_agent:
                errors.append(
                    f"event {event_index + 1} {subtype} names the wrong subagent"
                )
        elif event_agent not in (None, expected_agent):
            errors.append(
                f"event {event_index + 1} {subtype} names the wrong subagent"
            )

    if task_start_index is not None and task_start_index <= call_index:
        errors.append("linked task_started event appears before its Agent tool call")
    if (
        task_start_index is not None
        and task_notification_index is not None
        and task_notification_index <= task_start_index
    ):
        errors.append("linked task_notification appears before task_started")

    for event_index, event in task_events:
        if event.get("subtype") != "task_progress":
            continue
        if task_start_index is not None and event_index <= task_start_index:
            errors.append("task_progress appears before task_started")
        if (
            task_notification_index is not None
            and event_index >= task_notification_index
        ):
            errors.append("task_progress appears after task_notification")

    lifecycle_agents = {
        event["subagent_type"]
        for event in events
        if isinstance(event.get("subagent_type"), str)
    }
    unexpected_lifecycle_agents = lifecycle_agents - {expected_agent}
    if unexpected_lifecycle_agents:
        errors.append(
            "trace contains lifecycle events for unexpected agents: "
            + ", ".join(sorted(unexpected_lifecycle_agents))
        )

    for event_index, event in enumerate(events):
        subtype = event.get("subtype")
        if (
            event.get("type") == "system"
            and isinstance(subtype, str)
            and subtype.startswith("task_")
        ):
            continue
        parent_tool_use_id = event.get("parent_tool_use_id")
        event_agent = event.get("subagent_type")
        if parent_tool_use_id in (None, "") and event_agent in (None, ""):
            continue
        if parent_tool_use_id != tool_id:
            errors.append(
                f"event {event_index + 1} is subagent-scoped but does not link "
                "to the sole Agent tool call"
            )
        if event_agent != expected_agent:
            errors.append(
                f"event {event_index + 1} is subagent-scoped but names the "
                "wrong subagent"
            )

    model_evidence: list[tuple[int, str]] = []
    for event_index, event in enumerate(events):
        if event.get("type") != "assistant":
            continue
        if event.get("parent_tool_use_id") != tool_id:
            continue
        if event.get("subagent_type") != expected_agent:
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        model = message.get("model")
        if isinstance(model, str) and model.strip():
            model_evidence.append((event_index, model.strip()))

    unique_models = sorted({model for _, model in model_evidence}, key=str.casefold)
    if not unique_models:
        errors.append("no assistant model evidence was linked to the expected Agent call")
        observed_model = None
    elif len(unique_models) != 1:
        errors.append(
            "ambiguous assistant model evidence: " + ", ".join(unique_models)
        )
        observed_model = None
    else:
        observed_model = unique_models[0]
        if _model_family(observed_model) is None:
            errors.append(f"observed model {observed_model!r} has no unambiguous known family")
        if not _model_matches(observed_model, expected_model):
            errors.append(
                f"observed model {observed_model!r} does not match "
                f"expected {expected_model!r}"
            )

    linked_agent_results: list[tuple[int, dict[str, Any]]] = []
    for event_index, event in enumerate(events):
        if event.get("type") != "user":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and block.get("tool_use_id") == tool_id
            ):
                linked_agent_results.append((event_index, block))

    if len(linked_agent_results) != 1:
        errors.append(
            "expected exactly one linked Agent tool result, "
            f"found {len(linked_agent_results)}"
        )
        agent_result_index = None
    else:
        agent_result_index, agent_result = linked_agent_results[0]
        if agent_result.get("is_error") is True:
            errors.append("linked Agent tool result reports an error")
        content = agent_result.get("content")
        if isinstance(content, str):
            nonempty_content = bool(content.strip())
        elif isinstance(content, list):
            nonempty_content = bool(content) and all(
                isinstance(item, dict)
                and item.get("type") == "text"
                and isinstance(item.get("text"), str)
                and bool(item["text"].strip())
                and item.get("is_error") is not True
                for item in content
            )
        else:
            nonempty_content = False
        if not nonempty_content:
            errors.append("linked Agent tool result has no non-empty content")

    child_indices = [index for index, _ in model_evidence]
    if child_indices and min(child_indices) <= call_index:
        errors.append("subagent model evidence appears before its Agent tool call")
    if (
        child_indices
        and task_start_index is not None
        and min(child_indices) <= task_start_index
    ):
        errors.append("subagent model evidence appears before task_started")
    if (
        child_indices
        and task_notification_index is not None
        and task_notification_index < max(child_indices)
    ):
        errors.append("task_notification appears before subagent model evidence completed")
    if agent_result_index is not None:
        if agent_result_index <= call_index:
            errors.append("linked Agent tool result appears before its Agent tool call")
        if child_indices and agent_result_index <= max(child_indices):
            errors.append("linked Agent tool result appears before subagent model evidence completed")
        if (
            task_notification_index is not None
            and agent_result_index <= task_notification_index
        ):
            errors.append("linked Agent tool result appears before task_notification")

    results = [
        (event_index, event)
        for event_index, event in enumerate(events)
        if event.get("type") == "result"
    ]
    if len(results) != 1:
        errors.append(f"expected exactly one final result event, found {len(results)}")
    else:
        result_index, result = results[0]
        if result.get("subtype") != "success" or result.get("is_error") is not False:
            errors.append("final result event is not an unambiguous success")
        if not isinstance(result.get("result"), str) or not result["result"].strip():
            errors.append("successful final result has no non-empty result text")
        if result_index <= call_index:
            errors.append("final result appears before the Agent tool call")
        if agent_result_index is not None and result_index <= agent_result_index:
            errors.append("final result appears before the linked Agent tool result")

    return errors, observed_model


def verify_trace(
    path: Path, expected_agent: str, expected_model: str
) -> tuple[list[str], str | None, int]:
    events, errors = load_events(path)
    if errors:
        return errors, None, len(events)
    verification_errors, observed_model = verify_events(
        events, expected_agent, expected_model
    )
    return verification_errors, observed_model, len(events)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="Claude Code stream-json JSONL file")
    parser.add_argument("--expected-agent", required=True, help="expected subagent_type")
    parser.add_argument(
        "--expected-model",
        required=True,
        help="expected model alias/family (opus, sonnet, haiku) or exact resolved model id",
    )
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[a-z][a-z0-9-]*", args.expected_agent):
        print("OBSERVED TRACE FAIL")
        print("- expected agent must be a lowercase kebab-case name")
        return 1
    if not args.expected_model.strip():
        print("OBSERVED TRACE FAIL")
        print("- expected model must not be empty")
        return 1

    errors, observed_model, event_count = verify_trace(
        args.trace, args.expected_agent, args.expected_model
    )
    if errors:
        print("OBSERVED TRACE FAIL")
        for error in errors:
            print(f"- {error}")
        print("- this is observed trace evidence, not cryptographic proof of execution")
        return 1

    print("OBSERVED TRACE PASS")
    print(f"- parsed {event_count} JSON events")
    print(f"- observed exactly one Agent call for {args.expected_agent!r}")
    print(f"- linked assistant model evidence: {observed_model}")
    print("- completed task lifecycle links to one non-error Agent tool result")
    print("- final result event reports success")
    print("LIMITATION")
    print("- this is observed trace evidence, not cryptographic proof of execution")
    return 0


if __name__ == "__main__":
    sys.exit(main())
