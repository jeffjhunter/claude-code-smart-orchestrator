#!/usr/bin/env python3
from pathlib import Path
import re
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / '.claude' / 'agents'
REQUIRED = {'name', 'description'}
EXPECTED = {'architect', 'deep-reasoner', 'fast-worker', 'qa-reviewer'}
EXPECTED_TOOLS = {
    'architect': {'Read', 'Glob', 'Grep'},
    'deep-reasoner': {'Read', 'Glob', 'Grep'},
    'fast-worker': {'Read', 'Glob', 'Grep', 'Edit', 'Write', 'Bash'},
    'qa-reviewer': {'Read', 'Glob', 'Grep', 'Bash'},
}
EXPECTED_MODES = {
    'architect': 'plan',
    'deep-reasoner': 'plan',
    'fast-worker': 'default',
    'qa-reviewer': 'plan',
}
DISALLOWED_PUBLIC_PATTERNS = [
    (r'\b(?:opus|sonnet|haiku|fable)[ -]?\d', 'versioned model identifier'),
    (r'\$\d+(?:\.\d+)?\s*(?:/|per)\s*(?:million|m\b)', 'hard-coded model pricing'),
    (r'(?i)api[_ -]?key\s*[:=]\s*\S+', 'possible API key'),
]

def parse_agent(path: Path):
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        raise ValueError('missing opening YAML delimiter')
    parts = text.split('---\n', 2)
    if len(parts) != 3:
        raise ValueError('missing closing YAML delimiter')
    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return meta, body, text

def main():
    errors = []
    names = []
    files = sorted(AGENTS.glob('*.md'))
    if len(files) != 4:
        errors.append(f'expected 4 agent files, found {len(files)}')
    for path in files:
        try:
            meta, body, text = parse_agent(path)
        except Exception as exc:
            errors.append(f'{path.name}: {exc}')
            continue
        missing = REQUIRED - set(meta)
        if missing:
            errors.append(f'{path.name}: missing {sorted(missing)}')
        name = meta.get('name', '')
        names.append(name)
        if not re.fullmatch(r'[a-z][a-z0-9-]*', name):
            errors.append(f'{path.name}: invalid name {name!r}')
        if path.stem != name:
            errors.append(f'{path.name}: filename should match name {name!r}')
        if not str(meta.get('description', '')).strip():
            errors.append(f'{path.name}: empty description')
        if not body:
            errors.append(f'{path.name}: empty system prompt body')
        tools = meta.get('tools', [])
        if not isinstance(tools, list):
            errors.append(f'{path.name}: tools must use a YAML block list')
            tools = []
        if 'Agent' in tools or any(str(x).startswith(('Agent(', 'Task(', 'Task')) for x in tools):
            errors.append(f'{path.name}: nested delegation tool is not allowed')
        if name in EXPECTED_TOOLS and set(tools) != EXPECTED_TOOLS[name]:
            errors.append(f'{path.name}: tools differ from safe public profile: {tools}')
        if name in EXPECTED_MODES and meta.get('permissionMode') != EXPECTED_MODES[name]:
            errors.append(f'{path.name}: permissionMode must be {EXPECTED_MODES[name]!r}')
        if meta.get('model') not in (None, 'inherit'):
            errors.append(f'{path.name}: public kit must use model: inherit or omit model')
    if set(names) != EXPECTED:
        errors.append(f'agent names differ from expected: {sorted(names)}')
    if len(names) != len(set(names)):
        errors.append('duplicate agent names')

    public_files = [ROOT / 'CLAUDE.md', ROOT / 'ROUTING-MATRIX.md', ROOT / 'SETUP.md', ROOT / 'TEST-PROMPTS.md', *files]
    for path in public_files:
        text = path.read_text(encoding='utf-8')
        for pattern, label in DISALLOWED_PUBLIC_PATTERNS:
            if re.search(pattern, text, flags=re.I):
                errors.append(f'{path.name}: contains {label}')

    claude = (ROOT / 'CLAUDE.md').read_text(encoding='utf-8')
    for name in EXPECTED:
        if f'`{name}`' not in claude:
            errors.append(f'CLAUDE.md does not reference {name}')
    if 'Do not ask agents to delegate further' not in claude:
        errors.append('CLAUDE.md lacks no-recursion instruction')

    if errors:
        print('FAIL')
        for error in errors:
            print(f'- {error}')
        return 1
    print('PASS')
    print(f'- parsed {len(files)} valid agent files')
    print(f'- unique agents: {", ".join(sorted(names))}')
    print('- nested delegation disabled by tool allowlists')
    print('- canonical YAML tool lists and safe permission modes verified')
    print('- Bash omitted from Architect and Deep Reasoner; QA keeps Bash only for approved checks')
    print('- public starter contains no versioned model IDs, pricing, or obvious API keys')
    print('- CLAUDE.md references every agent and owns orchestration')
    return 0

if __name__ == '__main__':
    sys.exit(main())
