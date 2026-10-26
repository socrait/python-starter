"""Check a project generated from the template: right files for its answers, no leftover
names, and its own `app check` passes. Used by both CI configurations.

    uv run python scripts/check_generated.py PATH --database sqlite --forge github
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

LEFTOVER_NAMES = re.compile(r"starter[-_]app|STARTER_APP")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--database", choices=["sqlite", "postgres"], required=True)
    parser.add_argument("--forge", choices=["github", "gitlab", "none"], required=True)
    args = parser.parse_args()
    root: Path = args.path

    problems = _layout_problems(root, database=args.database, forge=args.forge)
    problems += [f"leftover template name in {p}" for p in _files_with_leftover_names(root)]
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    # A fresh project has no lockfile yet: `uv sync` creates it. Its pre-commit hooks see
    # only tracked files, so stage everything first.
    commands = (
        ["uv", "sync"],
        ["git", "init", "--quiet"],
        ["git", "add", "--all"],
        ["uv", "run", "pre-commit", "run", "--all-files"],
        ["uv", "run", "app", "check"],
    )
    for command in commands:
        if subprocess.call(command, cwd=root):  # noqa: S603 - fixed commands, no input
            return 1
    return 0


def _layout_problems(root: Path, *, database: str, forge: str) -> list[str]:
    expected = {
        "compose.yaml": database == "postgres",
        ".github/workflows/ci.yml": forge == "github",
        ".gitlab-ci.yml": forge == "gitlab",
        ".copier-answers.yml": True,
        ".env.example": True,
    }
    problems = [
        f"{path} should {'exist' if wanted else 'not exist'}"
        for path, wanted in expected.items()
        if (root / path).exists() != wanted
    ]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    if ("psycopg" in pyproject) != (database == "postgres"):
        problems.append(f"psycopg dependency doesn't match database={database}")
    return problems


def _files_with_leftover_names(root: Path) -> list[Path]:
    found = []
    for path in root.rglob("*"):
        if ".venv" in path.parts or ".git" in path.parts or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if LEFTOVER_NAMES.search(text) or LEFTOVER_NAMES.search(str(path)):
            found.append(path.relative_to(root))
    return found


if __name__ == "__main__":
    sys.exit(main())
