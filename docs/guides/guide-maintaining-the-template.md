# Maintaining the template

This repository is a working project and a [Copier](https://copier.readthedocs.io/)
template. The project at the root is the source of truth; the template is derived from it
when a release is tagged, so `main` never carries a second copy of the code.

## How the template is built

[scripts/build_template.py](../../scripts/build_template.py) copies every tracked file
into `template/`, then:

- replaces `starter-app`, `starter_app`, `STARTER_APP`, and the default description with
  Copier variables;
- turns comment-line blocks `begin: postgres-only` ... `end: postgres-only` (and
  `sqlite-only`) into conditionals on the `database` answer, and drops
  `template-repo-only` blocks;
- generates `compose.yaml`, `.github/`, and `.gitlab-ci.yml` only for the answers that use
  them (see `PATH_CONDITIONS`);
- leaves out this repository's own machinery: the LICENSE, `uv.lock`, the build and check
  scripts, the template and release workflows, and this guide.

Files it changes get a `.jinja` suffix; everything else in them stays literal, including
`${{ }}` in workflow files. The questions live in [copier.yml](../../copier.yml).

## Making a change

Change the project as you would any project, then try the template:

```bash
uv run app check
uv run python scripts/build_template.py /tmp/tpl
uv run copier copy --defaults --data database=postgres --data forge=gitlab \
  --data project_name=acme-billing /tmp/tpl /tmp/acme-billing
uv run python scripts/check_generated.py /tmp/acme-billing --database postgres --forge gitlab
```

CI does the same for every combination of database and forge, and checks that a project
generated from one release updates cleanly to the next with `copier update`
([template.yml](../../.github/workflows/template.yml),
[check_update.py](../../scripts/check_update.py)).

## Releasing

Run the **Release** workflow with a version such as `v0.2.0`. It builds `template/` from
`main`, commits it on a commit that only the tag points to, pushes the tag, and publishes
release notes. `copier copy` and `copier update` use the newest tag:

```bash
uvx copier copy gh:socrait/python-starter my-service
cd my-service && uvx copier update        # later, to pull in a newer release
```
