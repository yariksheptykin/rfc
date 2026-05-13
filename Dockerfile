ARG VALE_VERSION=3.7.1

# ── base: all tools ──────────────────────────────────────────────────────────
FROM debian:bookworm-slim AS base

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
        nodejs \
        npm \
        pandoc \
        plantuml \
        python3 \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @mermaid-js/mermaid-cli markdownlint-cli \
    && npm cache clean --force

RUN curl -fsSL \
        "https://github.com/errata-ai/vale/releases/download/v${VALE_VERSION}/vale_${VALE_VERSION}_Linux_64-bit.tar.gz" \
    | tar -xz -C /usr/local/bin vale

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
    && echo "# ok" | pandoc -f markdown -t html \
    \
    && echo "==> graphviz" \
    && echo "digraph G{A->B}" | dot -Tsvg > /dev/null \
    \
    && echo "==> plantuml" \
    && printf '@startuml\nAlice -> Bob: Hello\n@enduml\n' > /tmp/smoke.puml \
    && plantuml /tmp/smoke.puml \
    && test -f /tmp/smoke.png \
    \
    && echo "==> aspell" \
    && echo "hello wrold" | aspell list -l en | grep -q wrold \
    \
    && echo "==> jq" \
    && echo '{"ok":true}' | jq -e .ok \
    \
    && echo "==> vale" \
    && vale --version \
    \
    && echo "==> markdownlint" \
    && echo "# Heading" > /tmp/smoke.md \
    && markdownlint /tmp/smoke.md \
    \
    && echo "==> mmdc (mermaid)" \
    && printf 'graph LR\n    A-->B\n' > /tmp/smoke.mmd \
    && mmdc -i /tmp/smoke.mmd -o /tmp/smoke.svg \
       -p /etc/mermaid/puppeteer-config.json \
    \
    && echo "All smoke tests passed."

CMD ["echo", "All smoke tests passed."]
