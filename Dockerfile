ARG VALE_VERSION=3.7.1

# ── base: all tools ──────────────────────────────────────────────────────────
FROM node:20-bookworm-slim AS base

ARG VALE_VERSION

ENV PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

RUN apt-get update && apt-get install -y --no-install-recommends \
        aspell \
        aspell-en \
        ca-certificates \
        chromium \
        curl \
        default-jre-headless \
        git \
        graphviz \
        jq \
        make \
        pandoc \
        plantuml \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install weasyprint --break-system-packages

RUN npm install -g @mermaid-js/mermaid-cli markdownlint-cli \
    && npm cache clean --force

RUN curl -fsSL \
        "https://github.com/errata-ai/vale/releases/download/v${VALE_VERSION}/vale_${VALE_VERSION}_Linux_64-bit.tar.gz" \
    | tar -xz -C /usr/local/bin vale

COPY src/rfc.css /rfc/rfc.css
RUN chmod a+r /rfc/rfc.css

COPY --chmod=755 src/rfc.py /usr/local/bin/rfc

# Chromium inside a container requires --no-sandbox
RUN mkdir -p /etc/mermaid \
    && echo '{"args":["--no-sandbox","--disable-setuid-sandbox"]}' \
       > /etc/mermaid/puppeteer-config.json

WORKDIR /workspace

# ── production (default) ─────────────────────────────────────────────────────
FROM base AS production

CMD ["/bin/bash"]

# ── test: smoke-test every tool before publishing ────────────────────────────
FROM base AS test

RUN echo "==> pandoc" \
    && echo "# ok" | pandoc -f markdown -t html

RUN echo "==> graphviz" \
    && echo "digraph G{A->B}" | dot -Tsvg > /dev/null

RUN echo "==> plantuml" \
    && printf '@startuml\nAlice -> Bob: Hello\n@enduml\n' > /tmp/smoke.puml \
    && plantuml /tmp/smoke.puml \
    && test -f /tmp/smoke.png

RUN echo "==> aspell" \
    && echo "hello wrold" | aspell list -l en | grep -q wrold

RUN echo "==> jq" \
    && echo '{"ok":true}' | jq -e .ok

RUN echo "==> vale" \
    && vale --version

RUN echo "==> markdownlint" \
    && echo "# Heading" > /tmp/smoke.md \
    && markdownlint /tmp/smoke.md

RUN echo "==> mmdc (mermaid)" \
    && printf 'graph LR\n    A-->B\n' > /tmp/smoke.mmd \
    && mmdc -i /tmp/smoke.mmd -o /tmp/smoke.svg \
       -p /etc/mermaid/puppeteer-config.json

RUN echo "==> weasyprint" \
    && echo "# ok" | pandoc -s --css /rfc/rfc.css --pdf-engine=weasyprint -o /tmp/smoke.pdf \
    && test -f /tmp/smoke.pdf

COPY src/ /app/src/
COPY tests/test_rfc.py /app/tests/test_rfc.py

RUN echo "==> rfc unit tests" \
    && python3 /app/tests/test_rfc.py

COPY tests/pdf/* /tests/pdf/
RUN echo "==> pdf regression" \
    && chmod +x /tests/pdf/test-pdf.py \
    && /tests/pdf/test-pdf.py /tests/pdf/test.md /tests/pdf/test.pdf

RUN echo "==> rfc bootstrap (explicit output)" \
    && rfc bootstrap "Distributed Rate Limiting" -o /tmp/rfc-smoke.md \
    && test -f /tmp/rfc-smoke.md \
    && grep -q "Title: Distributed Rate Limiting" /tmp/rfc-smoke.md \
    && grep -q "RFC 2119" /tmp/rfc-smoke.md \
    && grep -q "## Abstract" /tmp/rfc-smoke.md \
    && grep -q "## Motivation" /tmp/rfc-smoke.md \
    && grep -q "## Proposal" /tmp/rfc-smoke.md \
    && grep -q "## Drawbacks" /tmp/rfc-smoke.md \
    && grep -q "## Alternatives" /tmp/rfc-smoke.md \
    && grep -q "## Security Considerations" /tmp/rfc-smoke.md

RUN echo "==> rfc bootstrap (auto-naming and numbering)" \
    && mkdir /tmp/rfc-autonaming \
    && cd /tmp/rfc-autonaming \
    && rfc bootstrap "First RFC" \
    && test -f 0001-first-rfc.md \
    && rfc bootstrap "Second RFC" \
    && test -f 0002-second-rfc.md

RUN echo "==> rfc bootstrap (--force overwrites, without --force fails)" \
    && rfc bootstrap "Overwrite Test" -o /tmp/rfc-overwrite.md \
    && rfc bootstrap "Overwrite Test" -o /tmp/rfc-overwrite.md --force \
    && if rfc bootstrap "Overwrite Test" -o /tmp/rfc-overwrite.md; then exit 1; fi

RUN echo "==> rfc bootstrap (agent files created)" \
    && mkdir /tmp/rfc-agents && cd /tmp/rfc-agents \
    && rfc bootstrap "Agent Test" \
    && test -f .claude/skills/rfc/SKILL.md \
    && grep -q "description:" .claude/skills/rfc/SKILL.md \
    && grep -q "RFC 2119" .claude/skills/rfc/SKILL.md \
    && test -f .github/copilot-instructions.md \
    && grep -q "rfc-tools" .github/copilot-instructions.md \
    && grep -q "RFC 2119" .github/copilot-instructions.md

RUN echo "==> rfc bootstrap (agent files idempotent)" \
    && cd /tmp/rfc-agents \
    && rfc bootstrap "Second RFC" 2>&1 | grep -q "Skipped .claude/skills/rfc/SKILL.md" \
    && rfc bootstrap "Second RFC" 2>&1 | grep -q "Skipped .github/copilot-instructions.md"

RUN echo "==> rfc render (derived output name)" \
    && echo "# Smoke" > /tmp/render-smoke.md \
    && rfc render /tmp/render-smoke.md \
    && test -f /tmp/render-smoke.pdf

RUN echo "==> rfc render (explicit output)" \
    && rfc render /tmp/render-smoke.md -o /tmp/render-explicit.pdf \
    && test -f /tmp/render-explicit.pdf

RUN echo "==> rfc render (missing input exits non-zero)" \
    && if rfc render /tmp/nonexistent.md; then exit 1; fi

CMD ["echo", "All smoke tests passed."]
