#!/usr/bin/env python3
"""rfc — entry-point tool for managing RFCs."""

import argparse
import datetime
import os
import re
import subprocess
import sys


# ── helpers ───────────────────────────────────────────────────────────────────

def git_user():
    """Return git config user.name, falling back to $USER then 'Unknown'."""
    try:
        result = subprocess.run(
            ['git', 'config', 'user.name'],
            capture_output=True, text=True, check=True,
        )
        name = result.stdout.strip()
        if name:
            return name
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return os.environ.get('USER', 'Unknown')


def slugify(title):
    """Convert a title to a lowercase-hyphenated slug suitable for filenames."""
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def next_rfc_number(directory='.'):
    """Scan directory for NNNN-*.md files and return the next sequential number."""
    pattern = re.compile(r'^(\d{4})-.*\.md$')
    numbers = []
    for name in os.listdir(directory):
        m = pattern.match(name)
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers, default=0) + 1


# ── template ──────────────────────────────────────────────────────────────────

RFC_TEMPLATE = """\
---
RFC: {number:04d}
Title: {title}
Author: {author}
Date: {date}
Status: Draft
---

# {title}

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be
interpreted as described in [RFC 2119].

## Abstract

<!--
One paragraph. State what is being proposed and why. Write this last —
it is easier to summarise once the rest of the document is complete.
-->

## Motivation

<!--
Why is this change necessary? What problem does it solve, and for whom?
Include concrete examples or data where available.

A good motivation section answers: what breaks or is painful today,
and what does success look like after this RFC is adopted?
-->

## Proposal

<!--
The core specification. Describe the solution in enough detail that an
engineer unfamiliar with the problem could implement it correctly.

Use RFC 2119 keywords for requirements that must be unambiguous:
  - MUST / MUST NOT    — absolute requirements
  - SHOULD / SHOULD NOT — strong recommendations with valid exceptions
  - MAY / OPTIONAL     — genuinely discretionary behaviour

Keep scope narrow. Smaller, tightly scoped proposals have a significantly
higher chance of adoption than large multi-part documents.
-->

## Drawbacks

<!--
Known downsides, costs, or trade-offs introduced by this proposal.
Be honest — reviewers will raise these anyway, and addressing them here
builds trust. Consider: complexity, performance, migration burden,
operational overhead, and impact on other teams.
-->

## Alternatives

<!--
Other designs considered and why they were not chosen.
This prevents "why didn't we just do X?" during review and preserves
the reasoning for future readers who may re-open the question.
-->

## Security Considerations

<!--
Describe any security implications of this proposal.
Authors MUST NOT knowingly omit foreseen risks or threats.
Consider: authentication, authorisation, data exposure, injection,
denial of service, and supply-chain concerns.

If there are genuinely no security implications, state that explicitly
with a brief justification rather than leaving this section empty.
-->

## References

- [RFC 2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement
  Levels", BCP 14, RFC 2119, March 1997.
  <https://www.rfc-editor.org/rfc/rfc2119>
"""


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_bootstrap(args):
    today = datetime.date.today().isoformat()
    author = git_user()
    title = args.title or 'Untitled RFC'
    number = next_rfc_number()

    if args.output:
        path = args.output
    else:
        path = f'{number:04d}-{slugify(title)}.md'

    if os.path.exists(path) and not args.force:
        sys.exit(f'error: {path} already exists (use --force to overwrite)')

    content = RFC_TEMPLATE.format(
        number=number,
        title=title,
        author=author,
        date=today,
    )

    with open(path, 'w') as f:
        f.write(content)

    print(f'Created {path}')


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog='rfc',
        description='Entry-point tool for managing RFCs.',
    )
    sub = parser.add_subparsers(dest='command', metavar='COMMAND')

    bp = sub.add_parser('bootstrap', help='Create a new RFC from the standard template.')
    bp.add_argument('title', nargs='?', metavar='TITLE',
                    help='RFC title. Used to derive the output filename.')
    bp.add_argument('-o', '--output', metavar='FILE',
                    help='Write to FILE instead of the auto-generated NNNN-slug.md.')
    bp.add_argument('--force', action='store_true',
                    help='Overwrite the output file if it already exists.')
    bp.set_defaults(func=cmd_bootstrap)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == '__main__':
    main()
