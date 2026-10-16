"""Install complete skill folders without overwriting an existing skill."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

SKILLS = ("injection-fuzzer", "schema-breaker", "pii-leak-prober", "hallucination-trap", "auto-hardener")
SOURCE = Path(__file__).resolve().parent.parent / "skills"


def install_skills(destination: Path, *, copy: bool = False, dry_run: bool = False) -> list[str]:
    sources = [SOURCE / name for name in SKILLS]
    for source in sources:
        manifest = source / "SKILL.md"
        if not manifest.is_file() or not (source / "scripts" / "run_skill.py").is_file():
            raise ValueError(f"Incomplete skill: {source.name}")
        content = manifest.read_text(encoding="utf-8")
        if not content.startswith("---\n") or f"name: {source.name}\n" not in content:
            raise ValueError(f"Invalid skill manifest: {source.name}")
    # Validate all destinations before creating anything.
    for source in sources:
        target = destination / source.name
        if target.exists() or target.is_symlink():
            if not (target.is_symlink() and target.resolve() == source.resolve()):
                raise FileExistsError(f"Existing skill preserved: {target}")
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)
        for source in sources:
            target = destination / source.name
            if target.is_symlink():
                continue
            if copy:
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                target.symlink_to(source, target_is_directory=True)
    return list(SKILLS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_home = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes")))
    parser.add_argument("--destination", type=Path, default=default_home / "skills")
    parser.add_argument("--copy", action="store_true", help="Copy instead of linking (recommended on Windows)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        names = install_skills(args.destination, copy=args.copy, dry_run=args.dry_run)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"{'Validated' if args.dry_run else 'Installed'} {len(names)} skills: {', '.join(names)}")
    print("Install Chaos-Harness in the agent's Python environment, then run: hermes skills list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
