"""Check that `copier update` moves a generated project from one release to the next.

Builds the template into a scratch git repository tagged v0.0.1, generates a project from
it, then tags a v0.0.2 with a change and runs `copier update`. Used by CI.

    uv run python scripts/check_update.py SCRATCH_DIR
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = "Line added by the update check."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scratch", type=Path, help="Empty or missing directory to work in")
    scratch: Path = parser.parse_args().scratch.resolve()
    if scratch.exists():
        shutil.rmtree(scratch)
    source, project = scratch / "template-repo", scratch / "acme-billing"

    _run(sys.executable, str(ROOT / "scripts" / "build_template.py"), str(source))
    _commit(source, "v0.0.1")
    _copier(
        "copy",
        "--defaults",
        "--vcs-ref",
        "v0.0.1",
        "--data",
        "project_name=acme-billing",
        str(source),
        str(project),
    )
    _commit(project, None)

    readme = source / "template" / "README.md.jinja"
    readme.write_text(readme.read_text(encoding="utf-8") + f"\n{MARKER}\n", encoding="utf-8")
    _commit(source, "v0.0.2")
    _copier("update", "--defaults", "--vcs-ref", "v0.0.2", cwd=project)

    changed = _git(project, "status", "--porcelain").split("\n")
    changed = sorted(line[3:] for line in changed if line)
    if changed != [".copier-answers.yml", "README.md"] or MARKER not in (
        project / "README.md"
    ).read_text(encoding="utf-8"):
        print(f"Unexpected update result; changed files: {changed}", file=sys.stderr)
        return 1
    return 0


def _commit(repo: Path, tag: str | None) -> None:
    if not (repo / ".git").exists():
        _git(repo, "init", "--quiet")
    _git(repo, "add", "--all")
    _git(
        repo,
        "-c",
        "user.name=ci",
        "-c",
        "user.email=ci@example.com",
        "commit",
        "--quiet",
        "--message",
        tag or "generated",
    )
    if tag:
        _git(repo, "tag", tag)


def _copier(*args: str, cwd: Path | None = None) -> None:
    _run(str(Path(sys.executable).parent / "copier"), *args, cwd=cwd)


def _git(repo: Path, *args: str) -> str:
    return _run("git", *args, cwd=repo)


def _run(*command: str, cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)  # noqa: S603
    return result.stdout


if __name__ == "__main__":
    sys.exit(main())
