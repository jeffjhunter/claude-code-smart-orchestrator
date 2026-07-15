#!/usr/bin/env python3
"""Fail-closed static validation for the public Claude Code starter kit."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver


ROOT = Path(__file__).resolve().parents[1]
AGENTS_REL = Path(".claude") / "agents"
ALLOWED_METADATA_KEYS = frozenset(
    {"name", "description", "tools", "model", "effort", "permissionMode"}
)
REQUIRED_DOCS = (
    "CLAUDE.md",
    "MODEL-POLICY.md",
    "ROUTING-MATRIX.md",
    "SETUP.md",
    "TEST-PROMPTS.md",
)

AGENT_PROFILES: dict[str, dict[str, Any]] = {
    ".claude/agents/fable-planner.md": {
        "name": "fable-planner",
        "description": "Produces long-horizon plans for broad goals that span multiple phases, decision points, or operating scenarios. Use only when the user explicitly requests Fable or invokes this agent; otherwise use the Opus architect.",
        "tools": ("Read", "Glob", "Grep"),
        "model": "fable",
        "effort": "xhigh",
        "permissionMode": "plan",
        "body_sha256": "02c89f59699b0159ed72002a444311e952bd697e9986e98655820914e97b82da",
    },
    ".claude/agents/architect.md": {
        "name": "architect",
        "description": "Designs implementation plans, boundaries, interfaces, and dependency order for multi-file or high-consequence work. Use before implementation when the path is not obvious and the cost of a design error justifies Opus reasoning.",
        "tools": ("Read", "Glob", "Grep"),
        "model": "opus",
        "effort": "high",
        "permissionMode": "plan",
        "body_sha256": "76b21578bbef9b7a723f3eb6856c2bb9cbd02fe6a15c446d4b740e62248673f3",
    },
    ".claude/agents/deep-reasoner.md": {
        "name": "deep-reasoner",
        "description": "Investigates difficult root causes, algorithms, security-sensitive decisions, and ambiguous failures. Use only when routine analysis is insufficient and the consequence or uncertainty justifies Opus with xhigh reasoning effort.",
        "tools": ("Read", "Glob", "Grep"),
        "model": "opus",
        "effort": "xhigh",
        "permissionMode": "plan",
        "body_sha256": "ff95120f8e39fd48c185dbe5d8174647987727637087bf39e5c5607fb64d5d33",
    },
    ".claude/agents/fast-worker.md": {
        "name": "fast-worker",
        "description": "Implements clear, bounded, low-consequence changes after requirements and acceptance criteria are defined. Use Haiku for boilerplate, focused refactors, formatting, test updates, and routine code changes where speed and cost matter more than deep reasoning.",
        "tools": (
            "Read",
            "Glob",
            "Grep",
            "Edit",
            "Write",
            "Bash",
            "PowerShell",
        ),
        "model": "haiku",
        "effort": "low",
        "permissionMode": "default",
        "body_sha256": "7edd67e41bc2b56cd344c8e268340cd9076bdabf20e28f6860c8d31048ca1866",
    },
    ".claude/agents/qa-reviewer.md": {
        "name": "qa-reviewer",
        "description": "Independently verifies completed work against requirements, tests, security expectations, and scope. Use Sonnet with high effort after implementation when the consequences justify a stronger review. Non-editing, but verification commands may create artifacts.",
        "tools": ("Read", "Glob", "Grep", "Bash", "PowerShell"),
        "model": "sonnet",
        "effort": "high",
        "permissionMode": "default",
        "body_sha256": "aa771f2d774be810304c55b660839c797e1453dc033112e9b4f8518026cb1920",
    },
}

BODY_REQUIREMENTS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "fable-planner": (
        (
            "analysis-only no-modification/no-execution invariant",
            re.compile(
                r"no Edit, Write, or shell tools.*do not attempt to modify files or execute commands",
                re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "distinct long-horizon planning invariant",
            re.compile(
                r"long-horizon planning specialist.*do not replace the Opus `architect`",
                re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "explicit Fable opt-in invariant",
            re.compile(
                r"explicit opt-in route.*user requests Fable by name.*Do not treat a broad or strategic task alone as permission",
                re.IGNORECASE | re.DOTALL,
            ),
        ),
    ),
    "architect": (
        (
            "analysis-only no-modification/no-execution invariant",
            re.compile(
                r"no Edit, Write, or shell tools.*do not attempt to modify files or execute commands",
                re.IGNORECASE | re.DOTALL,
            ),
        ),
    ),
    "deep-reasoner": (
        (
            "analysis-only no-modification/no-execution invariant",
            re.compile(
                r"no Edit, Write, or shell tools.*do not attempt to modify files or execute commands",
                re.IGNORECASE | re.DOTALL,
            ),
        ),
    ),
    "fast-worker": (
        (
            "bounded allowed-path invariant",
            re.compile(r"only inside the explicitly allowed paths", re.IGNORECASE),
        ),
        (
            "block-on-ambiguity invariant",
            re.compile(
                r"stop without editing and report a blocker.*ambiguous",
                re.IGNORECASE | re.DOTALL,
            ),
        ),
    ),
    "qa-reviewer": (
        (
            "no intentional source-edit invariant",
            re.compile(r"must not intentionally change source files", re.IGNORECASE),
        ),
        (
            "exact supplied-command invariant",
            re.compile(
                r"run that command verbatim as your first shell command", re.IGNORECASE
            ),
        ),
        (
            "no command-variant retry invariant",
            re.compile(r"do not retry it with command variants", re.IGNORECASE),
        ),
    ),
}
NESTED_DELEGATION_REQUIREMENTS = (
    re.compile(r"nested delegation is prohibited", re.IGNORECASE),
    re.compile(r"do not invoke, create, or hand work to another agent", re.IGNORECASE),
)

TEXT_SUFFIXES = frozenset(
    {
        ".cfg",
        ".conf",
        ".css",
        ".csv",
        ".html",
        ".ini",
        ".js",
        ".json",
        ".jsonl",
        ".jsx",
        ".key",
        ".lock",
        ".md",
        ".pem",
        ".properties",
        ".ps1",
        ".py",
        ".rst",
        ".sh",
        ".toml",
        ".ts",
        ".tsv",
        ".tsx",
        ".txt",
        ".xml",
        ".svg",
        ".yaml",
        ".yml",
    }
)
IGNORED_DIRECTORY_NAMES = frozenset({".git", "__pycache__"})

VERSIONED_MODEL_PATTERNS = (
    re.compile(r"\bclaude-(?:opus|sonnet|haiku|fable)-\d", re.IGNORECASE),
    re.compile(r"\bclaude-\d+(?:[-.]\d+)*-(?:opus|sonnet|haiku|fable)\b", re.IGNORECASE),
    re.compile(
        r"\bclaude\s+\d+(?:[.-]\d+)*\s+(?:opus|sonnet|haiku|fable)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:opus|sonnet|haiku|fable)[\s_-]+\d+(?:[.-]\d+)*\b", re.IGNORECASE),
)
PRICING_PATTERN = re.compile(
    r"(?:\$\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:USD|dollars?))"
    r"\s*(?:/|per)\s*(?:1\s*)?(?:m(?:tok|\s*tokens?)?|million\s*(?:tokens?)?)\b",
    re.IGNORECASE,
)


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that treats every duplicate mapping key as invalid."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: MappingNode, deep: bool = False
) -> dict[Any, Any]:
    if not isinstance(node, MappingNode):
        raise ConstructorError(
            None, None, "expected a mapping node", getattr(node, "start_mark", None)
        )
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _read_utf8(path: Path, root: Path, errors: list[str]) -> str | None:
    label = _relative(path, root)
    if path.is_symlink():
        errors.append(f"{label}: symbolic links are not allowed")
        return None
    try:
        if not path.is_file():
            errors.append(f"{label}: expected a regular file")
            return None
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"{label}: is not valid UTF-8 text")
    except OSError as exc:
        errors.append(f"{label}: could not be read ({exc.__class__.__name__})")
    return None


def parse_agent(path: Path, root: Path, errors: list[str]) -> tuple[dict[Any, Any], str] | None:
    """Read one agent file without allowing malformed YAML to escape as a traceback."""

    label = _relative(path, root)
    text = _read_utf8(path, root, errors)
    if text is None:
        return None
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        errors.append(f"{label}: missing opening YAML delimiter")
        return None
    try:
        closing_index = lines.index("---", 1)
    except ValueError:
        errors.append(f"{label}: missing closing YAML delimiter")
        return None

    yaml_text = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :]).strip()
    try:
        metadata = yaml.load(yaml_text, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None) or exc.__class__.__name__
        errors.append(f"{label}: invalid YAML ({problem})")
        return None
    except (TypeError, ValueError) as exc:
        errors.append(f"{label}: invalid YAML structure ({exc.__class__.__name__})")
        return None

    if not isinstance(metadata, dict):
        errors.append(f"{label}: YAML frontmatter must be a mapping")
        return None
    return metadata, body


def _discover_claude_files(root: Path, errors: list[str]) -> list[Path]:
    claude = root / ".claude"
    if claude.is_symlink():
        errors.append(".claude: symbolic links are not allowed")
        return []
    if not claude.is_dir():
        errors.append(".claude: configuration directory is missing")
        return []
    try:
        return sorted(
            (
                path for path in claude.rglob("*") if path.is_file() or path.is_symlink()
            ),
            key=lambda item: _relative(item, root).casefold(),
        )
    except OSError as exc:
        errors.append(
            f".claude: could not enumerate files ({exc.__class__.__name__})"
        )
        return []


def _format_keys(keys: set[Any]) -> str:
    return ", ".join(sorted((repr(key) for key in keys), key=str.casefold))


def _validate_metadata(
    relative_path: str,
    metadata: dict[Any, Any],
    body: str,
    names: list[str],
    errors: list[str],
) -> None:
    keys = set(metadata)
    missing = ALLOWED_METADATA_KEYS - keys
    unknown = keys - ALLOWED_METADATA_KEYS
    if missing:
        errors.append(f"{relative_path}: missing metadata keys: {_format_keys(missing)}")
    if unknown:
        errors.append(f"{relative_path}: unsupported metadata keys: {_format_keys(unknown)}")

    name = metadata.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        errors.append(f"{relative_path}: name must be a lowercase kebab-case string")
    else:
        names.append(name)

    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{relative_path}: description must be a non-empty string")
    if not body:
        errors.append(f"{relative_path}: system prompt body must not be empty")
    else:
        for pattern in NESTED_DELEGATION_REQUIREMENTS:
            if not pattern.search(body):
                errors.append(
                    f"{relative_path}: body lacks the nested-delegation prohibition"
                )
                break
        if isinstance(name, str):
            for label, pattern in BODY_REQUIREMENTS.get(name, ()):
                if not pattern.search(body):
                    errors.append(f"{relative_path}: body lacks the {label}")

    tools = metadata.get("tools")
    if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
        errors.append(f"{relative_path}: tools must be a YAML block list of strings")
        tools_list: list[str] = []
    else:
        tools_list = tools
        if len(tools_list) != len(set(tools_list)):
            errors.append(f"{relative_path}: tools must not contain duplicates")
        for tool in tools_list:
            if tool == "Agent" or tool.startswith(("Agent(", "Task", "mcp__")):
                errors.append(f"{relative_path}: delegation and MCP tools are forbidden")

    for key in ("model", "effort", "permissionMode"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{relative_path}: {key} must be a non-empty string")

    profile = AGENT_PROFILES.get(relative_path)
    if profile is None:
        return
    if name != profile["name"]:
        errors.append(
            f"{relative_path}: name must be {profile['name']!r}, found {name!r}"
        )
    if description != profile["description"]:
        errors.append(f"{relative_path}: description differs from the exact bundled profile")
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if body_hash != profile["body_sha256"]:
        errors.append(f"{relative_path}: body differs from the exact bundled profile")
    expected_tools = list(profile["tools"])
    if tools_list != expected_tools:
        errors.append(
            f"{relative_path}: tools must exactly match the bundled profile {expected_tools!r}"
        )
    for key in ("model", "effort", "permissionMode"):
        if metadata.get(key) != profile[key]:
            errors.append(
                f"{relative_path}: {key} must be {profile[key]!r}, "
                f"found {metadata.get(key)!r}"
            )


def _is_text_artifact(path: Path) -> bool:
    if any(part in IGNORED_DIRECTORY_NAMES for part in path.parts):
        return False
    name = path.name.casefold()
    return (
        name == ".env"
        or name.startswith(".env.")
        or path.suffix.casefold() in TEXT_SUFFIXES
        or not path.suffix
    )


def _iter_text_artifacts(root: Path, errors: list[str]) -> list[Path]:
    try:
        return sorted(
            (
                path
                for path in root.rglob("*")
                if (path.is_file() or path.is_symlink()) and _is_text_artifact(path)
            ),
            key=lambda item: _relative(item, root).casefold(),
        )
    except OSError as exc:
        errors.append(f"starter: could not enumerate text artifacts ({exc.__class__.__name__})")
        return []


def _looks_like_placeholder(value: str) -> bool:
    stripped = value.strip().strip("'\"")
    lowered = stripped.casefold()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    if stripped.startswith(("$", "<", "{{")) or stripped.endswith((">", "}}")):
        return True
    placeholder_words = (
        "changeme",
        "dummy",
        "example",
        "fake",
        "not_a_real",
        "placeholder",
        "redacted",
        "replace_me",
        "sample",
        "test_only",
        "your_",
    )
    if any(word in normalized for word in placeholder_words):
        return True
    return bool(re.fullmatch(r"(?:x+|\.+)", lowered))


def find_secret_like_content(text: str) -> list[tuple[int, str]]:
    """Return line-numbered heuristic credential findings for UTF-8 text."""
    findings: list[tuple[int, str]] = []
    token_patterns = (
        ("Anthropic API credential", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
        (
            "OpenAI API credential",
            re.compile(r"\bsk-(?:(?:proj|svcacct)-)?[A-Za-z0-9_-]{20,}\b"),
        ),
        ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
        ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
        ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
        ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
        ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    )
    for label, pattern in token_patterns:
        for match in pattern.finditer(text):
            if not _looks_like_placeholder(match.group(0)):
                findings.append((text.count("\n", 0, match.start()) + 1, label))

    private_key_marker = "-" * 5 + "BEGIN "
    private_key_pattern = re.compile(
        re.escape(private_key_marker)
        + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY"
        + re.escape("-" * 5)
    )
    for match in private_key_pattern.finditer(text):
        findings.append((text.count("\n", 0, match.start()) + 1, "private key material"))

    assignment_pattern = re.compile(
        r"\b(?:[A-Za-z][A-Za-z0-9]*[_-])*"
        r"(?:api[_-]?key|access[_-]?key|access[_-]?token|auth[_-]?token|"
        r"client[_-]?secret|password|secret(?:[_-]?access[_-]?key)?)\b"
        r"['\"]?\s*[:=]\s*['\"]?([^\s'\"#]{8,})",
        re.IGNORECASE,
    )
    for match in assignment_pattern.finditer(text):
        if not _looks_like_placeholder(match.group(1)):
            findings.append((text.count("\n", 0, match.start()) + 1, "assigned credential"))
    return findings


def _scan_text_artifacts(root: Path, errors: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in _iter_text_artifacts(root, errors):
        relative_path = _relative(path, root)
        if path.name.casefold() in {".mcp.json", "mcp.json"}:
            errors.append(f"{relative_path}: MCP configuration is forbidden")
        text = _read_utf8(path, root, errors)
        if text is None:
            continue
        texts[relative_path] = text
        for line, label in find_secret_like_content(text):
            errors.append(f"{relative_path}:{line}: contains possible {label}")
        for pattern in VERSIONED_MODEL_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                errors.append(
                    f"{relative_path}:{line}: contains a versioned model identifier"
                )
                break
        pricing_match = PRICING_PATTERN.search(text)
        if pricing_match:
            line = text.count("\n", 0, pricing_match.start()) + 1
            errors.append(f"{relative_path}:{line}: contains a hard-coded model price")
    return texts


def validate(root: Path = ROOT) -> list[str]:
    """Return deterministic human-readable errors; an empty list means static pass."""

    root = Path(root).resolve()
    errors: list[str] = []
    if not root.is_dir():
        return ["starter: validation root is not a directory"]

    for document in REQUIRED_DOCS:
        path = root / document
        if path.is_symlink() or not path.is_file():
            errors.append(f"{document}: required documentation file is missing")

    claude_files = _discover_claude_files(root, errors)
    discovered = {_relative(path, root) for path in claude_files}
    expected = set(AGENT_PROFILES)
    for missing in sorted(expected - discovered):
        errors.append(f"{missing}: expected agent file is missing")
    for extra in sorted(discovered - expected):
        errors.append(f"{extra}: unexpected .claude payload")

    names: list[str] = []
    agent_files = [
        path
        for path in claude_files
        if _relative(path, root).startswith(f"{AGENTS_REL.as_posix()}/")
        and path.suffix.casefold() == ".md"
    ]
    for path in agent_files:
        relative_path = _relative(path, root)
        parsed = parse_agent(path, root, errors)
        if parsed is None:
            continue
        metadata, body = parsed
        _validate_metadata(relative_path, metadata, body, names, errors)

    duplicates = sorted({name for name in names if names.count(name) > 1})
    for name in duplicates:
        errors.append(f"duplicate agent name: {name!r}")
    expected_names = {profile["name"] for profile in AGENT_PROFILES.values()}
    if set(names) != expected_names:
        errors.append(
            "agent names differ from expected: "
            + ", ".join(sorted(set(names)))
        )

    texts = _scan_text_artifacts(root, errors)
    claude = texts.get("CLAUDE.md")
    if claude is not None:
        for name in sorted(expected_names):
            if f"`{name}`" not in claude:
                errors.append(f"CLAUDE.md: does not reference `{name}`")
        if not re.search(r"(?:do not|never).{0,100}delegat", claude, re.IGNORECASE | re.DOTALL):
            errors.append("CLAUDE.md: lacks an explicit no-recursion instruction")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="starter directory to validate (defaults to this script's parent starter)",
    )
    args = parser.parse_args(argv)
    try:
        errors = validate(args.root)
    except Exception as exc:  # Last-resort fail-closed boundary for hostile filesystems.
        print("STATIC STRUCTURE FAIL")
        print(f"- validator could not complete safely ({exc.__class__.__name__})")
        return 1

    if errors:
        print("STATIC STRUCTURE FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("STATIC STRUCTURE PASS")
    print("- exact recursive five-agent inventory verified")
    print("- strict YAML schema, tools, models, effort, and permission modes verified")
    print("- obvious secrets, versioned model identifiers, and pricing claims not found")
    print("- required orchestration documentation is present and internally referenced")
    print("LIMITATIONS")
    print("- static validation does not prove runtime delegation or resolved model selection")
    print("- tool allowlists and permission modes are not an operating-system security sandbox")
    print("- heuristic secret scanning cannot guarantee that every credential is detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
