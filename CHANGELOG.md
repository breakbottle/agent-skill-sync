# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-03-01

### Added
- Initial public release of `agent-skill-sync`.
- CLI tool (`skill-create.py`) to create and install skills for:
  - Claude (`~/.claude/skills`)
  - Codex (`~/.codex/skills`)
  - Gemini Antigravity (`~/.gemini/antigravity/skills`)
- Multiple input modes:
  - source file
  - inline text (`--text`)
  - stdin (`--stdin`)
  - copy existing skill folder (`--new`)
- Skill name normalization via slug generation.
- Automatic frontmatter support for `name` and `description` when missing.
- Install targeting controls with `--only`.
- Install scope controls with `--scope` (`global`, `project`, `both`) and `--project-dir`.
- Project-local Antigravity install support at `.agent/skills`.
- Optional scripts directory copy support (`--scripts`).
- Guarded `.gitignore` sync for project installs (`--sync-gitignore`).
