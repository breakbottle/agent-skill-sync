#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="$ROOT_DIR/skill-create.py"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

project_dir="$tmpdir/project"
home_dir="$tmpdir/home"
mkdir -p "$project_dir" "$home_dir"

sample_md="$tmpdir/sample.md"
cat > "$sample_md" <<'EOF'
---
name: sample-skill
description: sample skill for smoke testing
---

Do a useful thing.
EOF

echo "1. Verifying help and bytecode compilation"
python3 "$SCRIPT_PATH" --help >/dev/null
python3 -m py_compile "$SCRIPT_PATH"

echo "2. Verifying create"
python3 "$SCRIPT_PATH" create "$sample_md" \
  --home "$home_dir" \
  --project-dir "$project_dir" \
  --scope both \
  --only codex gemini >/dev/null

test -f "$home_dir/.codex/skills/sample-skill/SKILL.md"
test -f "$project_dir/.codex/skills/sample-skill/SKILL.md"
test -f "$home_dir/.gemini/antigravity/skills/sample-skill/SKILL.md"
test -f "$project_dir/.agent/skills/sample-skill/SKILL.md"

echo "3. Verifying inspect"
inspect_output="$(python3 "$SCRIPT_PATH" inspect --name sample-skill \
  --home "$home_dir" \
  --project-dir "$project_dir" \
  --scope both \
  --only codex gemini)"
printf '%s\n' "$inspect_output" | rg "present" >/dev/null

echo "4. Verifying list"
list_output="$(python3 "$SCRIPT_PATH" list \
  --home "$home_dir" \
  --project-dir "$project_dir" \
  --scope both \
  --only codex gemini)"
printf '%s\n' "$list_output" | rg "sample-skill" >/dev/null

echo "5. Verifying remove dry-run"
python3 "$SCRIPT_PATH" remove --name sample-skill \
  --home "$home_dir" \
  --project-dir "$project_dir" \
  --scope both \
  --only codex gemini \
  --dry-run >/dev/null

test -d "$home_dir/.codex/skills/sample-skill"

echo "6. Verifying remove"
python3 "$SCRIPT_PATH" remove --name sample-skill \
  --home "$home_dir" \
  --project-dir "$project_dir" \
  --scope both \
  --only codex gemini >/dev/null

test ! -d "$home_dir/.codex/skills/sample-skill"
test ! -d "$project_dir/.codex/skills/sample-skill"
test ! -d "$home_dir/.gemini/antigravity/skills/sample-skill"
test ! -d "$project_dir/.agent/skills/sample-skill"

echo "7. Verifying legacy mode"
legacy_md="$tmpdir/legacy.md"
printf '%s\n' 'simple skill body' > "$legacy_md"
legacy_output="$(python3 "$SCRIPT_PATH" "$legacy_md" --home "$home_dir" --only claude --dry-run)"
printf '%s\n' "$legacy_output" | rg "Would install to claude" >/dev/null

echo "Smoke test passed."
