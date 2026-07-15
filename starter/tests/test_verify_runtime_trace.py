from __future__ import annotations

import codecs
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify_runtime_trace  # noqa: E402


def resolved_model(family: str = "opus") -> str:
    return "claude-" + family + "-" + "4-1"


def valid_events(
    agent: str = "architect", model: str | None = None
) -> list[dict[str, object]]:
    model = model or resolved_model()
    return [
        {
            "type": "system",
            "subtype": "init",
            "model": resolved_model("sonnet"),
            "session_id": "session-1",
        },
        {
            "type": "assistant",
            "session_id": "session-1",
            "message": {
                "role": "assistant",
                "model": resolved_model("sonnet"),
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-agent-1",
                        "name": "Agent",
                        "input": {"subagent_type": agent, "prompt": "Inspect."},
                    }
                ],
            },
        },
        {
            "type": "system",
            "subtype": "task_started",
            "task_id": "task-1",
            "tool_use_id": "tool-agent-1",
            "subagent_type": agent,
            "task_type": "local_agent",
            "session_id": "session-1",
        },
        {
            "type": "assistant",
            "session_id": "session-1",
            "parent_tool_use_id": "tool-agent-1",
            "subagent_type": agent,
            "message": {
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": "Observed response."}],
            },
        },
        {
            "type": "system",
            "subtype": "task_notification",
            "task_id": "task-1",
            "tool_use_id": "tool-agent-1",
            "status": "completed",
            "summary": "Roadmap.",
            "session_id": "session-1",
        },
        {
            "type": "user",
            "session_id": "session-1",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-agent-1",
                        "content": [
                            {"type": "text", "text": "Agent completed."}
                        ],
                    }
                ],
            },
        },
        {
            "type": "result",
            "session_id": "session-1",
            "subtype": "success",
            "is_error": False,
            "result": "Completed successfully.",
        },
    ]


def valid_async_events(
    agent: str = "fable-planner", model: str | None = None
) -> list[dict[str, object]]:
    model = model or resolved_model("fable")
    return [
        {
            "type": "system",
            "subtype": "init",
            "model": resolved_model("sonnet"),
            "session_id": "session-1",
        },
        {
            "type": "assistant",
            "session_id": "session-1",
            "message": {
                "role": "assistant",
                "model": resolved_model("sonnet"),
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-agent-1",
                        "name": "Agent",
                        "input": {"subagent_type": agent, "prompt": "Plan."},
                    }
                ],
            },
        },
        {
            "type": "system",
            "subtype": "task_started",
            "task_id": "task-1",
            "tool_use_id": "tool-agent-1",
            "subagent_type": agent,
            "task_type": "local_agent",
            "session_id": "session-1",
        },
        {
            "type": "user",
            "session_id": "session-1",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-agent-1",
                        "content": [{"type": "text", "text": "Launched."}],
                    }
                ],
            },
            "tool_use_result": {
                "isAsync": True,
                "status": "async_launched",
                "agentId": "task-1",
                "resolvedModel": model,
            },
        },
        {
            "type": "assistant",
            "session_id": "session-1",
            "parent_tool_use_id": "tool-agent-1",
            "subagent_type": agent,
            "message": {
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": "Roadmap."}],
            },
        },
        {
            "type": "system",
            "subtype": "task_progress",
            "task_id": "task-1",
            "tool_use_id": "tool-agent-1",
            "subagent_type": agent,
            "session_id": "session-1",
        },
        {
            "type": "system",
            "subtype": "task_updated",
            "task_id": "task-1",
            "patch": {"status": "completed"},
            "session_id": "session-1",
        },
        {
            "type": "system",
            "subtype": "task_notification",
            "task_id": "task-1",
            "tool_use_id": "tool-agent-1",
            "status": "completed",
            "summary": "Roadmap.",
            "session_id": "session-1",
        },
        {
            "type": "result",
            "session_id": "session-1",
            "subtype": "success",
            "is_error": False,
            "result": "Launch command completed.",
        },
        {
            "type": "result",
            "session_id": "session-1",
            "subtype": "success",
            "is_error": False,
            "result": "Background task completed.",
            "origin": {"kind": "task-notification"},
        },
    ]


def valid_foreground_completion_events(
    agent: str = "fable-planner", model: str | None = None
) -> list[dict[str, object]]:
    model = model or resolved_model("fable")
    events = valid_events(agent=agent, model=model)
    events.insert(
        4,
        {
            "type": "system",
            "subtype": "task_updated",
            "task_id": "task-1",
            "patch": {"status": "completed"},
            "session_id": "session-1",
        },
    )
    events[6]["tool_use_result"] = {
        "status": "completed",
        "agentId": "task-1",
        "agentType": agent,
        "resolvedModel": model,
    }
    return events


def jsonl(events: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(event, separators=(",", ":")) for event in events) + "\n"


class RuntimeTraceVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "trace.jsonl"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def verify(
        self, agent: str = "architect", model: str = "opus"
    ) -> tuple[list[str], str | None, int]:
        return verify_runtime_trace.verify_trace(self.path, agent, model)

    def test_utf8_trace_passes_for_expected_model_family(self) -> None:
        self.path.write_text(jsonl(valid_events()), encoding="utf-8")
        errors, model, count = self.verify()
        self.assertEqual(errors, [])
        self.assertEqual(model, resolved_model())
        self.assertEqual(count, 7)

    def test_fable_trace_passes_when_fable_is_expected(self) -> None:
        self.path.write_text(
            jsonl(valid_events(agent="fable-planner", model=resolved_model("fable"))),
            encoding="utf-8",
        )
        errors, model, count = self.verify(agent="fable-planner", model="fable")
        self.assertEqual(errors, [])
        self.assertEqual(model, resolved_model("fable"))
        self.assertEqual(count, 7)

    def test_foreground_completion_metadata_and_update_are_accepted(self) -> None:
        events = valid_foreground_completion_events()
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, model, count = self.verify(
            agent="fable-planner", model="fable"
        )
        self.assertEqual(errors, [])
        self.assertEqual(model, resolved_model("fable"))
        self.assertEqual(count, 8)

    def test_foreground_completion_metadata_is_strictly_linked(self) -> None:
        mutations = (
            ("status", "running", "status is not 'completed'"),
            ("agentId", "different-task", "agentId does not match"),
            ("agentType", "qa-reviewer", "wrong agentType"),
            ("resolvedModel", resolved_model("opus"), "resolvedModel"),
        )
        for key, value, expected_error in mutations:
            with self.subTest(key=key):
                events = valid_foreground_completion_events()
                events[6]["tool_use_result"][key] = value
                self.path.write_text(jsonl(events), encoding="utf-8")
                errors, _, _ = self.verify(
                    agent="fable-planner", model="fable"
                )
                self.assertTrue(
                    any(expected_error in error for error in errors), errors
                )

    def test_agent_result_metadata_must_be_an_object(self) -> None:
        events = valid_foreground_completion_events()
        events[6]["tool_use_result"] = "completed"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("metadata is not an object" in error for error in errors))

    def test_completed_update_follows_all_subagent_activity(self) -> None:
        events = valid_foreground_completion_events()
        events.insert(
            5,
            {
                "type": "user",
                "session_id": "session-1",
                "parent_tool_use_id": "tool-agent-1",
                "subagent_type": "fable-planner",
                "message": {"role": "user", "content": []},
            },
        )
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(
            any("after all subagent activity" in error for error in errors),
            errors,
        )

    def test_opus_trace_fails_when_fable_is_expected(self) -> None:
        self.path.write_text(
            jsonl(valid_events(agent="fable-planner", model=resolved_model("opus"))),
            encoding="utf-8",
        )
        errors, model, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("does not match" in error for error in errors))
        self.assertEqual(model, resolved_model("opus"))

    def test_async_fable_trace_passes_with_or_without_task_updated(self) -> None:
        for include_update in (True, False):
            with self.subTest(include_update=include_update):
                events = valid_async_events()
                if not include_update:
                    del events[6]
                self.path.write_text(jsonl(events), encoding="utf-8")
                errors, model, count = self.verify(
                    agent="fable-planner", model="fable"
                )
                self.assertEqual(errors, [])
                self.assertEqual(model, resolved_model("fable"))
                self.assertEqual(count, 10 if include_update else 9)

    def test_async_launch_agent_id_must_match_started_task(self) -> None:
        events = valid_async_events()
        events[3]["tool_use_result"]["agentId"] = "different-task"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("agentId does not match" in error for error in errors))

    def test_async_launch_resolved_model_must_match_observed_and_expected(self) -> None:
        events = valid_async_events()
        events[3]["tool_use_result"]["resolvedModel"] = resolved_model("opus")
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("resolvedModel" in error for error in errors))
        self.assertTrue(any("does not exactly match" in error for error in errors))

    def test_async_launch_requires_completed_notification_and_progress(self) -> None:
        mutations = (
            ("missing notification", lambda events: events.pop(7), "task_notification"),
            ("missing progress", lambda events: events.pop(5), "task_progress"),
        )
        for label, mutate, expected_error in mutations:
            with self.subTest(label=label):
                events = valid_async_events()
                mutate(events)
                self.path.write_text(jsonl(events), encoding="utf-8")
                errors, _, _ = self.verify(agent="fable-planner", model="fable")
                self.assertTrue(
                    any(expected_error in error for error in errors), errors
                )

    def test_async_started_event_requires_local_agent_task_type(self) -> None:
        events = valid_async_events()
        events[2]["task_type"] = "local_bash"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("task_type is not 'local_agent'" in error for error in errors))

    def test_foreground_started_event_requires_local_agent_task_type(self) -> None:
        for value in (None, "local_bash"):
            with self.subTest(value=value):
                events = valid_events()
                if value is None:
                    del events[2]["task_type"]
                else:
                    events[2]["task_type"] = value
                self.path.write_text(jsonl(events), encoding="utf-8")
                errors, _, _ = self.verify()
                self.assertTrue(
                    any(
                        "task_type is not 'local_agent'" in error
                        for error in errors
                    ),
                    errors,
                )

    def test_async_notification_requires_nonempty_terminal_summary(self) -> None:
        for value in (None, "   "):
            with self.subTest(value=value):
                events = valid_async_events()
                events[7]["summary"] = value
                self.path.write_text(jsonl(events), encoding="utf-8")
                errors, _, _ = self.verify(agent="fable-planner", model="fable")
                self.assertTrue(
                    any("no non-empty terminal summary" in error for error in errors),
                    errors,
                )

    def test_async_launch_acknowledgement_must_follow_task_started(self) -> None:
        events = valid_async_events()
        events[2], events[3] = events[3], events[2]
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(
            any("launch result does not appear after task_started" in error for error in errors),
            errors,
        )

    def test_async_launch_acknowledgement_precedes_child_progress_and_update(self) -> None:
        def move_ack_after_child_and_progress(
            events: list[dict[str, object]],
        ) -> None:
            acknowledgement = events.pop(3)
            events.insert(5, acknowledgement)

        def move_completed_update_before_ack(
            events: list[dict[str, object]],
        ) -> None:
            completed_update = events.pop(6)
            events.insert(3, completed_update)

        for mutate in (
            move_ack_after_child_and_progress,
            move_completed_update_before_ack,
        ):
            with self.subTest(mutation=mutate.__name__):
                events = valid_async_events()
                mutate(events)
                self.path.write_text(jsonl(events), encoding="utf-8")
                errors, _, _ = self.verify(
                    agent="fable-planner", model="fable"
                )
                self.assertTrue(
                    any(
                        "after the async Agent launch result" in error
                        for error in errors
                    ),
                    errors,
                )

    def test_async_completed_update_follows_child_and_progress(self) -> None:
        events = valid_async_events()
        completed_update = events.pop(6)
        events.insert(4, completed_update)
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(
            any(
                "task_updated completion does not appear after" in error
                for error in errors
            ),
            errors,
        )

    def test_linked_agent_result_event_must_be_parent_scoped(self) -> None:
        events = valid_async_events()
        events[3]["parent_tool_use_id"] = "tool-agent-1"
        events[3]["subagent_type"] = "fable-planner"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(
            any("unexpectedly subagent-scoped" in error for error in errors),
            errors,
        )

    def test_subagent_scoped_activity_after_notification_is_rejected(self) -> None:
        events = valid_async_events()
        events.insert(
            8,
            {
                "type": "user",
                "session_id": "session-1",
                "parent_tool_use_id": "tool-agent-1",
                "subagent_type": "fable-planner",
                "message": {"role": "user", "content": []},
            },
        )
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(
            any("does not appear before task_notification" in error for error in errors),
            errors,
        )

    def test_linked_agent_result_rejects_malformed_error_markers(self) -> None:
        events = valid_async_events()
        agent_result = events[3]["message"]["content"][0]
        agent_result["is_error"] = "false"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(
            any("not an unambiguous non-error" in error for error in errors),
            errors,
        )

        events = valid_async_events()
        agent_result = events[3]["message"]["content"][0]
        agent_result["content"][0]["is_error"] = "false"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(
            any("no non-empty content" in error for error in errors), errors
        )

    def test_async_task_updated_requires_completed_status_and_valid_links(self) -> None:
        def bad_status(events: list[dict[str, object]]) -> None:
            events[6]["patch"]["status"] = "running"

        def bad_task(events: list[dict[str, object]]) -> None:
            events[6]["task_id"] = "different-task"

        def bad_tool(events: list[dict[str, object]]) -> None:
            events[6]["tool_use_id"] = "different-tool"

        mutations = (
            (bad_status, "patch status is not 'completed'"),
            (bad_task, "does not belong to the sole started task"),
            (bad_tool, "does not link to the sole Agent tool call"),
        )
        for mutate, expected_error in mutations:
            with self.subTest(expected_error=expected_error):
                events = valid_async_events()
                mutate(events)
                self.path.write_text(jsonl(events), encoding="utf-8")
                errors, _, _ = self.verify(agent="fable-planner", model="fable")
                self.assertTrue(
                    any(expected_error in error for error in errors), errors
                )

    def test_async_duplicate_results_require_one_task_notification_origin(self) -> None:
        events = valid_async_events()
        events[9]["origin"] = {"kind": "something-else"}
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("origin.kind" in error for error in errors))

        events = valid_async_events()
        events.append(dict(events[9]))
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("found 3" in error for error in errors))

    def test_async_incomplete_child_without_model_evidence_is_rejected(self) -> None:
        events = valid_async_events()
        del events[4]
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, model, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("no assistant model evidence" in error for error in errors))
        self.assertIsNone(model)

    def test_async_terminal_results_must_be_non_error_and_nonempty(self) -> None:
        events = valid_async_events()
        events[9]["subtype"] = "error"
        events[9]["is_error"] = True
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("not an unambiguous success" in error for error in errors))

        events = valid_async_events()
        events[9]["result"] = "   "
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("no non-empty result text" in error for error in errors))

    def test_async_launch_status_must_be_async_launched(self) -> None:
        events = valid_async_events()
        events[3]["tool_use_result"]["status"] = "queued"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify(agent="fable-planner", model="fable")
        self.assertTrue(any("status is not 'async_launched'" in error for error in errors))

    def test_utf8_bom_trace_passes_for_exact_resolved_model(self) -> None:
        self.path.write_bytes(codecs.BOM_UTF8 + jsonl(valid_events()).encode("utf-8"))
        errors, model, _ = self.verify(model=resolved_model())
        self.assertEqual(errors, [])
        self.assertEqual(model, resolved_model())

    def test_utf16_bom_trace_passes(self) -> None:
        self.path.write_text(jsonl(valid_events()), encoding="utf-16")
        errors, model, count = self.verify()
        self.assertEqual(errors, [])
        self.assertEqual(model, resolved_model())
        self.assertEqual(count, 7)

    def test_malformed_json_fails_closed(self) -> None:
        self.path.write_text('{"type":"assistant"}\nnot-json\n', encoding="utf-8")
        errors, model, _ = self.verify()
        self.assertTrue(any("malformed JSON" in error for error in errors))
        self.assertIsNone(model)

    def test_invalid_unicode_fails_closed(self) -> None:
        self.path.write_bytes(b"\xff\xfe\x00")
        errors, _, _ = self.verify()
        self.assertTrue(errors)

    def test_multiple_agent_calls_are_ambiguous_and_rejected(self) -> None:
        events = valid_events()
        second_call = {
            "type": "assistant",
            "session_id": "session-1",
            "message": {
                "role": "assistant",
                "model": resolved_model("sonnet"),
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool-agent-2",
                        "name": "Agent",
                        "input": {"subagent_type": "qa-reviewer"},
                    }
                ],
            },
        }
        events.insert(2, second_call)
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("exactly one Agent tool call" in error for error in errors))

    def test_wrong_agent_is_rejected(self) -> None:
        self.path.write_text(jsonl(valid_events(agent="qa-reviewer")), encoding="utf-8")
        errors, _, _ = self.verify(agent="architect", model="opus")
        self.assertTrue(any("expected 'architect'" in error for error in errors))

    def test_unexpected_agent_lifecycle_event_is_rejected(self) -> None:
        events = valid_events()
        events.insert(
            3,
            {
                "type": "system",
                "subtype": "task_started",
                "subagent_type": "qa-reviewer",
                "session_id": "session-1",
            },
        )
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("unexpected agents" in error for error in errors))

    def test_linked_task_progress_event_is_accepted(self) -> None:
        events = valid_events()
        events.insert(
            3,
            {
                "type": "system",
                "subtype": "task_progress",
                "task_id": "task-1",
                "tool_use_id": "tool-agent-1",
                "subagent_type": "architect",
                "session_id": "session-1",
            },
        )
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, model, _ = self.verify()
        self.assertEqual(errors, [])
        self.assertEqual(model, resolved_model())

    def test_orphan_same_agent_task_events_are_rejected(self) -> None:
        for subtype in ("task_started", "task_progress", "task_notification"):
            with self.subTest(subtype=subtype):
                events = valid_events()
                orphan = {
                    "type": "system",
                    "subtype": subtype,
                    "task_id": "orphan-task",
                    "tool_use_id": "orphan-tool",
                    "subagent_type": "architect",
                    "session_id": "session-1",
                }
                if subtype == "task_notification":
                    orphan["status"] = "completed"
                events.insert(3, orphan)
                self.path.write_text(jsonl(events), encoding="utf-8")
                errors, _, _ = self.verify()
                self.assertTrue(
                    any("does not link to the sole Agent tool call" in error for error in errors),
                    errors,
                )

    def test_same_agent_task_event_with_wrong_task_id_is_rejected(self) -> None:
        events = valid_events()
        events.insert(
            3,
            {
                "type": "system",
                "subtype": "task_progress",
                "task_id": "orphan-task",
                "tool_use_id": "tool-agent-1",
                "subagent_type": "architect",
                "session_id": "session-1",
            },
        )
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(
            any("does not belong to the sole started task" in error for error in errors)
        )

    def test_orphan_same_agent_child_model_event_is_rejected(self) -> None:
        events = valid_events()
        orphan_model_event = dict(events[3])
        orphan_model_event["parent_tool_use_id"] = "orphan-tool"
        orphan_model_event["message"] = {
            "role": "assistant",
            "model": resolved_model("sonnet"),
            "content": [{"type": "text", "text": "Orphan response."}],
        }
        events.insert(4, orphan_model_event)
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(
            any("subagent-scoped but does not link" in error for error in errors),
            errors,
        )

    def test_unknown_task_lifecycle_subtype_is_rejected(self) -> None:
        events = valid_events()
        events.insert(
            3,
            {
                "type": "system",
                "subtype": "task_paused",
                "task_id": "task-1",
                "tool_use_id": "tool-agent-1",
                "subagent_type": "architect",
                "session_id": "session-1",
            },
        )
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("unsupported task lifecycle subtype" in error for error in errors))

    def test_unlinked_model_evidence_is_rejected(self) -> None:
        events = valid_events()
        events[3]["parent_tool_use_id"] = "different-tool"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, model, _ = self.verify()
        self.assertTrue(any("no assistant model evidence" in error for error in errors))
        self.assertIsNone(model)

    def test_ambiguous_subagent_models_are_rejected(self) -> None:
        events = valid_events()
        second_model_event = dict(events[3])
        second_model_event["message"] = {
            "role": "assistant",
            "model": resolved_model("sonnet"),
            "content": [{"type": "text", "text": "Different model."}],
        }
        events.insert(4, second_model_event)
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, model, _ = self.verify()
        self.assertTrue(any("ambiguous assistant model evidence" in error for error in errors))
        self.assertIsNone(model)

    def test_wrong_model_family_is_rejected(self) -> None:
        self.path.write_text(
            jsonl(valid_events(model=resolved_model("sonnet"))), encoding="utf-8"
        )
        errors, _, _ = self.verify(model="opus")
        self.assertTrue(any("does not match" in error for error in errors))

    def test_failed_or_duplicate_final_result_is_rejected(self) -> None:
        events = valid_events()
        events[-1]["subtype"] = "error"
        events[-1]["is_error"] = True
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("not an unambiguous success" in error for error in errors))

        events.append(
            {
                "type": "result",
                "session_id": "session-1",
                "subtype": "success",
                "is_error": False,
                "result": "Second result.",
            }
        )
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("exactly one final result" in error for error in errors))

    def test_user_supplied_fake_agent_block_does_not_count(self) -> None:
        events = valid_events()
        events.insert(
            1,
            {
                "type": "user",
                "session_id": "session-1",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "fake",
                            "name": "Agent",
                            "input": {"subagent_type": "qa-reviewer"},
                        }
                    ],
                },
            },
        )
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertEqual(errors, [])

    def test_failed_agent_tool_result_is_rejected_even_if_parent_succeeds(self) -> None:
        events = valid_events()
        events[5]["message"]["content"][0]["is_error"] = True
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("Agent tool result reports an error" in error for error in errors))

    def test_out_of_order_trace_is_rejected(self) -> None:
        events = valid_events()
        events[1], events[3] = events[3], events[1]
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("appears before its Agent tool call" in error for error in errors))

    def test_child_model_before_task_started_is_rejected(self) -> None:
        events = valid_events()
        events[2], events[3] = events[3], events[2]
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("model evidence appears before task_started" in error for error in errors))

    def test_task_notification_before_child_model_is_rejected(self) -> None:
        events = valid_events()
        events[3], events[4] = events[4], events[3]
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("task_notification appears before" in error for error in errors))

    def test_mixed_or_missing_session_ids_are_rejected(self) -> None:
        events = valid_events()
        events[3]["session_id"] = "session-2"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("exactly one session_id" in error for error in errors))

        events = valid_events()
        del events[3]["session_id"]
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("has no non-empty session_id" in error for error in errors))

    def test_forged_model_name_without_supported_claude_prefix_is_rejected(self) -> None:
        self.path.write_text(
            jsonl(valid_events(model="not-opus-test")), encoding="utf-8"
        )
        errors, _, _ = self.verify()
        self.assertTrue(any("no unambiguous known family" in error for error in errors))

    def test_per_call_model_override_is_rejected(self) -> None:
        events = valid_events()
        events[1]["message"]["content"][0]["input"]["model"] = "haiku"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("per-call model override" in error for error in errors))

    def test_failed_task_notification_is_rejected(self) -> None:
        events = valid_events()
        events[4]["status"] = "failed"
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("status is not 'completed'" in error for error in errors))

    def test_malformed_agent_result_content_list_is_rejected(self) -> None:
        events = valid_events()
        events[5]["message"]["content"][0]["content"] = [
            {"type": "text", "text": ""},
            {"type": "image", "source": "untrusted"},
        ]
        self.path.write_text(jsonl(events), encoding="utf-8")
        errors, _, _ = self.verify()
        self.assertTrue(any("no non-empty content" in error for error in errors))

    def test_cli_output_states_observed_evidence_limitation(self) -> None:
        self.path.write_text(jsonl(valid_events()), encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            result = verify_runtime_trace.main(
                [
                    str(self.path),
                    "--expected-agent",
                    "architect",
                    "--expected-model",
                    "opus",
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("OBSERVED TRACE PASS", output.getvalue())
        self.assertIn("foreground task lifecycle", output.getvalue())
        self.assertIn("not cryptographic proof", output.getvalue())

    def test_cli_output_identifies_async_completion(self) -> None:
        self.path.write_text(jsonl(valid_async_events()), encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            result = verify_runtime_trace.main(
                [
                    str(self.path),
                    "--expected-agent",
                    "fable-planner",
                    "--expected-model",
                    "fable",
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("OBSERVED TRACE PASS", output.getvalue())
        self.assertIn("async task lifecycle", output.getvalue())
        self.assertIn("task-notification result events", output.getvalue())


if __name__ == "__main__":
    unittest.main()
