# RFC-TOOLS

**Status:** Informational  
**Author:** Iaroslav Sheptykin  
**Created:** 2026-05-13  
**Repository:** ghcr.io/isheptykin/rfc  

---

## Abstract

This document describes `rfc-tools`, a Docker image that provides a
reproducible, self-contained environment for authoring, linting, and rendering
technical documents in the RFC tradition. Authors mount a local directory and
receive a shell with a curated set of document-tooling on `PATH`, identical
across machines.

## 1. Introduction

Writing an RFC requires more than prose. Authors generate diagrams, convert
source Markdown to multiple output formats, check grammar and style, and verify
spelling — often with tools that install differently on different operating
systems. Environment drift between authors degrades document quality and
introduces friction.

`rfc-tools` resolves this by shipping all required tools in a single OCI
image. The image is built and published automatically on every push to `main`;
a smoke-test stage must pass before the production image is pushed.

## 2. Included Tools

| Tool | Purpose |
|---|---|
| `pandoc` | Document format conversion — Markdown → HTML, PDF, DOCX, … |
| `plantuml` | UML and sequence diagrams from text |
| `graphviz` (`dot`) | Directed graphs and network topology diagrams |
| `mmdc` (mermaid-cli) | Flowcharts and sequence diagrams from Mermaid syntax |
| `vale` | Prose style and grammar linting |
| `aspell` | Spell checking (English dictionary included) |
| `markdownlint` | Markdown structure and style linting |
| `jq` | JSON processing |
| `git`, `make`, `curl` | General-purpose authoring utilities |

## 3. Usage

### 3.1 Starting a Shell

```sh
docker run -it --rm \
  -v "$(pwd):/workspace" \
  ghcr.io/yariksheptykin/rfc
```

All tools are available on `PATH`. The working directory inside the container
is `/workspace`, mapped to the host directory provided at runtime.

### 3.2 Converting a Document

```sh
# Markdown to HTML
pandoc RFC.md -o RFC.html

# Markdown to PDF (weasyprint renders the bundled stylesheet cleanly)
pandoc RFC.md --css /rfc/rfc.css --pdf-engine=weasyprint -o RFC.pdf

# Markdown to DOCX
pandoc RFC.md -o RFC.docx
```

### 3.3 Rendering Diagrams

```sh
# Mermaid (pass the bundled puppeteer config for --no-sandbox)
mmdc -i diagram.mmd -o diagram.svg -p /etc/mermaid/puppeteer-config.json

# PlantUML
plantuml sequence.puml

# Graphviz
dot -Tsvg architecture.dot -o architecture.svg
```

### 3.4 Linting and Spell-Checking

```sh
vale RFC.md
markdownlint RFC.md
echo "check spelling" | aspell list -l en
```

### 3.5 Managing RFCs with the `rfc` CLI

The image ships a `rfc` command for managing RFC documents.

**Bootstrap a new RFC**

```sh
docker run -it --rm \
  -v "$(pwd):/workspace" \
  ghcr.io/yariksheptykin/rfc \
  rfc bootstrap "Distributed Rate Limiting"
```

This creates `0001-distributed-rate-limiting.md` in the current directory,
pre-filled with today's date, your git author name, and the full RFC template
(Abstract, Motivation, Proposal, Drawbacks, Alternatives, Security
Considerations, RFC 2119 boilerplate).

The filename prefix increments automatically based on existing `NNNN-*.md`
files in the directory, so running `rfc bootstrap` twice produces
`0001-…md` and `0002-….md`.

**Options**

| Flag | Effect |
|---|---|
| `TITLE` | RFC title. Used to derive the `NNNN-slug.md` filename. |
| `-o FILE` | Write to `FILE` instead of the auto-generated name. |
| `--force` | Overwrite the output file if it already exists. |

**Help**

```sh
docker run --rm ghcr.io/yariksheptykin/rfc rfc bootstrap --help
```

## 4. CI Integration

### 4.1 GitLab CI — Render RFC to PDF

The example below converts a Markdown RFC to a clean, print-ready PDF.
Pandoc delegates rendering to WeasyPrint, which applies the bundled stylesheet
directly — no browser chrome, no URLs or titles in margins, content only.

```yaml
image: ghcr.io/yariksheptykin/rfc:main

stages:
  - render

render_pdf:
  stage: render
  script:
    - mkdir -p dist
    - pandoc RFC.md --css /rfc/rfc.css --pdf-engine=weasyprint -o dist/RFC.pdf
  artifacts:
    paths:
      - dist/RFC.pdf
    expire_in: 1 week
```

**Key flags:**

| Flag | Effect |
|---|---|
| `--pdf-engine=weasyprint` | WeasyPrint renders via CSS — no browser headers, footers, or URLs |
| `--css /rfc/rfc.css` | Applies the bundled RFC stylesheet (typography, tables, page margins) |
| `@page { margin: 2.5cm }` | Page margins controlled by CSS, not by a browser print dialog |

## 5. Image Targets

The Dockerfile defines two build targets:

- **`production`** *(default)*: the full tool image ready for authoring work.
- **`test`**: extends `production` and executes a smoke test for each installed
  tool. The CI pipeline builds `test` first; a failure in any smoke test blocks
  publication of the `production` image.

Build the test target locally with:

```sh
docker build --target test .
```

## 6. Security Considerations

Chromium is installed as the rendering engine for mermaid-cli and is
configured to run with `--no-sandbox` inside the container. Authors should
avoid processing untrusted Mermaid input in automated or networked pipelines
and should not expose the container's network interface unless required.

## 7. References

- Pandoc — https://pandoc.org
- PlantUML — https://plantuml.com
- Graphviz — https://graphviz.org
- Mermaid — https://mermaid.js.org
- Vale — https://vale.sh
- markdownlint-cli — https://github.com/igorshubovych/markdownlint-cli
- aspell — http://aspell.net
