from __future__ import annotations

import codecs
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify_direct_model_trace  # noqa: E402


EXPECTED_RESULT = "FABLE_ROUTE_OK"


def resolved_model(family: str = "fable") -> str:
    return "claude-" + family + "-5"


def valid_events(model: str | None = None) -> list[dict[str, object]]:
    return [
        {
            "type": "system",
            "subtype": "init",
            "model": model or resolved_model(),
            "session_id": "session-direct-1",
        },
        {
            "type": "assistant",
            "session_id": "session-direct-1",
            "message": {
                "role": "assistant",
                "model": model or resolved_model(),
                "content": [{"type": "text", "text": EXPECTED_RESULT}],
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": EXPECTED_RESULT,
            "session_id": "session-direct-1",
        },
    ]


def jsonl(events: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(event) for event in events) + "\n"


class VerifyDirectModelTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "trace.jsonl"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def verify(
        self,
        *,
        model: str = "fable",
        result: str = EXPECTED_RESULT,
    ) -> tuple[list[str], str | None, int]:
        return verify_direct_model_trace.verify_trace(self.path, model, result)

    def write(self, events: list[dict[str, object]]) -> None:
        self.path.write_text(jsonl(events), encoding="utf-8")

    def test_minimal_direct_trace_passes_for_family(self) -> None:
        self.write(valid_events())
        errors, model, count = self.verify()
        self.assertEqual(errors, [])
        self.assertEqual(model, resolved_model())
        self.assertEqual(count, 3)

    def test_exact_model_id_passes_case_insensitively(self) -> None:
        self.write(valid_events())
        errors, model, _ = self.verify(model=resolved_model().upper())
        self.assertEqual(errors, [])
        self.assertEqual(model, resolved_model())

    def test_utf8_bom_and_utf16_bom_are_supported(self) -> None:
        payload = jsonl(valid_events())
        encodings = {
            "utf8-bom": codecs.BOM_UTF8 + payload.encode("utf-8"),
            "utf16-le": payload.encode("utf-16"),
            "utf16-be": codecs.BOM_UTF16_BE + payload.encode("utf-16-be"),
        }
        for name, encoded in encodings.items():
            with self.subTest(name=name):
                self.path.write_bytes(encoded)
                errors, model, count = self.verify()
                self.assertEqual(errors, [])
                self.assertEqual(model, resolved_model())
                self.assertEqual(count, 3)

    def test_malformed_json_and_invalid_unicode_fail_closed(self) -> None:
        self.path.write_text('{"type":"assistant"}\nnot-json\n', encoding="utf-8")
        errors, model, _ = self.verify()
        self.assertTrue(any("malformed JSON" in error for error in errors))
        self.assertIsNone(model)

        self.path.write_bytes(b"\x80\x81")
        errors, model, _ = self.verify()
        self.assertTrue(errors)
        self.assertIsNone(model)

    def test_every_event_requires_one_shared_session(self) -> None:
        events = valid_events()
        events[1]["session_id"] = "session-direct-2"
        self.write(events)
        errors, _, _ = self.verify()
        self.assertTrue(any("exactly one session_id" in error for error in errors))

        events = valid_events()
        del events[1]["session_id"]
        self.write(events)
        errors, _, _ = self.verify()
        self.assertTrue(any("has no non-empty session_id" in error for error in errors))

    def test_agent_tool_call_is_rejected(self) -> None:
        events = valid_events()
        events[1]["message"]["content"] = [
            {
                "type": "tool_use",
                "id": "agent-1",
                "name": "Agent",
                "input": {"subagent_type": "fable-planner"},
            }
        ]
        self.write(events)
        errors, _, _ = self.verify()
        self.assertTrue(any("Agent tool calls" in error for error in errors), errors)
        self.assertTrue(any("no tool_use blocks" in error for error in errors), errors)

    def test_non_agent_tool_use_is_rejected(self) -> None:
        events = valid_events()
        events[1]["message"]["content"] = [
            {"type": "tool_use", "id": "read-1", "name": "Read", "input": {}}
        ]
        self.write(events)
        errors, _, _ = self.verify()
        self.assertFalse(any("Agent tool calls" in error for error in errors), errors)
        self.assertTrue(any("no tool_use blocks" in error for error in errors), errors)

    def test_tool_results_and_server_tool_activity_are_rejected(self) -> None:
        for block_type, expected_error in (
            ("tool_result", "no tool_result blocks"),
            ("server_tool_use", "no tool_use blocks"),
            ("mcp_tool_result", "no tool_result blocks"),
        ):
            with self.subTest(block_type=block_type):
                events = valid_events()
                events.insert(
                    1,
                    {
                        "type": "user",
                        "session_id": "session-direct-1",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": block_type,
                                    "tool_use_id": "hidden-tool",
                                    "content": "hidden tool output",
                                }
                            ],
                        },
                    },
                )
                self.write(events)
                errors, _, _ = self.verify()
                self.assertTrue(
                    any(expected_error in error for error in errors), errors
                )

    def test_user_scoped_forged_tool_use_is_also_rejected(self) -> None:
        events = valid_events()
        events.insert(
            1,
            {
                "type": "user",
                "session_id": "session-direct-1",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "fake-agent",
                            "name": "Agent",
                            "input": {},
                        }
                    ],
                },
            },
        )
        self.write(events)
        errors, _, _ = self.verify()
        self.assertTrue(any("Agent tool calls" in error for error in errors), errors)

    def test_task_lifecycle_event_is_rejected_regardless_of_event_type(self) -> None:
        events = valid_events()
        events.insert(
            2,
            {
                "type": "system",
                "subtype": "task_started",
                "task_id": "task-1",
                "session_id": "session-direct-1",
            },
        )
        self.write(events)
        errors, _, _ = self.verify()
        self.assertTrue(any("no task_* lifecycle" in error for error in errors), errors)

    def test_subagent_scoped_events_are_rejected(self) -> None:
        mutations = (
            {"parent_tool_use_id": "agent-1"},
            {"subagent_type": "fable-planner"},
            {"origin": {"kind": "task-notification"}},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                events = valid_events()
                events[1].update(mutation)
                self.write(events)
                errors, _, _ = self.verify()
                self.assertTrue(
                    any("subagent-scoped events" in error for error in errors), errors
                )

    def test_system_init_model_is_not_assistant_evidence(self) -> None:
        events = valid_events()
        del events[1]["message"]["model"]
        self.write(events)
        errors, model, _ = self.verify()
        self.assertTrue(
            any("no non-empty assistant message.model" in error for error in errors),
            errors,
        )
        self.assertIsNone(model)

    def test_malformed_assistant_message_is_rejected(self) -> None:
        events = valid_events()
        events[1]["message"]["role"] = "user"
        self.write(events)
        errors, model, _ = self.verify()
        self.assertTrue(any("not a well-formed assistant" in error for error in errors))
        self.assertIsNone(model)

    def test_multiple_assistant_events_pass_when_model_is_consistent(self) -> None:
        events = valid_events()
        thinking = json.loads(json.dumps(events[1]))
        thinking["message"]["content"] = [
            {"type": "thinking", "thinking": "Direct preflight."}
        ]
        events.insert(1, thinking)
        self.write(events)
        errors, model, _ = self.verify()
        self.assertEqual(errors, [])
        self.assertEqual(model, resolved_model())

    def test_different_assistant_models_are_ambiguous(self) -> None:
        events = valid_events()
        second = json.loads(json.dumps(events[1]))
        second["message"]["model"] = resolved_model("opus")
        events.insert(2, second)
        self.write(events)
        errors, model, _ = self.verify()
        self.assertTrue(any("ambiguous assistant model evidence" in error for error in errors))
        self.assertIsNone(model)

    def test_wrong_model_family_and_exact_model_are_rejected(self) -> None:
        self.write(valid_events(model=resolved_model("opus")))
        errors, _, _ = self.verify(model="fable")
        self.assertTrue(any("does not match" in error for error in errors))

        self.write(valid_events())
        errors, _, _ = self.verify(model=resolved_model() + "-20260701")
        self.assertTrue(any("does not match" in error for error in errors))

    def test_forged_model_without_supported_claude_prefix_is_rejected(self) -> None:
        self.write(valid_events(model="definitely-fable"))
        errors, _, _ = self.verify(model="definitely-fable")
        self.assertTrue(any("no unambiguous known family" in error for error in errors))

    def test_exactly_one_result_is_required(self) -> None:
        events = valid_events()[:-1]
        self.write(events)
        errors, _, _ = self.verify()
        self.assertTrue(any("exactly one final result" in error for error in errors))

        events = valid_events()
        events.append(dict(events[-1]))
        self.write(events)
        errors, _, _ = self.verify()
        self.assertTrue(any("exactly one final result" in error for error in errors))

    def test_result_must_be_unambiguous_success(self) -> None:
        mutations = (
            ("subtype", "error", "subtype is not 'success'"),
            ("is_error", True, "is_error is not exactly false"),
            ("is_error", "false", "is_error is not exactly false"),
        )
        for key, value, expected_error in mutations:
            with self.subTest(key=key, value=value):
                events = valid_events()
                events[-1][key] = value
                self.write(events)
                errors, _, _ = self.verify()
                self.assertTrue(
                    any(expected_error in error for error in errors), errors
                )

    def test_result_text_match_is_exact_and_type_safe(self) -> None:
        for value in ("fable_route_ok", EXPECTED_RESULT + "\n", None, 1):
            with self.subTest(value=value):
                events = valid_events()
                events[-1]["result"] = value
                self.write(events)
                errors, _, _ = self.verify()
                self.assertTrue(
                    any("final result text" in error for error in errors), errors
                )

    def test_empty_expected_and_result_text_are_rejected(self) -> None:
        events = valid_events()
        events[1]["message"]["content"][0]["text"] = ""
        events[2]["result"] = ""
        self.write(events)
        errors, _, _ = self.verify(result="")
        self.assertTrue(any("expected result must be" in error for error in errors))
        self.assertTrue(any("final result text is empty" in error for error in errors))

    def test_assistant_text_must_match_expected_sentinel(self) -> None:
        events = valid_events()
        events[1]["message"]["content"][0]["text"] = "CONTRADICTORY_TEXT"
        self.write(events)
        errors, _, _ = self.verify()
        self.assertTrue(
            any("assistant text does not exactly match" in error for error in errors),
            errors,
        )

    def test_result_must_follow_assistant_evidence(self) -> None:
        events = valid_events()
        events[1], events[2] = events[2], events[1]
        self.write(events)
        errors, _, _ = self.verify()
        self.assertTrue(any("appears before assistant" in error for error in errors))

    def test_cli_reports_pass_and_observed_evidence_limitation(self) -> None:
        self.write(valid_events())
        output = io.StringIO()
        with redirect_stdout(output):
            result = verify_direct_model_trace.main(
                [
                    str(self.path),
                    "--expected-model",
                    "fable",
                    "--expected-result",
                    EXPECTED_RESULT,
                ]
            )
        rendered = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("DIRECT TRACE PASS", rendered)
        self.assertIn("observed direct assistant message.model", rendered)
        self.assertIn("LIMITATION", rendered)
        self.assertIn("not cryptographic proof", rendered)

    def test_isolated_cli_can_import_sibling_verifier(self) -> None:
        self.write(valid_events())
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                str(SCRIPTS / "verify_direct_model_trace.py"),
                str(self.path),
                "--expected-model",
                "fable",
                "--expected-result",
                EXPECTED_RESULT,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("DIRECT TRACE PASS", completed.stdout)

    def test_cli_reports_fail_and_observed_evidence_limitation(self) -> None:
        self.write(valid_events())
        output = io.StringIO()
        with redirect_stdout(output):
            result = verify_direct_model_trace.main(
                [
                    str(self.path),
                    "--expected-model",
                    "opus",
                    "--expected-result",
                    EXPECTED_RESULT,
                ]
            )
        rendered = output.getvalue()
        self.assertEqual(result, 1)
        self.assertIn("DIRECT TRACE FAIL", rendered)
        self.assertIn("LIMITATION", rendered)
        self.assertIn("not cryptographic proof", rendered)


if __name__ == "__main__":
    unittest.main()
