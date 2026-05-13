#!/usr/bin/env bash
# publish.sh — validate, commit, tag, and push in one step.
# Run --help for usage.
set -euo pipefail

usage() {
    cat <<'EOF'
publish.sh — build tests locally, then commit, tag, and push

Targets agents: run this after making changes to validate and release in a
single step. The Docker test suite must pass before anything is committed or
pushed. If the build fails, staged changes are rolled back and nothing is
written to the remote.

Usage:
  ./publish.sh <message> <tag>

Arguments:
  message   Commit message and tag annotation (quote multi-word strings)
  tag       Semver tag: vMAJOR.MINOR.PATCH

Semver rules (from agents.md):
  MAJOR  Breaking change to the public interface or tool removal
  MINOR  New tool, file, feature, or flag — anything additive
  PATCH  Bug fix or correction to existing behaviour or content

Examples:
  ./publish.sh "Add rate-limit RFC template" v1.6.0
  ./publish.sh "Fix typo in rfc.css" v1.5.1
EOF
}

# ── argument validation ───────────────────────────────────────────────────────

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage; exit 0
fi

MESSAGE="${1:-}"
TAG="${2:-}"

if [[ -z "$MESSAGE" || -z "$TAG" ]]; then
    usage; exit 1
fi

if ! [[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "error: tag must be vMAJOR.MINOR.PATCH (got: $TAG)" >&2; exit 1
fi

if git tag | grep -qx "$TAG"; then
    echo "error: tag $TAG already exists" >&2; exit 1
fi

# ── stage ─────────────────────────────────────────────────────────────────────

git add -A

if git diff --cached --quiet; then
    NEEDS_COMMIT=0
    echo "Nothing new to stage — will tag current HEAD."
else
    NEEDS_COMMIT=1
    echo "==> Staged changes:"
    git diff --cached --stat
fi

# Roll back staged changes if anything below fails.
rollback() {
    local code=$?
    if [[ $code -ne 0 ]]; then
        echo "" >&2
        echo "error: rolling back staged changes." >&2
        git reset >/dev/null 2>&1 || true
    fi
}
trap rollback EXIT

# ── build and test ────────────────────────────────────────────────────────────

echo ""
echo "==> Building Docker test target..."
if ! docker build --target test --progress=plain .; then
    echo "" >&2
    echo "error: tests failed — nothing was committed or pushed." >&2
    exit 1
fi

# ── commit, tag, push ─────────────────────────────────────────────────────────

echo ""
echo "==> Tests passed."

if [[ "$NEEDS_COMMIT" == "1" ]]; then
    git commit -m "$MESSAGE

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
    echo "Committed: $(git log -1 --oneline)"
fi

git tag "$TAG" -m "$MESSAGE"
echo "Tagged:    $TAG"

git push origin main
git push origin "$TAG"

echo ""
echo "Published $TAG — $(git log -1 --oneline)"
