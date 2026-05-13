#!/usr/bin/env bash
set -euo pipefail

RENDERED=/tmp/test-pdf-rendered.pdf
UPDATE_BASELINE=0
SOURCE_MD=""
BASELINE_PDF=""

usage() {
    cat <<'EOF'
test-pdf.sh — render a Markdown file to PDF and compare against a baseline

Run from the host (repo root):

  # Compare rendered output against the baseline:
  docker run --rm \
    -v "$(pwd)/tests/pdf:/tests/pdf" \
    ghcr.io/yariksheptykin/rfc:main \
    /tests/pdf/test-pdf.sh /tests/pdf/test.md /tests/pdf/test.pdf

  # Re-render and overwrite the baseline (after changing test.md or rfc.css):
  docker run --rm \
    -v "$(pwd)/tests/pdf:/tests/pdf" \
    ghcr.io/yariksheptykin/rfc:main \
    /tests/pdf/test-pdf.sh /tests/pdf/test.md /tests/pdf/test.pdf --update-baseline

This script runs INSIDE the container — pandoc, weasyprint, and /rfc/rfc.css
are all provided by the image. The volume mount makes the rendered PDF
accessible on the host so --update-baseline can write the new baseline back.

Usage:
  test-pdf.sh <source.md> <baseline.pdf> [--update-baseline]

Parameters:
  source.md           Markdown file to render with pandoc + weasyprint
  baseline.pdf        Reference PDF to compare against (golden file)
  --update-baseline   Overwrite baseline.pdf with the freshly rendered output
                      instead of comparing. Commit both files together.

Comparison is an exact md5 match. WeasyPrint produces byte-identical output
for the same input and library version, so the hash is stable across runs.
If a weasyprint upgrade changes the output format, re-run with
--update-baseline to accept the new output as the new baseline.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --help) usage; exit 0 ;;
        --update-baseline) UPDATE_BASELINE=1 ;;
        *)
            if   [ -z "$SOURCE_MD"    ]; then SOURCE_MD="$arg"
            elif [ -z "$BASELINE_PDF" ]; then BASELINE_PDF="$arg"
            else echo "Unexpected argument: $arg" >&2; exit 1
            fi ;;
    esac
done

if [ -z "$SOURCE_MD" ] || [ -z "$BASELINE_PDF" ]; then
    echo "Usage: $0 <source.md> <baseline.pdf> [--update-baseline] [--help]" >&2
    exit 1
fi

[ -f "$SOURCE_MD" ] || { echo "Not found: $SOURCE_MD" >&2; exit 1; }
[ "$UPDATE_BASELINE" = "1" ] || [ -f "$BASELINE_PDF" ] \
    || { echo "Not found: $BASELINE_PDF" >&2; exit 1; }

pandoc "$SOURCE_MD" --css /rfc/rfc.css --pdf-engine=weasyprint -o "$RENDERED"

if [ "$UPDATE_BASELINE" = "1" ]; then
    cp "$RENDERED" "$BASELINE_PDF"
    echo "Baseline updated: $BASELINE_PDF"
    echo "  md5: $(md5sum "$BASELINE_PDF" | awk '{print $1}')"
else
    expected=$(md5sum "$BASELINE_PDF" | awk '{print $1}')
    actual=$(md5sum "$RENDERED"       | awk '{print $1}')
    if [ "$expected" = "$actual" ]; then
        echo "OK  $BASELINE_PDF"
    else
        echo "FAIL: rendered PDF does not match baseline" >&2
        echo "  expected: $expected  ($BASELINE_PDF)" >&2
        echo "  actual:   $actual  ($SOURCE_MD)" >&2
        exit 1
    fi
fi
