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


def write_if_absent(path, content):
    """Write content to path only if the file does not already exist.

    Returns True if the file was written, False if it was skipped.
    """
    if os.path.exists(path):
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    return True


def append_if_marker_absent(path, marker, content):
    """Append content to path if marker is not already present in the file.

    Creates the file (and parent directories) if it does not exist.
    Returns True if content was written, False if marker was already present.
    """
    if os.path.exists(path):
        with open(path) as f:
            if marker in f.read():
                return False
        with open(path, 'a') as f:
            f.write(content)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
    return True


# ── templates ─────────────────────────────────────────────────────────────────

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

# Placed in .claude/skills/rfc/SKILL.md.
# The description field drives Claude Code auto-invocation; keep it specific.
CLAUDE_SKILL = """\
---
description: >
  Help write, draft, or review a technical RFC document. Use when the user
  asks to create, improve, or critique an RFC, or when editing a file that
  follows the RFC template structure (Abstract, Motivation, Proposal, …).
arguments:
  - topic
---

Help the user write or improve a technical RFC. $ARGUMENTS

## Approach

1. If a topic or partial draft is provided, identify what is missing before
   writing. Ask for context you do not have rather than inventing it.
2. Challenge vague requirements — imprecision in specs causes implementation
   drift downstream.
3. Once all sections are present, review each for completeness and precision.

## Required structure

Every RFC MUST contain all six sections in this order:

| Section | Purpose |
|---|---|
| **Abstract** | One-paragraph overview — write this last |
| **Motivation** | The problem, who it affects, and why it matters now; include data or examples |
| **Proposal** | The specification; use RFC 2119 keywords for all requirements |
| **Drawbacks** | Honest trade-offs — reviewers will raise these regardless |
| **Alternatives** | Rejected designs and the reasons — prevents "why not X?" in review |
| **Security Considerations** | Never omit; if genuinely none, justify that explicitly |

## RFC 2119 requirement keywords

Use these precisely to eliminate ambiguity. Flag any requirement expressed
as "should", "needs to", "has to", or "we want" — it is almost certainly
a MUST or SHOULD that needs to be made explicit.

| Keyword | Meaning |
|---|---|
| MUST / MUST NOT | Absolute requirement; no exceptions permitted |
| SHOULD / SHOULD NOT | Strong recommendation; exceptions require explicit justification |
| MAY / OPTIONAL | Genuinely discretionary behaviour |

## Quality checklist

Before considering an RFC complete, verify:

- **Scope**: Is it narrow enough to be adopted? Large multi-part proposals
  fail significantly more often than focused ones.
- **Motivation**: Does it answer what is broken today, and what success
  looks like after adoption?
- **Alternatives**: Is every plausible alternative documented with a reason
  for rejection?
- **Security Considerations**: Is it substantive, not boilerplate?
- **Readability**: Would an engineer unfamiliar with the problem understand
  the Proposal well enough to implement it correctly?
"""

# Marker used to detect whether the RFC block is already present in the
# Copilot instructions file, so re-running bootstrap does not duplicate it.
COPILOT_MARKER = '<!-- rfc-tools -->'

# Appended to (or used to create) .github/copilot-instructions.md.
COPILOT_INSTRUCTIONS = """\
{marker}
## RFC Authoring

This repository contains technical RFCs authored with rfc-tools.

**Required sections** (in order): Abstract, Motivation, Proposal, Drawbacks,
Alternatives, Security Considerations.

**Requirement language** follows RFC 2119:

| Keyword | Meaning |
|---|---|
| MUST / MUST NOT | Absolute requirement — no exceptions |
| SHOULD / SHOULD NOT | Strong recommendation — exceptions need justification |
| MAY / OPTIONAL | Discretionary behaviour |

**When reviewing or editing RFC files:**

- Suggest RFC 2119 keywords wherever requirements are expressed imprecisely
  ("should", "needs to", "has to", "we want").
- Flag any missing sections from the required list above.
- Challenge proposals that have no documented alternatives — ask what else
  was considered and why it was rejected.
- Security Considerations MUST NOT be left empty; prompt the author to
  justify why none apply if they believe that is the case.
- Prefer narrow scope: smaller, focused RFCs have significantly higher
  adoption rates than large multi-part documents.

**Bootstrapping:** Run `rfc bootstrap "Title"` inside the rfc-tools container
to create a pre-filled RFC skeleton with today's date and git author.
""".format(marker=COPILOT_MARKER)


# ── agent scaffolding ─────────────────────────────────────────────────────────

def scaffold_agent_files(directory, force=False):
    """Create agent skill files under directory.

    Without force, existing files are left untouched. With force, every file
    is regenerated from its template.

    Returns a list of (path, action) tuples where action is 'created' or
    'skipped'.
    """
    results = []

    claude_path = os.path.join(directory, '.claude', 'skills', 'rfc', 'SKILL.md')
    if force:
        os.makedirs(os.path.dirname(claude_path), exist_ok=True)
        with open(claude_path, 'w') as f:
            f.write(CLAUDE_SKILL)
        action = 'created'
    else:
        action = 'created' if write_if_absent(claude_path, CLAUDE_SKILL) else 'skipped'
    results.append((claude_path, action))

    copilot_path = os.path.join(directory, '.github', 'copilot-instructions.md')
    if force:
        os.makedirs(os.path.dirname(copilot_path), exist_ok=True)
        with open(copilot_path, 'w') as f:
            f.write(COPILOT_INSTRUCTIONS)
        action = 'created'
    else:
        action = 'created' if append_if_marker_absent(
            copilot_path, COPILOT_MARKER, COPILOT_INSTRUCTIONS,
        ) else 'skipped'
    results.append((copilot_path, action))

    return results


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_bootstrap(args):
    today = datetime.date.today().isoformat()
    author = git_user()
    title = args.title or 'Untitled RFC'
    number = next_rfc_number()

    if args.output:
        rfc_path = args.output
    else:
        rfc_path = f'{number:04d}-{slugify(title)}.md'

    if os.path.exists(rfc_path) and not args.force:
        sys.exit(f'error: {rfc_path} already exists (use --force to overwrite)')

    content = RFC_TEMPLATE.format(
        number=number,
        title=title,
        author=author,
        date=today,
    )

    with open(rfc_path, 'w') as f:
        f.write(content)
    print(f'Created {rfc_path}')

    cwd = os.path.dirname(os.path.abspath(rfc_path))
    for path, action in scaffold_agent_files(cwd, force=args.force):
        rel = os.path.relpath(path, cwd)
        print(f'{"Created" if action == "created" else "Skipped"} {rel}')


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
