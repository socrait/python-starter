"""Build the Copier template from this repository's own project.

The repository root is a working project and the source of truth. The template is derived
from it at release time (and in CI) by replacing the project's names with Copier variables
and turning marked blocks into conditionals:

    uv run python scripts/build_template.py OUT   # writes OUT/copier.yml and OUT/template/

Marked blocks are comment lines `begin: <name>` ... `end: <name>` (`#` or `<!-- -->`):
`template-repo-only` blocks are dropped; the others become `{% if %}` blocks.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Longest first, so a replacement never splits a longer token.
REPLACEMENTS = (
    ("STARTER_APP", "{{ env_prefix }}"),
    ("starter_app", "{{ package_name }}"),
    ("starter-app", "{{ project_name }}"),
    ("A FastAPI + SQLAlchemy service", "{{ description }}"),
)

BLOCK_CONDITIONS = {
    "postgres-only": 'database == "postgres"',
    "sqlite-only": 'database == "sqlite"',
}
REPO_ONLY = "template-repo-only"

# Files and directories generated only for some answers.
PATH_CONDITIONS = {
    "compose.yaml": 'database == "postgres"',
    ".github": 'forge == "github"',
    ".gitlab-ci.yml": 'forge == "gitlab"',
}

EXCLUDED = (
    "LICENSE",  # a generated project chooses its own
    "uv.lock",  # depends on the answers; `uv sync` creates it in the new project
    "copier.yml",
    "scripts/build_template.py",
    "scripts/check_generated.py",
    "scripts/check_update.py",
    ".github/workflows/template.yml",
    ".github/workflows/release.yml",
    "docs/guides/guide-maintaining-the-template.md",
)

# Records the answers in generated projects, which `copier update` needs.
ANSWERS_FILE = "{{ _copier_conf.answers_file }}.jinja"
ANSWERS_TEMPLATE = (
    "# Changes here will be overwritten by Copier; do not edit manually.\n"
    "{{ _copier_answers | to_nice_yaml }}"
)

MARKER = re.compile(r"^\s*(?:#|<!--)\s*(begin|end):\s*([a-z-]+)\s*(?:-->)?\s*$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, help="Directory to write copier.yml and template/ into")
    args = parser.parse_args()
    out: Path = args.out.resolve()
    _build(out / "template")
    if out != ROOT:
        shutil.copy2(ROOT / "copier.yml", out / "copier.yml")
    return 0


def _build(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    for relative in _tracked_files():
        source = ROOT / relative
        target = destination / _template_path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(source, target)
            continue
        rendered, is_template = _template_text(text)
        if is_template:
            target = target.with_name(target.name + ".jinja")
        target.write_text(rendered, encoding="utf-8")
        shutil.copymode(source, target)
    (destination / ANSWERS_FILE).write_text(ANSWERS_TEMPLATE, encoding="utf-8")


def _tracked_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted(
        path
        for path in output.splitlines()
        if not path.startswith("template/") and path not in EXCLUDED and (ROOT / path).is_file()
    )


def _template_path(path: str) -> str:
    for prefix, condition in PATH_CONDITIONS.items():
        if path == prefix or path.startswith(prefix + "/"):
            head, _, name = prefix.rpartition("/")
            wrapped = f"{{% if {condition} %}}{name}{{% endif %}}"
            path = (f"{head}/" if head else "") + wrapped + path[len(prefix) :]
            break
    for token, variable in REPLACEMENTS:
        path = path.replace(token, variable)
    return path


def _template_text(text: str) -> tuple[str, bool]:
    """The file's template source, and whether Copier must render it.

    Text stays literal (including any `{{ }}` of its own) except for the replaced names
    and the conditional blocks.
    """
    segments: list[tuple[bool, str]] = []  # (is_jinja_tag, content)
    skipping = False
    # Formatters surround a marker comment with blank lines on both sides; without the
    # marker those would double up, so blank lines right after a marker that already has
    # blank lines before it are dropped.
    swallow_blanks = False
    previous_blank = False
    for line in text.splitlines(keepends=True):
        marker = MARKER.match(line)
        if marker is None:
            blank = not line.strip()
            if swallow_blanks and blank:
                continue
            swallow_blanks = False
            previous_blank = blank
            if not skipping:
                if segments and not segments[-1][0]:
                    segments[-1] = (False, segments[-1][1] + line)
                else:
                    segments.append((False, line))
            continue
        swallow_blanks = previous_blank
        edge, name = marker.groups()
        if name == REPO_ONLY:
            skipping = edge == "begin"
        elif edge == "begin":
            segments.append((True, f"{{% if {BLOCK_CONDITIONS[name]} %}}"))
        else:
            segments.append((True, "{% endif %}"))

    plain = "".join(content for _, content in segments)
    has_tags = any(is_tag for is_tag, _ in segments)
    if not has_tags and not any(token in plain for token, _ in REPLACEMENTS):
        return plain, False

    rendered = []
    for is_tag, content in segments:
        if is_tag:
            rendered.append(content)
            continue
        escaped = "{% raw %}" + content + "{% endraw %}"
        for token, variable in REPLACEMENTS:
            escaped = escaped.replace(token, "{% endraw %}" + variable + "{% raw %}")
        rendered.append(escaped)
    return "".join(rendered).replace("{% raw %}{% endraw %}", ""), True


if __name__ == "__main__":
    sys.exit(main())
