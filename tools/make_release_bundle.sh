#!/usr/bin/env bash
# Build a self-contained full-source ZIP of PocketQuake + its submodules.
#
# WHY: GitHub's auto-generated "Download ZIP" of a superproject contains EMPTY
# submodule directories, so users without git (notably on Windows) cannot get a
# runnable tree that way (user request via issue reporter, 2026-08).
#
# WHAT'S EXCLUDED: korea-cluster-relocation's pipeline/notebooks/*.ipynb — these
# are ~700 MB of GENERATED per-cluster result notebooks (the pipeline recreates
# them on every run; browse them on GitHub instead). Everything else tracked in
# the three repos is included. No symlinks are tracked, so the ZIP is
# Windows-safe.
#
# Usage: tools/make_release_bundle.sh [output.zip]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="$(git -C "$ROOT" describe --tags --always)"
OUT="${1:-$ROOT/PocketQuake-$VER-full-source.zip}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

git -C "$ROOT" archive --format=tar HEAD | tar -x -C "$STAGE"
for SM in external/korea-cluster-relocation external/necis-downloader; do
    SHA="$(git -C "$ROOT" ls-tree HEAD "$SM" | awk '{print $3}')"
    mkdir -p "$STAGE/$SM"
    git -C "$ROOT/$SM" archive --format=tar "$SHA" | tar -x -C "$STAGE/$SM"
done
# prune the generated result notebooks (see header)
find "$STAGE/external/korea-cluster-relocation/pipeline/notebooks" -name "*.ipynb" -delete

{
  echo "PocketQuake full-source bundle  $VER  ($(date -u +%F))"
  echo "superproject: $(git -C "$ROOT" rev-parse HEAD)"
  for SM in external/korea-cluster-relocation external/necis-downloader; do
      echo "$SM: $(git -C "$ROOT" ls-tree HEAD "$SM" | awk '{print $3}')"
  done
  echo
  echo "Generated result notebooks (external/korea-cluster-relocation/pipeline/"
  echo "notebooks/*.ipynb, ~700 MB) are excluded; the pipeline regenerates them,"
  echo "and the committed versions can be browsed on GitHub."
  echo "Install: see docs/INSTALL.md (identical to a git checkout from here on)."
} > "$STAGE/BUNDLE_INFO.txt"

( cd "$STAGE" && zip -qr "$OUT" . )
echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
