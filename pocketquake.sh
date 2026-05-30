#!/usr/bin/env bash
# pocketquake.sh — catalog CSV → relocation summary notebook in one command.
#
# USAGE
#   ./pocketquake.sh CATALOG SLUG [options]
#
# OPTIONS
#   --epi LAT,LON                   override the auto-derived epicenter (catalog centroid)
#   --bounds LAT0,LAT1,LON0,LON1    override the auto-derived bounds (catalog bbox + 0.2°)
#   --picker {phasenet_plus|stead}  picker model (default: phasenet_plus)
#   --mainshock UTC_YYYYMMDDHHMMSS  also run Gwangyang-style mainshock treatment after the
#                                   default pipeline (re-runs xcorr→dtcc, builds a _main notebook)
#   --fg                            run in foreground (default: nohup background)
#   -h, --help                      show this and exit
#
# EXAMPLES
#   # 1. default run, auto-derived epi/bounds, background:
#   ./pocketquake.sh ~/catalogs/myswarm.csv myswarm
#
#   # 2. with explicit epicenter + bounds + mainshock treatment, foreground:
#   ./pocketquake.sh ~/catalogs/myswarm.csv myswarm \
#       --epi 35.46,128.43 --bounds 35.3,35.65,128.25,128.65 \
#       --mainshock 20240912144719 --fg
#
# OUTPUT
#   external/korea-cluster-relocation/pipeline/notebooks/03_results_<slug>.ipynb
#   (+ 03_results_<slug>_main.ipynb if --mainshock is given)

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=/home/msseo/miniforge3/envs/pipeline/bin/python
EQDIR="$HERE/external/korea-cluster-relocation"
EXISTING=(gwangyang kimcheon jangsung gyeongju changnyeong)

usage(){ cat <<'EOF'
pocketquake.sh — catalog CSV → relocation summary notebook in one command.

USAGE
  ./pocketquake.sh CATALOG SLUG [options]

OPTIONS
  --epi LAT,LON                   override the auto-derived epicenter (catalog centroid)
  --bounds LAT0,LAT1,LON0,LON1    override the auto-derived bounds (catalog bbox + 0.2°)
  --picker {phasenet_plus|stead}  picker model (default: phasenet_plus)
  --mainshock UTC_YYYYMMDDHHMMSS  also run Gwangyang-style mainshock treatment after the
                                  default pipeline (re-runs xcorr→dtcc, builds a _main notebook)
  --fg                            run in foreground (default: nohup background)
  -h, --help                      show this and exit

EXAMPLES
  # 1. default run, auto-derived epi/bounds, background:
  ./pocketquake.sh ~/catalogs/myswarm.csv myswarm

  # 2. with explicit epicenter + bounds + mainshock treatment, foreground:
  ./pocketquake.sh ~/catalogs/myswarm.csv myswarm \
      --epi 35.46,128.43 --bounds 35.3,35.65,128.25,128.65 \
      --mainshock 20240912144719 --fg

OUTPUT
  external/korea-cluster-relocation/pipeline/notebooks/03_results_<slug>.ipynb
  (+ 03_results_<slug>_main.ipynb if --mainshock is given)
EOF
exit "${1:-0}"; }
fail(){ echo "✗ $*" >&2; exit 1; }
ok(){ echo "  ✓ $*"; }
hdr(){ echo; echo "▸ $*"; }

# ---- arguments ----
[[ $# -lt 2 ]] && usage 1
CATALOG="$1"; SLUG="$2"; shift 2
EPI=""; BBOX=""; PICKER="phasenet_plus"; MAINSHOCK=""; FG=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --epi)             EPI="$2"; shift 2 ;;
        --bounds)          BBOX="$2"; shift 2 ;;
        --picker)          PICKER="$2"; shift 2 ;;
        --mainshock)       MAINSHOCK="$2"; shift 2 ;;
        --fg|--foreground) FG=1; shift ;;
        -h|--help)         usage 0 ;;
        *) fail "unknown option: $1" ;;
    esac
done

# ---- preflight ----
hdr "preflight"
[[ -f "$CATALOG" ]] || fail "catalog not found: $CATALOG"
hdrline=$(head -1 "$CATALOG")
for c in Year Month Day Hour Minute Second Latitude Longitude Magnitude Depth; do
    [[ "$hdrline" == *"$c"* ]] || fail "catalog header missing '$c'"
done
ok "catalog: $CATALOG"

for c in "${EXISTING[@]}"; do
    [[ "$SLUG" == "$c" ]] && fail "slug '$SLUG' collides with an existing cluster (${EXISTING[*]})"
done
ok "slug: $SLUG"

[[ -f "$HERE/.env" ]] || fail "missing $HERE/.env (set NECIS_USER and NECIS_PASS)"
set -a; . "$HERE/.env"; set +a
[[ -n "${NECIS_USER:-}" ]] || fail ".env loaded but NECIS_USER is empty"
ok "NECIS credentials loaded ($NECIS_USER)"

[[ -x "$PY" ]] || fail "python env not found: $PY"
ok "python: $PY"

# ---- auto-derive epi / bbox from the catalog ----
if [[ -z "$EPI" || -z "$BBOX" ]]; then
    read -r EPI_AUTO BBOX_AUTO NEV MAGS YRS < <(
        "$PY" - "$CATALOG" <<'PY'
import sys, pandas as pd
d = pd.read_csv(sys.argv[1])
pad = 0.2
print(f"{d.Latitude.mean():.3f},{d.Longitude.mean():.3f}",
      f"{d.Latitude.min()-pad:.3f},{d.Latitude.max()+pad:.3f},{d.Longitude.min()-pad:.3f},{d.Longitude.max()+pad:.3f}",
      f"{len(d)}",
      f"M{d.Magnitude.min():.1f}-{d.Magnitude.max():.1f}",
      f"{int(d.Year.min())}-{int(d.Year.max())}")
PY
    )
    [[ -z "$EPI" ]] && EPI="$EPI_AUTO"
    [[ -z "$BBOX" ]] && BBOX="$BBOX_AUTO"
    ok "$NEV events, $MAGS, $YRS"
fi
ok "epicenter:   $EPI"
ok "region-bbox: $BBOX"
ok "picker:      $PICKER"
[[ -n "$MAINSHOCK" ]] && ok "mainshock:   $MAINSHOCK (treatment will be applied after default run)"

# ---- the orchestrator command ----
CMD=(
    "$PY" -u -m pocketquake.orchestrate "$CATALOG"
    --cluster "$SLUG"
    --epicenter "$EPI"
    --region-bounds "$BBOX"
    --picker "$PICKER"
)
LOG="$HERE/${SLUG}_run.log"

cd "$HERE"
hdr "launching default pipeline (log: $LOG)"
if [[ "$FG" == "1" ]]; then
    "${CMD[@]}" 2>&1 | tee "$LOG"
    DEFAULT_RC="${PIPESTATUS[0]}"
    [[ "$DEFAULT_RC" == "0" ]] || fail "default pipeline failed (exit $DEFAULT_RC)"
elif [[ -z "$MAINSHOCK" ]]; then
    # fire-and-forget background
    nohup "${CMD[@]}" > "$LOG" 2>&1 &
    PID=$!
    echo "  background pid=$PID  —  tail -f $LOG  (kill $PID to stop)"
    echo
    echo "When the run finishes, open:"
    echo "  jupyter lab $EQDIR/pipeline/notebooks/03_results_${SLUG}.ipynb"
    exit 0
else
    # background but wait for it so we can chain the mainshock step
    "${CMD[@]}" > "$LOG" 2>&1 &
    PID=$!
    echo "  pid=$PID (chaining mainshock treatment after it finishes)"
    echo "  follow:  tail -f $LOG"
    wait "$PID" || fail "default pipeline failed (exit $?); check $LOG"
fi

# ---- optional mainshock treatment ----
if [[ -n "$MAINSHOCK" ]]; then
    hdr "applying Gwangyang-style mainshock treatment ($MAINSHOCK)"
    CLUSTER_PY="$EQDIR/pipeline/clusters/${SLUG}.py"
    NB_DEFAULT="$EQDIR/pipeline/notebooks/03_results_${SLUG}.ipynb"
    NB_MAIN="$EQDIR/pipeline/notebooks/03_results_${SLUG}_main.ipynb"
    DTCC_DIR="$EQDIR/pipeline/runs/${SLUG}/2.HypoDD/02.dt.cc"

    # snapshot the untreated dt.cc + duplicate the default notebook
    cp "$DTCC_DIR/hypoDD.reloc" "$DTCC_DIR/hypoDD.reloc.untreated"
    cp "$NB_DEFAULT" "$NB_MAIN"
    ok "snapshot saved (.untreated + ${SLUG}_main.ipynb)"

    # patch the cluster .py to add mainshock_event_id + xcorr_pair_overrides (idempotent)
    "$PY" - "$CLUSTER_PY" "$MAINSHOCK" <<'PY'
import sys, re
path, eid = sys.argv[1], sys.argv[2]
src = open(path).read()
if "mainshock_event_id=" not in src:
    src = re.sub(r"(dtct_isolv=\d+,)\s*\)",
                 fr'\1\n    mainshock_event_id="{eid}",\n)',
                 src, count=1)
if "xcorr_pair_overrides" not in src:
    src += (
        "\n\nfrom dataclasses import replace\n"
        f'CONFIG = replace(CONFIG, xcorr_pair_overrides={{\n'
        f'    frozenset({{"{eid}"}}): dict(pre=0.05, post=0.05, bandpass=(1, 40)),\n'
        "}})\n"
    )
open(path, "w").write(src)
print("patched", path)
PY

    # re-run xcorr → dtcc only (everything upstream is unchanged)
    hdr "re-running xcorr → dtcc with mainshock treatment"
    PYTHONPATH="$EQDIR" taskset -c 0-7 "$PY" -m pipeline.cli.run_pipeline \
        --cluster "$SLUG" --picker "$PICKER" --stage-from xcorr --through dtcc \
        2>&1 | tee -a "$LOG"

    # add a header to the _main notebook + clear stale outputs, then execute it
    "$PY" - "$NB_MAIN" "$MAINSHOCK" "$SLUG" <<'PY'
import json, sys
nb_path, eid, slug = sys.argv[1], sys.argv[2], sys.argv[3]
nb = json.load(open(nb_path))
note = (
    "# Mainshock-treated relocation (Gwangyang style)\n\n"
    f"`mainshock_event_id=\"{eid}\"` plus `xcorr_pair_overrides` (±0.05 s window, 1–40 Hz band) "
    "for pairs involving the mainshock — preventing its longer source duration from dominating "
    f"the alignment of the smaller events. See `03_results_{slug}.ipynb` for the untreated reloc.\n"
)
hdr = {"cell_type": "markdown", "metadata": {}, "source": note.splitlines(keepends=True)}
nb["cells"] = nb["cells"][:1] + [hdr] + nb["cells"][1:]
for c in nb["cells"]:
    if c.get("cell_type") == "code":
        c["outputs"] = []; c["execution_count"] = None
json.dump(nb, open(nb_path, "w"), indent=1)
print("notebook prepared:", nb_path)
PY
    hdr "executing $NB_MAIN"
    "$PY" -m jupyter nbconvert --to notebook --execute --inplace \
        --ExecutePreprocessor.timeout=1800 "$NB_MAIN" 2>&1 | tee -a "$LOG"
    ok "mainshock-treated notebook ready"
fi

hdr "done — open the notebook(s):"
echo "  jupyter lab $EQDIR/pipeline/notebooks/03_results_${SLUG}.ipynb"
[[ -n "$MAINSHOCK" ]] && \
echo "  jupyter lab $EQDIR/pipeline/notebooks/03_results_${SLUG}_main.ipynb     (mainshock-treated)"
