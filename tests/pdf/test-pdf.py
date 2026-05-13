#!/usr/bin/env python3
"""Render a Markdown file to PDF and compare against a baseline."""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DESCRIPTION = """\
test-pdf.py — render a Markdown file to PDF and compare against a baseline

Run from the host (repo root):

  # Compare rendered output against the baseline:
  docker run --rm \\
    -v "$(pwd)/tests/pdf:/tests/pdf" \\
    ghcr.io/yariksheptykin/rfc:main \\
    /tests/pdf/test-pdf.py /tests/pdf/test.md /tests/pdf/test.pdf

  # Re-render and overwrite the baseline (after changing test.md or rfc.css):
  docker run --rm \\
    -v "$(pwd)/tests/pdf:/tests/pdf" \\
    ghcr.io/yariksheptykin/rfc:main \\
    /tests/pdf/test-pdf.py /tests/pdf/test.md /tests/pdf/test.pdf --update-baseline

This script runs INSIDE the container — pandoc, weasyprint, and /rfc/rfc.css
are all provided by the image. The volume mount makes the rendered PDF
accessible on the host so --update-baseline can write the new baseline back.

Comparison is an exact md5 match. WeasyPrint produces byte-identical output
for the same input and library version, so the hash is stable across runs.
If a weasyprint upgrade changes the output format, re-run with
--update-baseline to accept the new output as the new baseline.
"""


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def render(source: Path, dest: Path) -> None:
    subprocess.run(
        ['pandoc', str(source), '--css', '/rfc/rfc.css', '--pdf-engine=weasyprint', '-o', str(dest)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='test-pdf.py',
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('source_md', metavar='source.md',
                        help='Markdown file to render with pandoc + weasyprint')
    parser.add_argument('baseline_pdf', metavar='baseline.pdf',
                        help='Reference PDF to compare against (golden file)')
    parser.add_argument('--update-baseline', action='store_true',
                        help='Overwrite baseline.pdf with the freshly rendered output')
    args = parser.parse_args()

    source = Path(args.source_md)
    baseline = Path(args.baseline_pdf)

    if not source.exists():
        sys.exit(f'Not found: {source}')
    if not args.update_baseline and not baseline.exists():
        sys.exit(f'Not found: {baseline}')

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        rendered = Path(tmp.name)

    try:
        render(source, rendered)

        if args.update_baseline:
            shutil.copy2(rendered, baseline)
            print(f'Baseline updated: {baseline}')
            print(f'  md5: {md5(baseline)}')
        else:
            expected = md5(baseline)
            actual = md5(rendered)
            if expected == actual:
                print(f'OK  {baseline}')
            else:
                print(f'FAIL: rendered PDF does not match baseline', file=sys.stderr)
                print(f'  expected: {expected}  ({baseline})', file=sys.stderr)
                print(f'  actual:   {actual}  ({source})', file=sys.stderr)
                sys.exit(1)
    finally:
        rendered.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
