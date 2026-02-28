# agent-skill-sync

Cross-IDE skill creator and installer for Claude, Codex, and Gemini Antigravity.

## Usage

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py [source] [options]
```

## Input modes

From Markdown file:

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py /path/to/instructions.md
```

From inline text:

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py \
  --text "Your skill instructions..." \
  --name my-skill
```

From stdin/pipe (agent -> skill-create):

```bash
agent "write me a deploy skill" | \
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py --stdin --name deploy-skill
```

Copy an existing skill folder (for example from Claude) to all IDEs:

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py \
  --new ~/.claude/skills/newskill
```

Copy and rename while installing:

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py \
  --new ~/.claude/skills/newskill \
  --name shared-newskill
```

Install only to Codex:

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py ./my-skill.md --only codex
```

## Install scopes

Global install (default):

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py ./my-skill.md
```

Project install only:

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py ./my-skill.md \
  --project-dir /path/to/project \
  --scope project
```

Global + project install:

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py ./my-skill.md \
  --project-dir /path/to/project \
  --scope both
```

Project install + guarded gitignore sync:

```bash
/Users/cbot/dev/tools/agent-skill-sync/skill-create.py ./my-skill.md \
  --project-dir /path/to/project \
  --scope project \
  --sync-gitignore
```

Project install writes to:

- `/path/to/project/.claude/skills/<skill-name>`
- `/path/to/project/.codex/skills/<skill-name>`
- `/path/to/project/.agent/skills/<skill-name>` (Antigravity)

## Optional flags

- `--name <skill-name>`: required for `--text` and `--stdin`
- `--description "..."`: frontmatter description if input has no metadata
- `--scripts <dir>`: copy scripts into each installed skill
- `--only claude codex gemini`: restrict install targets
- `--home <dir>`: override home for global install paths
- `--sync-gitignore`: for project installs, add missing `.claude/`, `.codex/`, `.agent/` only when repo root has `.gitignore` and at least one IDE entry already exists

## Make callable from bash

Add an alias to your shell config:

```bash
alias skill-create='/Users/cbot/dev/tools/agent-skill-sync/skill-create.py'
```

Then reload shell and run:

```bash
skill-create /path/to/instructions.md
```

## TODO

- Add remote registry publish flow for GitHub `breakbottle`.
