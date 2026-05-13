# agents.md — guide for AI agents contributing to rfc-tools

This file is the first thing an AI coding agent should read before making
changes to this repository. It describes what the project does, where things
live, how to develop safely, and how releases are cut.

---

## Purpose

`rfc-tools` is a Docker image that gives engineering teams a reproducible,
single-command environment for authoring, linting, and rendering technical
RFCs written in Markdown. It ships:

- Document conversion and PDF rendering (`pandoc`, `weasyprint`, `rfc.css`)
- Diagram generation (`plantuml`, `graphviz`, `mmdc`)
- Prose and style linting (`vale`, `aspell`, `markdownlint`)
- A `rfc` CLI (`src/rfc.py`) for bootstrapping new RFC documents and
  scaffolding agent skill files for Claude Code and GitHub Copilot

The image is published to `ghcr.io/yariksheptykin/rfc`. Every push to `main`
runs the full test suite inside Docker before the production image is pushed.
Tagged releases (`v*`) produce additional versioned image tags.

---

## Directory map

```
Dockerfile              Two-stage build: base→production and base→test
src/
  rfc.py                The rfc CLI entry point (installed as /usr/local/bin/rfc)
  rfc.css               Bundled RFC stylesheet (installed at /rfc/rfc.css)
tests/
  test_rfc.py           Python unit tests for rfc.py (unittest, stdlib only)
  pdf/
    test.md             Markdown source for the PDF regression baseline
    test.pdf            Golden PDF baseline (regenerate with test-pdf.sh)
    test-pdf.sh         Script: render test.md and compare or update baseline
.github/
  workflows/
    docker.yml          CI: build test target, then publish production image
README.md               User-facing documentation
agents.md               This file
```

---

## Development workflow

### Test-driven development

New behaviour MUST be specified as a failing test before implementation.
The project uses two test layers that must both stay green:

**Python unit tests** (`tests/test_rfc.py`)

Cover pure logic: slugification, file-guard helpers, agent scaffolding,
and CLI argument handling. Run locally with:

```sh
python3 tests/test_rfc.py
```

All tests use `unittest` from the standard library. Do not add external
test dependencies.

**Docker smoke and integration tests** (Dockerfile `test` stage)

Cover the full tool chain end-to-end: every installed binary is exercised,
the PDF regression baseline is checked by md5 hash, and the `rfc` CLI is
exercised through its public interface (not imported). Build with:

```sh
docker build --target test .
```

### Adding a new feature

1. Write a failing test in `tests/test_rfc.py` (for `rfc.py` changes) or a
   new `RUN` layer in the Dockerfile `test` stage (for image-level changes).
2. Confirm the test fails before writing any implementation.
3. Implement the minimum code to make the test pass.
4. Run both test layers and confirm all pass.
5. Update `README.md` (see below).

### Updating the PDF baseline

When `tests/pdf/test.md` or `src/rfc.css` changes, the golden PDF must be
regenerated inside the canonical image so the md5 hash stays consistent:

```sh
docker run --rm \
  -v "$(pwd)/tests/pdf:/tests/pdf" \
  ghcr.io/yariksheptykin/rfc:main \
  /tests/pdf/test-pdf.sh /tests/pdf/test.md /tests/pdf/test.pdf --update-baseline
```

Commit `test.pdf` alongside the change that required the regeneration.

---

## Updating README.md

`README.md` is the user-facing document. Keep it in sync whenever the public
interface changes. Rules:

- **New tool added to the image** → add a row to the Included Tools table
  (section 2) and a usage example in section 3.
- **New `rfc` subcommand or flag** → update section 3.5. Document every flag
  in the options table. If behaviour differs between first-run and repeat-run
  (e.g. idempotency), state both explicitly.
- **New agent skill file** → describe what it does and where it is created in
  section 3.5 under the numbered bootstrap list.
- **CI or image target change** → update sections 4 or 5 as appropriate.
- Section numbering is sequential; renumber downstream sections when inserting.
- Do not describe implementation details (file paths inside the container,
  internal function names). Write for the user running `docker run`.

---

## Publishing a release

Use `publish.sh` to validate, commit, tag, and push in a single step.
The script is the canonical way for agents to cut a release.

```sh
./publish.sh "Short description of what changed" v1.6.0
```

**What it does, in order:**

1. Stages all changes (`git add -A`) and prints a diff summary.
2. Builds the Docker `test` target. If any smoke test or unit test fails,
   the staged changes are rolled back and nothing is written to the remote.
3. On success: commits with the supplied message, creates an annotated tag,
   and pushes both `main` and the tag to `origin`.

If there is nothing to commit (e.g. tagging an already-committed state),
step 3 skips the commit and proceeds directly to tagging and pushing.

Run `./publish.sh --help` for the full usage text including semver examples.

---

## Tagging and release

Releases follow **semver** (`vMAJOR.MINOR.PATCH`). Create a tag to publish
a versioned image:

```sh
git tag v1.5.0 -m "Short description of what changed"
git push origin v1.5.0
```

The CI workflow (`docker.yml`) triggers on `v*` tags and publishes the
production image with the following tags automatically:

| Image tag | Source |
|---|---|
| `1.5.0` | Full semver from the git tag |
| `1.5` | Major.minor — consumers who want patch auto-updates pin here |
| `main` | Always the latest commit on the main branch |
| `sha-<short>` | Immutable pointer to the exact commit |

**When to bump which component:**

| Change | Version bump |
|---|---|
| Breaking change to the public interface or tool removal | `MAJOR` |
| New tool, new CLI subcommand, new file, new feature — anything additive | `MINOR` |
| Bug fix or correction to existing behaviour, content, or documentation | `PATCH` |

The key distinction between `MINOR` and `PATCH`: if something new exists after
the change that did not exist before (a file, a flag, a tool, a guide), it is
`MINOR`. If something existing was corrected or repaired, it is `PATCH`.

The `main` tag is updated on every push and is suitable for CI pipelines that
always want the latest. Pin to a `MAJOR.MINOR` tag for reproducible builds.
