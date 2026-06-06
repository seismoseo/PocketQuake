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
#   --cores N                       cap xcorr workers (forwarded as --cores N to the eq-cycle
#                                   CLI; default: each cluster's cfg.num_cores, typically 10)
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
# Python interpreter: respect POCKETQUAKE_PYTHON if set; otherwise fall back to whichever
# python is on PATH. Override via env var when you want a specific conda/venv interpreter.
PY="${POCKETQUAKE_PYTHON:-$(command -v python3 || command -v python || true)}"
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
  --python                        shortcut for the pure-Python pipeline:
                                  = --loc-backend hyposvi --reloc-backend relocdd_py.
                                  Uses bundled EikoNet weights (fetch once with
                                  `python -m pipeline.core.fetch_eikonet`).
  --compare                       run the default (Fortran) pipeline, then re-run the
                                  Python backend on the SAME picks and build an executed
                                  04_compare_<slug>.ipynb (HYPOINVERSE vs HypoSVI and
                                  ff vs pp, abs + final). Implies --fg.
  --loc-backend {hypoinverse|hyposvi}
                                  absolute-location backend (default: hypoinverse, Fortran hyp1.40).
                                  hyposvi is the pure-Python path; uses a trained EikoNet
                                  (bundled/auto-discovered, or HYPOSVI_EIKONET_P/S in .env).
  --reloc-backend {hypodd|relocdd_py}
                                  relative-relocation backend (default: hypodd, Fortran ph2dt+hypoDD).
                                  relocdd_py is the pure-Python port; set RELOCDD_PY_DIR in .env.
  --source {necis|stp|mixed}      waveform source (default: necis). `mixed` dispatches
                                  per-event between STP and NECIS so a single cluster can span
                                  the STP/NECIS transition; default mode is try-STP-first with
                                  NECIS fallback for every event.
  --stp-cutoff YYYY-MM-DD         only with --source mixed: events with UTC origin >= this date
                                  skip STP and go straight to NECIS (saves a failed STP round-trip
                                  per known-late event). Omit to use the try-then-fallback default.
  --mainshock UTC_YYYYMMDDHHMMSS  also run Gwangyang-style mainshock treatment after the
                                  default pipeline (re-runs xcorr→dtcc, builds a _main notebook)
  --mainshock-only                skip the default pipeline pass (it must already be complete)
                                  and run ONLY the mainshock treatment + _main notebook —
                                  useful for re-running treatment on an existing cluster
                                  without redoing scaffold / download / picking / location.
                                  Requires --mainshock.
  --skip-download                 skip the waveform-download stage (waveforms already on disk).
                                  Useful for resuming a run after the downloads finished but
                                  before the pipeline started.
  --skip-pipeline                 skip the eq-cycle relocation chain AND the results notebook
                                  (download + scaffold only — for testing the fetch paths).
  --cores N                       cap xcorr workers (forwarded to the eq-cycle CLI's --cores;
                                  default: each cluster's cfg.num_cores, typically 10). Set lower
                                  on memory-constrained boxes (~24 GB/worker observed).
  --fg                            run in foreground (default: nohup background)
  -h, --help                      show this and exit

EXAMPLES
  # 1. default run, auto-derived epi/bounds, background:
  ./pocketquake.sh ~/catalogs/myswarm.csv myswarm

  # 2. with explicit epicenter + bounds + mainshock treatment, foreground:
  ./pocketquake.sh ~/catalogs/myswarm.csv myswarm \
      --epi 35.46,128.43 --bounds 35.3,35.65,128.25,128.65 \
      --mainshock 20240912144719 --fg

  # 3. limit xcorr to 6 workers (memory-constrained box):
  ./pocketquake.sh ~/catalogs/myswarm.csv myswarm --cores 6 --fg

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
EPI=""; BBOX=""; PICKER="phasenet_plus"; MAINSHOCK=""; FG=0; SOURCE="necis"; MAIN_ONLY=0; CORES=""; STP_CUTOFF=""
LOC_BACKEND="hypoinverse"; RELOC_BACKEND="hypodd"; LOC_SET=0; RELOC_SET=0; PYTHON_SHORTCUT=0; COMPARE=0
SKIP_DOWNLOAD=0; SKIP_PIPELINE=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --epi)             EPI="$2"; shift 2 ;;
        --bounds)          BBOX="$2"; shift 2 ;;
        --picker)          PICKER="$2"; shift 2 ;;
        --loc-backend)     LOC_BACKEND="$2"; LOC_SET=1; shift 2 ;;
        --reloc-backend)   RELOC_BACKEND="$2"; RELOC_SET=1; shift 2 ;;
        --python)          PYTHON_SHORTCUT=1; shift ;;
        --compare)         COMPARE=1; shift ;;
        --source)          SOURCE="$2"; shift 2 ;;
        --stp-cutoff)      STP_CUTOFF="$2"; shift 2 ;;
        --mainshock)       MAINSHOCK="$2"; shift 2 ;;
        --mainshock-only)  MAIN_ONLY=1; shift ;;
        --skip-download)   SKIP_DOWNLOAD=1; shift ;;
        --skip-pipeline)   SKIP_PIPELINE=1; shift ;;
        --cores)           CORES="$2"; shift 2 ;;
        --fg|--foreground) FG=1; shift ;;
        -h|--help)         usage 0 ;;
        *) fail "unknown option: $1" ;;
    esac
done
[[ "$SOURCE" == "necis" || "$SOURCE" == "stp" || "$SOURCE" == "mixed" ]] || fail "--source must be 'necis' | 'stp' | 'mixed' (got: $SOURCE)"
[[ -n "$STP_CUTOFF" && "$SOURCE" != "mixed" ]] && fail "--stp-cutoff is only meaningful with --source mixed (got --source $SOURCE)"
[[ "$MAIN_ONLY" == "1" && -z "$MAINSHOCK" ]] && fail "--mainshock-only requires --mainshock UTC_YYYYMMDDHHMMSS"
# --python = pure-Python backends shortcut (= --loc-backend hyposvi --reloc-backend relocdd_py)
if [[ "$PYTHON_SHORTCUT" == "1" ]]; then
    [[ "$LOC_SET" == "1" && "$LOC_BACKEND" != "hyposvi" ]] && fail "--python implies --loc-backend hyposvi, conflicting with --loc-backend $LOC_BACKEND"
    [[ "$RELOC_SET" == "1" && "$RELOC_BACKEND" != "relocdd_py" ]] && fail "--python implies --reloc-backend relocdd_py, conflicting with --reloc-backend $RELOC_BACKEND"
    LOC_BACKEND="hyposvi"; RELOC_BACKEND="relocdd_py"
fi
# --compare runs the DEFAULT (Fortran) pipeline then re-runs the Python backend on the
# same picks, so it cannot itself be a Python run; it also needs the full default pass.
if [[ "$COMPARE" == "1" ]]; then
    [[ "$PYTHON_SHORTCUT" == "1" || "$LOC_BACKEND" == "hyposvi" || "$RELOC_BACKEND" == "relocdd_py" ]] && \
        fail "--compare runs the Fortran pipeline then compares the Python one — don't combine it with --python / --loc-backend hyposvi / --reloc-backend relocdd_py"
    [[ "$MAIN_ONLY" == "1" ]] && fail "--compare is incompatible with --mainshock-only"
    [[ "$SKIP_PIPELINE" == "1" ]] && fail "--compare needs the pipeline outputs; drop --skip-pipeline"
    FG=1   # sequence the comparison after the pipeline
fi
[[ "$LOC_BACKEND" == "hypoinverse" || "$LOC_BACKEND" == "hyposvi" ]] || fail "--loc-backend must be 'hypoinverse' | 'hyposvi' (got: $LOC_BACKEND)"
[[ "$RELOC_BACKEND" == "hypodd" || "$RELOC_BACKEND" == "relocdd_py" ]] || fail "--reloc-backend must be 'hypodd' | 'relocdd_py' (got: $RELOC_BACKEND)"

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

[[ -f "$HERE/.env" ]] || fail "missing $HERE/.env (set NECIS_USER/NECIS_PASS for --source necis, STP_USER/STP_PASS for --source stp; mixed needs BOTH)"
set -a; . "$HERE/.env"; set +a
case "$SOURCE" in
    stp)
        [[ -n "${STP_USER:-}" && -n "${STP_PASS:-}" ]] || fail ".env loaded but STP_USER/STP_PASS missing (needed for --source stp)"
        ok "STP credentials loaded ($STP_USER)"
        ;;
    mixed)
        [[ -n "${STP_USER:-}" && -n "${STP_PASS:-}" ]] || fail ".env loaded but STP_USER/STP_PASS missing (mixed needs both backends)"
        [[ -n "${NECIS_USER:-}" ]] || fail ".env loaded but NECIS_USER is empty (mixed needs both backends)"
        ok "STP+NECIS credentials loaded (STP=$STP_USER, NECIS=$NECIS_USER)"
        ;;
    *)
        [[ -n "${NECIS_USER:-}" ]] || fail ".env loaded but NECIS_USER is empty"
        ok "NECIS credentials loaded ($NECIS_USER)"
        ;;
esac

# ---- Python relocation-backend preflight (opt-in; default Fortran path skips these) ----
# --compare also needs the Python backends (it re-runs pp on the same picks).
if [[ "$RELOC_BACKEND" == "relocdd_py" || "$COMPARE" == "1" ]]; then
    [[ -n "${RELOCDD_PY_DIR:-}" ]] || fail "Python relocation needs RELOCDD_PY_DIR in .env (path to the relocDD-py clone)"
    [[ -f "$RELOCDD_PY_DIR/run.py" ]] || fail "RELOCDD_PY_DIR=$RELOCDD_PY_DIR has no run.py — is it a relocDD-py clone?"
    ok "relocDD-py: $RELOCDD_PY_DIR"
fi
if [[ "$LOC_BACKEND" == "hyposvi" || "$COMPARE" == "1" ]]; then
    if [[ -n "${HYPOSVI_EIKONET_P:-}" && -n "${HYPOSVI_EIKONET_S:-}" ]]; then
        [[ -e "$HYPOSVI_EIKONET_P" ]] || fail "HYPOSVI_EIKONET_P=$HYPOSVI_EIKONET_P not found"
        [[ -e "$HYPOSVI_EIKONET_S" ]] || fail "HYPOSVI_EIKONET_S=$HYPOSVI_EIKONET_S not found"
        ok "HypoSVI EikoNet (env): P=$HYPOSVI_EIKONET_P"
    else
        # bundled auto-discovery: any eikonet_<vm>/<vm>_p with a meta.json + checkpoint
        BUNDLED_META=$(ls "$EQDIR"/pipeline/velocity_models/eikonet_*/*_p/eikonet_meta.json 2>/dev/null | head -1)
        [[ -n "$BUNDLED_META" ]] || fail "--loc-backend hyposvi: no EikoNet weights found. Fetch the bundled weights:
    (cd $EQDIR && python -m pipeline.core.fetch_eikonet)
  or set HYPOSVI_EIKONET_P / HYPOSVI_EIKONET_S in .env. See docs/python_backend/README.md."
        ok "HypoSVI EikoNet: bundled weights present ($(ls -d "$EQDIR"/pipeline/velocity_models/eikonet_* 2>/dev/null | xargs -n1 basename | tr '\n' ' '))"
    fi
    # The HypoSVI SVGD locator + EikoNet Model class are external clones (not the weights) —
    # needed to load the network. Check them up front so we fail here, not with an ImportError
    # after download+picking.
    EK_PATHS="${EIKONET_DIR:-}:${HYPOSVI_DIR:-}"
    if ! PYTHONPATH="$EK_PATHS:${PYTHONPATH:-}" "$PY" -c "import EikoNet.model, HypoSVI.location" 2>/dev/null; then
        fail "--loc-backend hyposvi needs the HypoSVI + EikoNet clones on the path. Clone them and set .env:
    git clone https://github.com/Ulvetanna/HypoSVI.git && echo \"HYPOSVI_DIR=\$PWD/HypoSVI\" >> $HERE/.env
    git clone https://github.com/Ulvetanna/EikoNet.git && echo \"EIKONET_DIR=\$PWD/EikoNet\" >> $HERE/.env
  See docs/python_backend/README.md."
    fi
    ok "HypoSVI + EikoNet code: importable"
fi

[[ -x "$PY" ]] || fail "python interpreter not found (PY='$PY'). Set POCKETQUAKE_PYTHON=/path/to/python or put 'python3' on PATH."
ok "python: $PY"

# ---- fail fast if the chosen interpreter lacks NECIS deps (playwright) ----
# NECIS uses a Playwright browser; mixed mode can fall back to NECIS mid-run. Without
# this check the import only fails AFTER the multi-minute STP batch. Catch it up front.
if [[ "$SOURCE" == "necis" || "$SOURCE" == "mixed" ]]; then
    if ! "$PY" -c "import playwright" 2>/dev/null; then
        # Try to point the user at an env that does have it (common: a conda env).
        HINT=""
        for cand in "$HOME"/miniforge3/envs/*/bin/python3 "$HOME"/miniconda3/envs/*/bin/python3 "$HOME"/anaconda3/envs/*/bin/python3; do
            [[ -x "$cand" ]] && "$cand" -c "import playwright" 2>/dev/null && { HINT="$cand"; break; }
        done
        msg="'$PY' cannot import playwright, required for --source $SOURCE (NECIS). "
        if [[ -n "$HINT" ]]; then
            msg+="Found playwright in: $HINT
  Re-run with:  POCKETQUAKE_PYTHON=$HINT ./pocketquake.sh ...   (or 'conda activate' that env first)"
        else
            msg+="Install it into this interpreter:  $PY -m pip install playwright && $PY -m playwright install chromium
  (or set POCKETQUAKE_PYTHON to an env that already has it). See docs/INSTALL.md."
        fi
        fail "$msg"
    fi
    ok "playwright: importable (NECIS ready)"
fi

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
ok "loc-backend: $LOC_BACKEND"
ok "reloc-bcknd: $RELOC_BACKEND"
ok "source:      $SOURCE"
[[ -n "$STP_CUTOFF" ]] && ok "stp-cutoff:  $STP_CUTOFF (events >= this date skip STP)"
[[ -n "$CORES"      ]] && ok "cores:       $CORES (xcorr worker cap)"
[[ -n "$MAINSHOCK"  ]] && ok "mainshock:   $MAINSHOCK (treatment will be applied after default run)"

# ---- the orchestrator command ----
CMD=(
    "$PY" -u -m pocketquake.orchestrate "$CATALOG"
    --cluster "$SLUG"
    --epicenter "$EPI"
    --region-bounds "$BBOX"
    --picker "$PICKER"
    --wf-backend "$SOURCE"
    --loc-backend "$LOC_BACKEND"
    --reloc-backend "$RELOC_BACKEND"
)
[[ -n "$STP_CUTOFF"     ]] && CMD+=(--stp-cutoff "$STP_CUTOFF")
[[ -n "$CORES"          ]] && CMD+=(--cores "$CORES")
[[ "$SKIP_DOWNLOAD" == "1" ]] && CMD+=(--skip-download)
[[ "$SKIP_PIPELINE" == "1" ]] && CMD+=(--skip-pipeline)
LOG="$HERE/${SLUG}_run.log"

cd "$HERE"
if [[ "$MAIN_ONLY" == "1" ]]; then
    # --mainshock-only: skip the default pipeline pass entirely; the cluster's runs/
    # directory must already exist (i.e. you ran the default pipeline previously and now
    # want to overlay the Gwangyang-style treatment without redoing scaffold / download
    # / picking / location).
    RELOC="$EQDIR/pipeline/runs/${SLUG}/2.HypoDD/02.dt.cc/hypoDD.reloc"
    [[ -f "$RELOC" ]] || fail "--mainshock-only set but $RELOC missing — run the default pipeline first"
    hdr "skipping default pipeline (--mainshock-only)"
    ok "cluster runs/ already present; jumping to mainshock treatment"
elif [[ "$FG" == "1" ]]; then
    hdr "launching default pipeline (log: $LOG)"
    "${CMD[@]}" 2>&1 | tee "$LOG"
    DEFAULT_RC="${PIPESTATUS[0]}"
    [[ "$DEFAULT_RC" == "0" ]] || fail "default pipeline failed (exit $DEFAULT_RC)"
    if [[ "$COMPARE" == "1" ]]; then
        hdr "comparing Fortran vs Python backends (same picks)"
        "$PY" -u -m pocketquake.compare_backends "$SLUG" 2>&1 | tee -a "$LOG"
        CMP_RC="${PIPESTATUS[0]}"
        [[ "$CMP_RC" == "0" ]] || fail "backend comparison failed (exit $CMP_RC)"
        ok "comparison notebook: $EQDIR/pipeline/notebooks/04_compare_${SLUG}.ipynb"
    fi
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
