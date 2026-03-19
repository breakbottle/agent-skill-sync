#!/usr/bin/env python3
"""Create, copy, inspect, list, and remove skills across IDE agent directories."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

TARGET_CHOICES = ("claude", "codex", "gemini")
SCOPE_CHOICES = ("global", "project", "both")


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


def extract_frontmatter_field(content: str, field: str) -> str | None:
    if not content.startswith("---\n"):
        return None

    lines = content.splitlines()
    closing_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_idx = idx
            break

    if closing_idx is None:
        return None

    frontmatter = "\n".join(lines[1:closing_idx])
    match = re.search(rf"^{re.escape(field)}\s*:\s*(.+)$", frontmatter, flags=re.MULTILINE)
    if match is None:
        return None
    return match.group(1).strip()


def copy_scripts(scripts_dir: Path, target_dir: Path, dry_run: bool = False) -> None:
    target_scripts = target_dir / "scripts"
    if dry_run:
        return
    if target_scripts.exists():
        shutil.rmtree(target_scripts)
    shutil.copytree(scripts_dir, target_scripts)


def write_skill(
    install_root: Path,
    skill_name: str,
    skill_md: str,
    scripts_dir: Path | None,
    dry_run: bool = False,
) -> Path:
    destination = install_root / skill_name
    if dry_run:
        return destination

    destination.mkdir(parents=True, exist_ok=True)
    (destination / "SKILL.md").write_text(skill_md, encoding="utf-8")

    if scripts_dir and scripts_dir.is_dir():
        copy_scripts(scripts_dir, destination, dry_run=dry_run)

    return destination


def copy_skill_folder(
    source_skill_dir: Path,
    install_root: Path,
    skill_name: str,
    dry_run: bool = False,
) -> Path:
    destination = install_root / skill_name
    if dry_run:
        return destination

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source_skill_dir, destination)
    return destination


def remove_skill_folder(destination: Path, dry_run: bool = False) -> bool:
    if not destination.exists():
        return False
    if dry_run:
        return True
    shutil.rmtree(destination)
    return True


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


def sync_gitignore_for_skill_project(project_dir: Path, dry_run: bool = False) -> None:
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

    if dry_run:
        print(f"Gitignore sync (dry-run): would add entries to {gitignore_path}: {', '.join(f'{m}/' for m in missing)}")
        return

    append_lines = []
    if raw_lines and raw_lines[-1].strip():
        append_lines.append("")
    append_lines.append("# IDE skill folders")
    append_lines.extend(f"{entry}/" for entry in missing)
    with gitignore_path.open("a", encoding="utf-8") as file:
        file.write("\n".join(append_lines) + "\n")

    print(f"Gitignore sync: added entries to {gitignore_path}: {', '.join(f'{m}/' for m in missing)}")


def resolve_home_dir(home: str | None) -> Path:
    return Path(home).expanduser().resolve() if home else Path.home()


def resolve_project_dir(project_dir: str | None) -> Path | None:
    return Path(project_dir).expanduser().resolve() if project_dir else None


def build_roots(home_dir: Path, project_dir: Path | None) -> tuple[dict[str, Path], dict[str, Path] | None]:
    global_roots = {
        "claude": home_dir / ".claude" / "skills",
        "codex": home_dir / ".codex" / "skills",
        "gemini": home_dir / ".gemini" / "antigravity" / "skills",
    }
    project_roots = None
    if project_dir is not None:
        project_roots = {
            "claude": project_dir / ".claude" / "skills",
            "codex": project_dir / ".codex" / "skills",
            "gemini": project_dir / ".agent" / "skills",
        }
    return global_roots, project_roots


def validate_scope(scope: str, project_dir: Path | None, sync_gitignore: bool) -> None:
    if scope in ("project", "both") and project_dir is None:
        raise ValueError("--project-dir is required when --scope is 'project' or 'both'.")
    if sync_gitignore and scope not in ("project", "both"):
        raise ValueError("--sync-gitignore requires --scope project or --scope both.")


def selected_locations(
    targets: Iterable[str],
    scope: str,
    global_roots: dict[str, Path],
    project_roots: dict[str, Path] | None,
) -> list[tuple[str, str, Path]]:
    locations: list[tuple[str, str, Path]] = []
    for target in targets:
        if scope in ("global", "both"):
            locations.append((target, "global", global_roots[target]))
        if scope in ("project", "both") and project_roots is not None:
            locations.append((target, "project", project_roots[target]))
    return locations


def find_scripts_dir(args: argparse.Namespace, source_path: Path | None) -> Path | None:
    if args.scripts:
        scripts_dir = Path(args.scripts).expanduser().resolve()
        if not scripts_dir.is_dir():
            raise FileNotFoundError(f"scripts directory not found: {scripts_dir}")
        return scripts_dir

    if source_path:
        sibling_scripts = source_path.parent / "scripts"
        if sibling_scripts.is_dir():
            return sibling_scripts.resolve()
    return None


def prepare_skill_content(args: argparse.Namespace) -> tuple[str, str, Path | None]:
    content, source_path = read_content(args)

    raw_name = args.name
    if raw_name is None:
        frontmatter_name = extract_frontmatter_field(content, "name")
        if frontmatter_name:
            raw_name = frontmatter_name
        elif source_path is not None:
            raw_name = source_path.stem
        else:
            raise ValueError("--name is required when using --text or --stdin.")

    skill_name = slugify(raw_name)
    scripts_dir = find_scripts_dir(args, source_path)
    skill_md = ensure_skill_markdown(content, skill_name, args.description)
    return skill_name, skill_md, scripts_dir


def prepare_copy_source(args: argparse.Namespace) -> tuple[str, Path]:
    source_skill_dir = Path(args.from_path).expanduser().resolve()
    if not source_skill_dir.is_dir():
        raise FileNotFoundError(f"skill folder not found: {source_skill_dir}")
    if not (source_skill_dir / "SKILL.md").is_file():
        raise FileNotFoundError(f"SKILL.md not found in skill folder: {source_skill_dir}")
    skill_name = slugify(args.name if args.name else source_skill_dir.name)
    return skill_name, source_skill_dir


def print_action_header(action: str, skill_name: str, dry_run: bool) -> None:
    prefix = "Dry-run" if dry_run else action.capitalize()
    print(f"{prefix} skill: {skill_name}")


def run_create(args: argparse.Namespace) -> int:
    try:
        skill_name, skill_md, scripts_dir = prepare_skill_content(args)
        home_dir = resolve_home_dir(args.home)
        project_dir = resolve_project_dir(args.project_dir)
        validate_scope(args.scope, project_dir, args.sync_gitignore)
        global_roots, project_roots = build_roots(home_dir, project_dir)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_action_header("building", skill_name, args.dry_run)
    for target, location, root in selected_locations(args.only, args.scope, global_roots, project_roots):
        destination = write_skill(root, skill_name, skill_md, scripts_dir, dry_run=args.dry_run)
        verb = "Would install" if args.dry_run else "Installed"
        print(f"{verb} to {target} ({location}): {destination}")

    if args.sync_gitignore and project_dir is not None:
        sync_gitignore_for_skill_project(project_dir, dry_run=args.dry_run)

    print("Done.")
    return 0


def run_copy(args: argparse.Namespace) -> int:
    try:
        skill_name, source_skill_dir = prepare_copy_source(args)
        home_dir = resolve_home_dir(args.home)
        project_dir = resolve_project_dir(args.project_dir)
        validate_scope(args.scope, project_dir, args.sync_gitignore)
        global_roots, project_roots = build_roots(home_dir, project_dir)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_action_header("copying", skill_name, args.dry_run)
    for target, location, root in selected_locations(args.only, args.scope, global_roots, project_roots):
        destination = copy_skill_folder(source_skill_dir, root, skill_name, dry_run=args.dry_run)
        verb = "Would copy" if args.dry_run else "Copied"
        print(f"{verb} to {target} ({location}): {destination}")

    if args.sync_gitignore and project_dir is not None:
        sync_gitignore_for_skill_project(project_dir, dry_run=args.dry_run)

    print("Done.")
    return 0


def run_remove(args: argparse.Namespace) -> int:
    try:
        skill_name = slugify(args.name)
        home_dir = resolve_home_dir(args.home)
        project_dir = resolve_project_dir(args.project_dir)
        validate_scope(args.scope, project_dir, sync_gitignore=False)
        global_roots, project_roots = build_roots(home_dir, project_dir)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_action_header("removing", skill_name, args.dry_run)
    found_any = False
    for target, location, root in selected_locations(args.only, args.scope, global_roots, project_roots):
        destination = root / skill_name
        removed = remove_skill_folder(destination, dry_run=args.dry_run)
        if removed:
            found_any = True
            verb = "Would remove" if args.dry_run else "Removed"
            print(f"{verb} from {target} ({location}): {destination}")
        else:
            print(f"Not found in {target} ({location}): {destination}")

    if not found_any:
        print("No matching skill folders found.")
    print("Done.")
    return 0


def run_inspect(args: argparse.Namespace) -> int:
    try:
        skill_name = slugify(args.name)
        home_dir = resolve_home_dir(args.home)
        project_dir = resolve_project_dir(args.project_dir)
        validate_scope(args.scope, project_dir, sync_gitignore=False)
        global_roots, project_roots = build_roots(home_dir, project_dir)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    found_any = False
    print(f"Inspect skill: {skill_name}")
    for target, location, root in selected_locations(args.only, args.scope, global_roots, project_roots):
        destination = root / skill_name
        status = "present" if destination.exists() else "missing"
        print(f"{target} ({location}): {status} {destination}")
        if destination.exists():
            found_any = True

    if not found_any:
        print("Skill not found in selected targets.")
        return 1
    return 0


def run_list(args: argparse.Namespace) -> int:
    try:
        home_dir = resolve_home_dir(args.home)
        project_dir = resolve_project_dir(args.project_dir)
        validate_scope(args.scope, project_dir, sync_gitignore=False)
        global_roots, project_roots = build_roots(home_dir, project_dir)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    listed_any = False
    for target, location, root in selected_locations(args.only, args.scope, global_roots, project_roots):
        print(f"{target} ({location}): {root}")
        if not root.exists():
            print("  [missing root]")
            continue
        entries = sorted(path.name for path in root.iterdir() if path.is_dir())
        if not entries:
            print("  [no skills]")
            continue
        listed_any = True
        for entry in entries:
            print(f"  - {entry}")

    if not listed_any:
        print("No skills found in selected targets.")
    return 0


def add_target_options(parser: argparse.ArgumentParser, default_scope: str = "global") -> None:
    parser.add_argument(
        "--only",
        nargs="+",
        choices=TARGET_CHOICES,
        default=list(TARGET_CHOICES),
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
        choices=SCOPE_CHOICES,
        default=default_scope,
        help="Install scope. If --project-dir is set, use 'both' to install globally and per-project.",
    )


def add_mutating_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview target paths and actions without writing or deleting files.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create, copy, remove, inspect, and list skills across Claude, Codex, and Gemini directories."
    )
    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser(
        "create",
        help="Create a skill from file, text, or stdin and install it to selected targets.",
    )
    create_parser.add_argument("source", nargs="?", help="Path to markdown/text file containing skill instructions.")
    create_parser.add_argument("--text", help="Inline instruction text to convert into SKILL.md content.")
    create_parser.add_argument("--stdin", action="store_true", help="Read instruction text from stdin.")
    create_parser.add_argument("--name", help="Skill name (slug). Defaults to input file stem when source file is used.")
    create_parser.add_argument(
        "--description",
        default="User-provided workflow skill.",
        help="Frontmatter description when input is missing required metadata.",
    )
    create_parser.add_argument("--scripts", help="Optional scripts directory to copy into each installed skill.")
    create_parser.add_argument(
        "--sync-gitignore",
        action="store_true",
        help=(
            "When using project scope, sync repo-root .gitignore with .claude/, .codex/, and .agent/ "
            "only if .gitignore already exists and at least one IDE entry already exists."
        ),
    )
    add_target_options(create_parser)
    add_mutating_options(create_parser)

    copy_parser = subparsers.add_parser(
        "copy",
        help="Copy an existing skill folder into selected targets.",
    )
    copy_parser.add_argument("from_path", help="Path to an existing skill folder to copy/install.")
    copy_parser.add_argument("--name", help="Override the installed skill name.")
    copy_parser.add_argument(
        "--sync-gitignore",
        action="store_true",
        help=(
            "When using project scope, sync repo-root .gitignore with .claude/, .codex/, and .agent/ "
            "only if .gitignore already exists and at least one IDE entry already exists."
        ),
    )
    add_target_options(copy_parser)
    add_mutating_options(copy_parser)

    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove a skill from selected targets.",
    )
    remove_parser.add_argument("--name", required=True, help="Skill name (slug) to remove.")
    add_target_options(remove_parser)
    add_mutating_options(remove_parser)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect whether a skill exists in selected targets.",
    )
    inspect_parser.add_argument("--name", required=True, help="Skill name (slug) to inspect.")
    add_target_options(inspect_parser)

    list_parser = subparsers.add_parser(
        "list",
        help="List installed skills in selected targets.",
    )
    add_target_options(list_parser)

    return parser


def run_legacy(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Create/install a skill in Claude, Codex, and Gemini Antigravity skill folders."
    )
    parser.add_argument("source", nargs="?", help="Path to markdown/text file containing skill instructions.")
    parser.add_argument("--new", help="Path to an existing skill folder to copy/install into target IDE folders.")
    parser.add_argument("--text", help="Inline instruction text to convert into SKILL.md content.")
    parser.add_argument("--stdin", action="store_true", help="Read instruction text from stdin.")
    parser.add_argument("--name", help="Skill name (slug). Defaults to input file stem when source file is used.")
    parser.add_argument(
        "--description",
        default="User-provided workflow skill.",
        help="Frontmatter description when input is missing required metadata.",
    )
    parser.add_argument("--scripts", help="Optional scripts directory to copy into each installed skill.")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=TARGET_CHOICES,
        default=list(TARGET_CHOICES),
        help="Install targets. Defaults to all.",
    )
    parser.add_argument("--home", help="Override home directory for installs (default: current user's home).")
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
        choices=SCOPE_CHOICES,
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview target paths and actions without writing files.",
    )
    args = parser.parse_args(argv)

    provided = sum(
        [
            1 if args.source else 0,
            1 if args.text is not None else 0,
            1 if args.stdin else 0,
            1 if args.new else 0,
        ]
    )
    if provided > 1:
        print("Error: use exactly one input mode: source file, --text, --stdin, or --new.", file=sys.stderr)
        return 1

    if args.new:
        shim_args = argparse.Namespace(
            from_path=args.new,
            name=args.name,
            only=args.only,
            home=args.home,
            project_dir=args.project_dir,
            scope=args.scope,
            sync_gitignore=args.sync_gitignore,
            dry_run=args.dry_run,
        )
        return run_copy(shim_args)

    shim_args = argparse.Namespace(
        source=args.source,
        text=args.text,
        stdin=args.stdin,
        name=args.name,
        description=args.description,
        scripts=args.scripts,
        only=args.only,
        home=args.home,
        project_dir=args.project_dir,
        scope=args.scope,
        sync_gitignore=args.sync_gitignore,
        dry_run=args.dry_run,
    )
    return run_create(shim_args)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] in {"create", "copy", "remove", "inspect", "list", "-h", "--help"}:
        parser = build_parser()
        args = parser.parse_args(argv)
        if args.command == "create":
            return run_create(args)
        if args.command == "copy":
            return run_copy(args)
        if args.command == "remove":
            return run_remove(args)
        if args.command == "inspect":
            return run_inspect(args)
        if args.command == "list":
            return run_list(args)
        parser.print_help()
        return 1

    return run_legacy(argv)


if __name__ == "__main__":
    raise SystemExit(main())
