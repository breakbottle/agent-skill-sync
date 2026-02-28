#!/usr/bin/env python3
"""Create and install a skill across multiple IDE agent directories."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def slugify(name: str) -> str:
    value = name.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        raise ValueError("Skill name resolved to an empty slug.")
    return value


def read_content(args: argparse.Namespace) -> tuple[str, Path | None]:
    if args.source:
        source_path = Path(args.source).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Input file not found: {source_path}")
        return source_path.read_text(encoding="utf-8"), source_path

    if args.text is not None:
        return args.text, None

    if args.stdin or not sys.stdin.isatty():
        return sys.stdin.read(), None

    raise ValueError("No input provided. Pass a .md file, --text, or pipe content to stdin.")


def has_frontmatter_with_required_fields(content: str) -> bool:
    if not content.startswith("---\n"):
        return False

    lines = content.splitlines()
    closing_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_idx = idx
            break

    if closing_idx is None:
        return False

    frontmatter = "\n".join(lines[1:closing_idx])
    has_name = re.search(r"^name\s*:\s*.+$", frontmatter, flags=re.MULTILINE) is not None
    has_description = re.search(r"^description\s*:\s*.+$", frontmatter, flags=re.MULTILINE) is not None
    return has_name and has_description


def ensure_skill_markdown(content: str, skill_name: str, description: str) -> str:
    body = content.strip()
    if has_frontmatter_with_required_fields(body):
        return body + "\n"

    return (
        "---\n"
        f"name: {skill_name}\n"
        f"description: {description}\n"
        "---\n\n"
        f"{body}\n"
    )


def copy_scripts(scripts_dir: Path, target_dir: Path) -> None:
    target_scripts = target_dir / "scripts"
    if target_scripts.exists():
        shutil.rmtree(target_scripts)
    shutil.copytree(scripts_dir, target_scripts)


def write_skill(
    install_root: Path,
    skill_name: str,
    skill_md: str,
    scripts_dir: Path | None,
) -> Path:
    destination = install_root / skill_name
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "SKILL.md").write_text(skill_md, encoding="utf-8")

    if scripts_dir and scripts_dir.is_dir():
        copy_scripts(scripts_dir, destination)

    return destination


def copy_skill_folder(
    source_skill_dir: Path,
    install_root: Path,
    skill_name: str,
) -> Path:
    destination = install_root / skill_name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source_skill_dir, destination)
    return destination


def is_git_repo(path: Path) -> tuple[bool, Path | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, None

    return True, Path(result.stdout.strip())


def normalize_ignore_entry(entry: str) -> str:
    return entry.strip().rstrip("/")


def sync_gitignore_for_skill_project(project_dir: Path) -> None:
    is_repo, repo_root = is_git_repo(project_dir)
    if not is_repo or repo_root is None:
        print(f"Gitignore sync skipped: not a git repository: {project_dir}")
        return

    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.is_file():
        print(f"Gitignore sync skipped: no .gitignore at {gitignore_path}")
        return

    raw_lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    existing = {normalize_ignore_entry(line) for line in raw_lines if line.strip() and not line.strip().startswith("#")}
    required = [".claude", ".codex", ".agent"]

    if not any(entry in existing for entry in required):
        print("Gitignore sync skipped: no existing IDE ignore entries found.")
        return

    missing = [entry for entry in required if entry not in existing]
    if not missing:
        print("Gitignore sync: all IDE entries already present.")
        return

    append_lines = []
    if raw_lines and raw_lines[-1].strip():
        append_lines.append("")
    append_lines.append("# IDE skill folders")
    append_lines.extend(f"{entry}/" for entry in missing)
    with gitignore_path.open("a", encoding="utf-8") as file:
        file.write("\n".join(append_lines) + "\n")

    print(f"Gitignore sync: added entries to {gitignore_path}: {', '.join(f'{m}/' for m in missing)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create/install a skill in Claude, Codex, and Gemini Antigravity skill folders."
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="Path to markdown/text file containing skill instructions.",
    )
    parser.add_argument(
        "--new",
        help="Path to an existing skill folder to copy/install into target IDE folders.",
    )
    parser.add_argument(
        "--text",
        help="Inline instruction text to convert into SKILL.md content.",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read instruction text from stdin.",
    )
    parser.add_argument(
        "--name",
        help="Skill name (slug). Defaults to input file stem when source file is used.",
    )
    parser.add_argument(
        "--description",
        default="User-provided workflow skill.",
        help="Frontmatter description when input is missing required metadata.",
    )
    parser.add_argument(
        "--scripts",
        help="Optional scripts directory to copy into each installed skill.",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=["claude", "codex", "gemini"],
        default=["claude", "codex", "gemini"],
        help="Install targets. Defaults to all.",
    )
    parser.add_argument(
        "--home",
        help="Override home directory for installs (default: current user's home).",
    )
    parser.add_argument(
        "--project-dir",
        help=(
            "Project root for instance install targets "
            "(writes to <project>/.claude/skills, <project>/.codex/skills, "
            "and <project>/.agent/skills for Antigravity)."
        ),
    )
    parser.add_argument(
        "--scope",
        choices=["global", "project", "both"],
        default="global",
        help="Install scope. If --project-dir is set, use 'both' to install globally and per-project.",
    )
    parser.add_argument(
        "--sync-gitignore",
        action="store_true",
        help=(
            "When using project scope, sync repo-root .gitignore with .claude/, .codex/, and .agent/ "
            "only if .gitignore already exists and at least one IDE entry already exists."
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    provided = 0
    if args.source:
        provided += 1
    if args.text is not None:
        provided += 1
    if args.stdin:
        provided += 1
    if args.new:
        provided += 1
    if provided > 1:
        print("Error: use exactly one input mode: source file, --text, --stdin, or --new.", file=sys.stderr)
        return 1

    source_path = None
    source_skill_dir = None
    content = None
    skill_md = None
    scripts_dir = None

    if args.new:
        source_skill_dir = Path(args.new).expanduser().resolve()
        if not source_skill_dir.is_dir():
            print(f"Error: skill folder not found: {source_skill_dir}", file=sys.stderr)
            return 1
        if not (source_skill_dir / "SKILL.md").is_file():
            print(f"Error: SKILL.md not found in skill folder: {source_skill_dir}", file=sys.stderr)
            return 1
        if args.scripts:
            print("Error: --scripts cannot be used with --new mode.", file=sys.stderr)
            return 1
        raw_name = args.name if args.name else source_skill_dir.name
    else:
        try:
            content, source_path = read_content(args)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        raw_name = args.name
        if raw_name is None:
            if source_path is not None:
                raw_name = source_path.stem
            else:
                print("Error: --name is required when using --text or --stdin.", file=sys.stderr)
                return 1

        if args.scripts:
            scripts_dir = Path(args.scripts).expanduser().resolve()
            if not scripts_dir.is_dir():
                print(f"Error: scripts directory not found: {scripts_dir}", file=sys.stderr)
                return 1
        elif source_path:
            sibling_scripts = source_path.parent / "scripts"
            if sibling_scripts.is_dir():
                scripts_dir = sibling_scripts.resolve()

    try:
        skill_name = slugify(raw_name)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if content is not None:
        skill_md = ensure_skill_markdown(content, skill_name, args.description)

    home_dir = Path(args.home).expanduser().resolve() if args.home else Path.home()
    global_roots = {
        "claude": home_dir / ".claude" / "skills",
        "codex": home_dir / ".codex" / "skills",
        "gemini": home_dir / ".gemini" / "antigravity" / "skills",
    }
    project_roots = None
    if args.project_dir:
        project_dir = Path(args.project_dir).expanduser().resolve()
        project_roots = {
            "claude": project_dir / ".claude" / "skills",
            "codex": project_dir / ".codex" / "skills",
            # Antigravity project-local skills convention.
            "gemini": project_dir / ".agent" / "skills",
        }
    elif args.scope in ("project", "both"):
        print("Error: --project-dir is required when --scope is 'project' or 'both'.", file=sys.stderr)
        return 1

    if args.sync_gitignore and args.scope not in ("project", "both"):
        print("Error: --sync-gitignore requires --scope project or --scope both.", file=sys.stderr)
        return 1

    print(f"Building skill: {skill_name}")
    for target in args.only:
        if args.scope in ("global", "both"):
            if source_skill_dir:
                global_dest = copy_skill_folder(source_skill_dir, global_roots[target], skill_name)
            else:
                global_dest = write_skill(global_roots[target], skill_name, skill_md, scripts_dir)
            print(f"Installed to {target} (global): {global_dest}")
        if args.scope in ("project", "both"):
            if source_skill_dir:
                project_dest = copy_skill_folder(source_skill_dir, project_roots[target], skill_name)
            else:
                project_dest = write_skill(project_roots[target], skill_name, skill_md, scripts_dir)
            print(f"Installed to {target} (project): {project_dest}")

    if args.sync_gitignore and project_roots:
        sync_gitignore_for_skill_project(project_dir)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
