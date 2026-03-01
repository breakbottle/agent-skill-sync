# agent-skill-sync

Cross-IDE skill creator and installer for Claude, Codex, and Gemini Antigravity.

## Problem Statement

Builders using AI coding tools lose momentum when skills are fragmented across IDE ecosystems and token limits force tool switching mid-flow. Manually recreating or copying skills across platforms is repetitive, inconsistent, and slows shipping.

## The Story (Why This Exists)

AI-assisted coding is moving fast. We now have Claude Code, Google Gemini Antigravity, and OpenAI Codex. They are all powerful, and they are all bounded by tokens.

Many of us play the token game while trying to stay IDE-agnostic and keep momentum. I hit this directly: I was coding in Codex, ran out of tokens, and did not want to stop shipping. I had access to other tools, so I started chaining IDEs to keep moving.

That challenge created `agent-skill-sync`: one simple way to create, copy, and sync skills across platforms, globally or per project, so your workflow keeps going even when one tool slows you down.

If this resonates, join in. More platforms are coming, and collaborative maintenance will help keep this practical and future-ready.

## Short Example

You build a deployment skill in one assistant and want it available everywhere.
Instead of manually recreating it in three places, run one command and install it to Claude, Codex, and Gemini skill folders in a project.

Result: less setup thrash, better coding momentum.

## Requirements

- Python 3.10+
- macOS/Linux shell environment
- Write access to your home directory or target project directory

## Installation

Clone the repository and make the script executable:

```bash
git clone https://github.com/<your-username>/agent-skill-sync.git
cd agent-skill-sync
chmod +x skill-create.py
```

Optional shell alias:

```bash
alias skill-create="$PWD/skill-create.py"
```

## Usage

```bash
./skill-create.py [source] [options]
```

## Use This Tool Two Ways

### 1) Direct CLI Use

Use CLI when you want explicit control from terminal scripts or manual workflows.

### Input Modes

From Markdown file:

```bash
./skill-create.py /path/to/instructions.md
```

From inline text:

```bash
./skill-create.py \
  --text "Your skill instructions..." \
  --name my-skill
```

From stdin/pipe:

```bash
agent "write me a deploy skill" | \
./skill-create.py --stdin --name deploy-skill
```

Copy an existing skill folder to selected IDEs:

```bash
./skill-create.py --new ~/.claude/skills/newskill
```

Copy and rename while installing:

```bash
./skill-create.py \
  --new ~/.claude/skills/newskill \
  --name shared-newskill
```

Install only to one IDE:

```bash
./skill-create.py ./my-skill.md --only codex
```

### Install Scopes

Global install (default):

```bash
./skill-create.py ./my-skill.md
```

Project install only:

```bash
./skill-create.py ./my-skill.md \
  --project-dir /path/to/project \
  --scope project
```

Global + project install:

```bash
./skill-create.py ./my-skill.md \
  --project-dir /path/to/project \
  --scope both
```

Project install + guarded gitignore sync:

```bash
./skill-create.py ./my-skill.md \
  --project-dir /path/to/project \
  --scope project \
  --sync-gitignore
```

Project installs write to:

- `/path/to/project/.claude/skills/<skill-name>`
- `/path/to/project/.codex/skills/<skill-name>`
- `/path/to/project/.agent/skills/<skill-name>` (Antigravity)

### Useful Options

- `--name <skill-name>`: required for `--text` and `--stdin`
- `--description "..."`: frontmatter description if metadata is missing
- `--scripts <dir>`: copy scripts into each installed skill
- `--only claude codex gemini`: restrict install targets
- `--home <dir>`: override home directory for global installs
- `--sync-gitignore`: add IDE folders to `.gitignore` only under guarded conditions

### Full Option Reference

```text
usage: skill-create.py [-h] [--new NEW] [--text TEXT] [--stdin] [--name NAME]
                       [--description DESCRIPTION] [--scripts SCRIPTS]
                       [--only {claude,codex,gemini} [{claude,codex,gemini} ...]]
                       [--home HOME] [--project-dir PROJECT_DIR]
                       [--scope {global,project,both}] [--sync-gitignore]
                       [source]
```

### 2) Use Through an AI Agent

Use this when you want an assistant (Codex/Claude/Gemini agent) to handle skill setup for you.

Flow:
1. Give the agent access to this repository folder.
2. Ask it to run `skill-create.py` with your chosen input mode and target params.
3. Provide either a skill file path, inline prompt text, or stdin content.

Prompt examples:

```text
Use /path/to/agent-skill-sync and create a new skill from ./my-skill.md.
Install it to claude codex gemini for project /path/to/repo only.
```

```text
Use /path/to/agent-skill-sync and create a skill named api-release from this prompt text.
Install globally to codex only.
```

## Contributing

Contributions are welcome, especially for support of new AI coding platforms and cross-IDE skill conventions. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution workflow, bug reports, and feature requests.

## License

MIT. See [LICENSE](LICENSE).

## Roadmap

- Add Windows support (PowerShell examples + path handling).
- Add remote registry publish flow for GitHub `breakbottle`.
- Add support for additional AI IDE/platform skill directory conventions as they emerge.
- Add automated tests for input modes, scope behavior, and `.gitignore` sync guards.
- Add CI to run tests/lint on macOS, Linux, and Windows.
- Add `--dry-run` mode to preview install targets and file changes before writing.
