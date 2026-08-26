# PocketQuake

[![Docs](https://readthedocs.org/projects/pocketquake/badge/?version=latest)](https://pocketquake.readthedocs.io/)

**From an event-catalog CSV to a relocation-summary notebook in one command.**

![Chungju Feb 2025 — 4-event time-lapse animation in the fault frame](examples/chungju/figures/00_seismicity_animation.gif)

*The PocketQuake output for the 4-event [Chungju Feb 2025 sequence](examples/chungju/README.md) — a cumulative time-lapse animation in the same 2×2 fault-frame layout as `viz.fault_sections`: events appear in chronological order on top of the focal-mechanism beachball (A grade, near-vertical N–S right-lateral strike-slip). **One command from a 4-line CSV to this animation + the rest of the [results notebook](external/korea-cluster-relocation/pipeline/notebooks/03_results_chungju.ipynb): `./pocketquake.sh examples/chungju/chungju_catalog.csv chungju --fg`** (~15 min wall-clock).*

PocketQuake glues two existing projects:

- **[seismoseo/necis-downloader](https://github.com/seismoseo/necis-downloader)** — downloads KMA NECIS waveforms for a given event list.
- **[seismoseo/korea-cluster-relocation](https://github.com/seismoseo/korea-cluster-relocation)** — HypoDD relocation + SKHASH focal-mechanism pipeline.

For **older events** (pre-~2020) that NECIS no longer serves as downloadable event
segments, PocketQuake can fetch via **STP** (Seoul National University's SAC Transfer
Protocol at `mara.snu.ac.kr:46804`) instead — same one-command flow, just pass
`--source stp`. See [examples/sangju/](examples/sangju/README.md) for a 2018–2022 worked
example where the M3.9 mainshock and its aftershocks live in STP's archive but not in
NECIS's.

Given just a catalog CSV like

```
Year,Month,Day,Hour,Minute,Second,Latitude,Longitude,Magnitude,Depth
2025,2,7,2,35,34,37.14,127.76,3.1,9
2025,2,7,2,54,38,37.14,127.76,1.4,6
2025,2,7,3,49,4,37.14,127.76,1.5,7
2025,2,8,10,13,23,37.14,127.76,1.6,7
```

PocketQuake scaffolds a cluster, downloads the event waveforms, runs the picking → HypoDD → focal-mechanism chain, and produces an executed `03_results_<cluster>.ipynb` with epicenter maps, depth sections, fault-frame sections, bootstrap error bars, and beachballs — plus a uniform, presentation-ready **beamer PDF run summary** at `runs/<cluster>/summary/<cluster>_summary.pdf`.

### Worked example: chungju (4 events, Feb 2025)

The 4-event chungju sequence shipped under `examples/chungju/chungju_catalog.csv` is the
canonical PocketQuake example — small enough to run quickly (~15 min wall-clock end-to-end),
and dense enough to exercise every stage of the pipeline:

- **Locations** (HypoInverse, kim1983): 4 events at (37.142, 127.760), depths 7.3 → 10.2 km,
  RMS 0.22 – 0.28 s, ERH 0.2 km — all grade B.
- **Relative relocation** (dt.cc): cluster tightens to ±100 m around (37.142, 127.759, 7.2 km).
- **Focal mechanisms** (SKHASH): the M3.1 mainshock + two aftershocks are grade A/B
  near-vertical strike-slip (strike ≈ 200°, dip 84–87°, rake near ±180°); the smallest M1.6
  drops to grade C with 13.5% polarity misfit (visible in the custom beachball as off-quadrant
  triangles).

The `03_results_chungju.ipynb` showcases every PocketQuake visual: catalog map, depth
sections, distance record sections (Z traces ordered by hypocentral distance, P/S picks
overlaid against the depth-averaged moveout), the dt.cc relocation map, the
polarity-and-S/P-overlay beachball gallery, fault-frame sections, an interactive 3-D view,
and a polarity-quality panel. See `examples/chungju/README.md` (TODO) for the per-stage
walkthrough.

## Architecture

```text
┌──────────────────────┐
│  catalog CSV (KST)   │
└──────────┬───────────┘
           ▼
    pocketquake.orchestrate
           │
           ├──► scaffold cluster dir         (sibling of external/korea-cluster-relocation/pipeline/)
           ├──► necis-downloader  ──────►   kma_waveforms/<event_id>/{a,v}/SAC/<band>/…
           ├──► register cluster             (pipeline/clusters/<name>.py + config.py)
           ├──► korea-cluster-relocation:   stations → waveforms → picking (PhaseNet+)
           │                                → hypoinverse → ph2dt → dtct
           │                                → rereference → xcorr → dtcc
           │                                → focal_mechanism (SKHASH, A/B mechanisms)
           └──► 03_results_<cluster>.ipynb  (executed, headless)
```

Both upstream projects are included as **git submodules** under `external/`, so
`git clone --recurse-submodules` brings everything.

## Quickstart

Full install walkthrough (conda env, external binaries, credentials):
[**docs/INSTALL.md**](docs/INSTALL.md). The condensed version:

```bash
git clone --recurse-submodules https://github.com/seismoseo/PocketQuake.git
cd PocketQuake

# 1. Python environment (one command; includes obspy, seisbench, playwright,
#    PyTorch CPU, libarchive's bsdtar, jupyter, plotly).
conda env create -f environment.yml
conda activate pocketquake
pip install -e . -e external/necis-downloader
playwright install chromium       # one-time, ~200 MB

# 2. External binaries (NOT pip-installable). See docs/EXTERNAL_TOOLS.md.
#    hyp1.40, ph2dt, hypoDD, mseed2sac on $PATH.

# 3. EQNet (PhaseNet+ — default picker) + SKHASH (focal mechanism) — required
#    for the default pipeline. See docs/INSTALL.md §4-§5. Two git clones + two
#    env vars in .env: EQNET_DIR, SKHASH_DIR.

# 4. NECIS account.
cp .env.example .env              # then edit NECIS_USER / NECIS_PASS

# 5. Run the chungju example end-to-end.
./pocketquake.sh examples/chungju/chungju_catalog.csv mytest

# Full CLI form (when you want explicit control):
pocketquake examples/chungju/chungju_catalog.csv \
    --cluster chungju \
    --epicenter 36.96,127.78 \
    --region-bounds 36.85,37.10,127.65,127.95
```

`pocketquake.sh` is the friendly one-liner; it auto-derives the epicenter (catalog centroid)
and region bounds (catalog bbox + 0.2°), checks credentials, and chains the optional
Gwangyang-style mainshock treatment when you pass `--mainshock UTC_YYYYMMDDHHMMSS`.

### Two ways to relocate — pick what fits your setup

PocketQuake ships **two interchangeable relocation modes**. They take the same picks, write
the same files, and build the same summary notebook — and they agree on *relative* locations
to ~1 m. Picking (PhaseNet+) and focal mechanisms (SKHASH) are identical either way.

| | **Fortran mode** *(default)* | **Python mode** (`--python`) |
|---|---|---|
| Absolute location | HYPOINVERSE (`hyp1.40`) | HypoSVI + EikoNet |
| Relocation | `ph2dt` + `hypoDD` | relocDD-py |
| Setup | 3 compiled Fortran binaries | 3 Python clones — **no compiler** |
| Good when… | you have the binaries / want the long-trusted reference | no Fortran toolchain (or you want GPU location) |

```bash
./pocketquake.sh catalog.csv myrun              # Fortran  (default)
./pocketquake.sh catalog.csv myrun --python     # pure Python
./pocketquake.sh catalog.csv myrun --compare    # run BOTH → side-by-side comparison notebook
```

**Fortran mode** needs `hyp1.40`, `ph2dt`, `hypoDD` on `$PATH` — see
[docs/EXTERNAL_TOOLS.md](docs/EXTERNAL_TOOLS.md). For a minimum-viable run without EQNet /
SKHASH, see [docs/INSTALL.md §Minimum-viable](docs/INSTALL.md#minimum-viable-install-no-focal-mechanism-no-phasenet).

**Python mode** needs three clones (no compiler) — set once in `.env`:

```bash
git clone https://github.com/katie-biegel/relocDD-py.git && echo "RELOCDD_PY_DIR=$PWD/relocDD-py" >> .env
git clone https://github.com/Ulvetanna/HypoSVI.git        && echo "HYPOSVI_DIR=$PWD/HypoSVI"       >> .env
git clone https://github.com/Ulvetanna/EikoNet.git        && echo "EIKONET_DIR=$PWD/EikoNet"       >> .env
python -m pipeline.core.fetch_eikonet            # pretrained kim1983 + kim2011 weights (one-time)
```

The absolute epicentre can differ between modes (HypoSVI vs HYPOINVERSE) — that centroid
offset is normal and not what double-difference relocation constrains. The default Fortran path
is unchanged. Full Python recipe (GPU, training your own velocity model):
[docs/python_backend/README.md](external/korea-cluster-relocation/docs/python_backend/README.md).

External binaries (`hyp1.40`, `hypoDD`, `mseed2sac`, etc.) are not pip-installable — see
[docs/EXTERNAL_TOOLS.md](docs/EXTERNAL_TOOLS.md) for build instructions per tool.
Errors during a fresh-clone smoke test are mapped in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

### Command-line options

`./pocketquake.sh CATALOG SLUG [options]` — the common ones (run `./pocketquake.sh --help` for all):

| Option | What it does |
|---|---|
| `--augment` | incremental mode: the catalog is an **augmented** version of an already-processed cluster's — add only the new events (download/pick/locate), reuse existing picks + dt.cc pairs, re-relocate the whole cluster (`--dry-run` previews the diff) |
| `--python` | pure-Python backend (= `--loc-backend hyposvi --reloc-backend relocdd_py`) |
| `--compare` | run Fortran **and** Python on the same picks → side-by-side `04_compare_<slug>.ipynb` |
| `--source {necis\|stp\|mixed}` | waveform source (default `necis`; use `stp`/`mixed` for **pre-2020** events) |
| `--skip-download` | reuse waveforms already on disk — skip the (slow) download stage |
| `--skip-pipeline` | scaffold + download only (skip relocation + notebook) |
| `--mainshock UTC_YYYYMMDDHHMMSS` | add Gwangyang-style mainshock treatment (builds a `_main` notebook) |
| `--mainshock-only` | re-run only the mainshock treatment on an existing cluster |
| `--picker {phasenet_plus\|stead}` | picker model (default `phasenet_plus`; `stead` needs no EQNet) |
| `--velmodel {kim1983\|kim2011}` | velocity model for relocation + focal mechanisms + notebook (default kim1983) |
| `--cores N` | cap xcorr workers (default per-cluster, ~10; lower it on small-RAM boxes) |
| `--epi LAT,LON` · `--bounds LAT0,LAT1,LON0,LON1` | override the auto-derived epicenter / region |
| `--fg` | run in the foreground (default: background via `nohup`, logs to `<slug>_run.log`) |

**Velocity model.** The location stage always computes **both** kim1983 and kim2011 (HYPOINVERSE /
HypoSVI); `--velmodel` (default `kim1983`) selects which one drives the **relocation** (ph2dt +
dt.ct/dt.cc), the **focal mechanisms**, and the **results notebook**:

```bash
./pocketquake.sh catalog.csv myrun --velmodel kim2011
```
This fully selects the model for the Fortran path; with `--python`, HypoSVI keeps its bundled
EikoNet weights for location while the relocation + notebook follow `--velmodel`.

**dt.cc cross-correlation backend.** The xcorr stage now defaults to a GPU FFT backend
(`cctorch_gpu_batched`) that batches across event-pairs — **bit-exact** to the obspy CPU baseline
(Δshift = 0.000 ms, ΔCC = 0), memory-safe by construction (VRAM-aware batch sizing + OOM-retry), and
**~3× faster** at scale (yeoncheon: ~12 min vs ~39 min). On a machine without a usable CUDA GPU it
**auto-falls-back to obspy**, so CPU-only setups are unaffected. Override with `--xcorr-backend`
(`obspy`, `cctorch_cpu`, `cctorch_gpu`, `cctorch_gpu_batched`); the GPU path needs the `pq-gpu`
conda env (PyTorch cu128).

## Gallery — what the notebook actually shows

These figures all come straight out of `03_results_chungju.ipynb` (no manual editing) — the full
catalog walkthrough is at [examples/chungju/README.md](examples/chungju/README.md).

**Per-event focal mechanisms with polarity + S/P overlays (v1.0.0):**

![Chungju beachball gallery with polarity + S-P overlays](examples/chungju/figures/04_beachball_gallery.png)

*Each panel = one event. Red ▲ = upward first motion, blue ▼ = downward (size ∝ polarity weight, position = (azimuth, takeoff) on the lower hemisphere). Offset colored circles = log₁₀(S/P amplitude ratio). The M3.1 grade-A mainshock (top-left) has 2.8 % polarity misfit — almost every triangle on the predicted side. The M1.6 grade-C event (bottom-right) has 13.5 % misfit — the off-quadrant triangles tell you exactly which stations the inversion can't fit.*

**Distance record section — picks vs depth-averaged moveout:**

![Distance record section for the M3.1 mainshock](examples/chungju/figures/06_record_section_M31.png)

*60 Z-component traces for the M3.1 mainshock, ordered by hypocentral distance. PhaseNet+ picks (red = P, blue = S) overlaid on the predicted moveouts at the kim1983 model's depth-averaged Vp/Vs down to the event focal depth. The picks lie right on the dashed lines — this is what PocketQuake's "your picks are good" QC looks like, automatically generated for every event.*

**Fault-coordinate sections (best-fit plane of the relocated cloud):**

![Chungju fault-coordinate sections](examples/chungju/figures/07_fault_sections.png)

*The dt.cc relocated cloud rotated into the SVD best-fit fault frame: fault-plane map view, along-strike depth section, across-strike depth section (dashed dip line), and the along-dip view. Markers coloured by origin time, sized by magnitude.*

Since **v1.14.0** the frame comes from the **SVD best-fit plane of the relocated cloud**
(`FRAME_FROM = "svd"`), so it is a property of the relocation — constrained by every event,
needing no focal mechanism, and free of the grade/size limits of one reference event. The
beachball is still drawn and the title reports both planes. `"auto"` (the previous default)
and `"mechanism"` remain selectable in the notebook's params cell; note that a *near-equant*
cloud has a well-determined plane but a poorly-determined strike within it — see
[the frame section in docs/workflow.md](docs/workflow.md#the-fault-coordinate-frame-frame_from).

That single command:

1. scaffolds `external/korea-cluster-relocation/changnyeong/{event_catalog,station_table,kma_waveforms}/`,
2. emits a `KS_station.csv` (404 stations) from the bundled `KP_station_list.csv`,
3. writes `pipeline/clusters/changnyeong.py` and registers it in `pipeline/config.py`,
4. downloads the 3 events from KMA NECIS,
5. runs the eq-cycle pipeline (PhaseNet+ picking + HypoDD + focal mechanisms),
6. writes and executes `pipeline/notebooks/03_results_changnyeong.ipynb`.

## What PocketQuake bundles (vs what is in the submodules)

| Bundled in PocketQuake | Lives in a submodule |
|---|---|
| `pocketquake/orchestrate.py` — the top-level workflow | NECIS scraping + ZIP organisation (`necis/`) |
| `pocketquake/scaffold.py` — cluster directory + config edits | Picking / HypoInv / HypoDD / SKHASH (`pipeline/`) |
| `pocketquake/necis_bridge.py` — async wrapper | Cluster configs for the four pilot clusters |
| `pocketquake/build_results_nb.py` — generates `03_results_<cluster>.ipynb` | Visualisation library (`pipeline/viz.py`) |
| `stations/KP_station_list.csv` — KMA master (404 KS + 61 KG) | — |
| `examples/changnyeong/` — test catalog | — |

PocketQuake stays lean (~10 files); upstream fixes flow in via `git submodule update --remote`.

## Prerequisites

Beyond Python 3.10+:

- **NECIS account** (`NECIS_USER` / `NECIS_PASS` in `.env`).
- **External binaries** on `PATH`: `hyp1.40`, `ncsn2pha`, `ph2dt`, `hypoDD`, `mseed2sac`.
- **PhaseNet+ weights**: `EQNET_DIR` + `EQNET_WEIGHTS` env vars (see the eq-cycle README).
- **SKHASH**: `SKHASH_DIR` env var (for focal mechanisms).
- A CUDA GPU is strongly recommended for PhaseNet+ picking; CPU works but is much slower.

## Local edits to the eq-cycle submodule

PocketQuake's scaffolder writes a cluster directory, a cluster module, and a small `config.py` edit into the **working tree** of the `korea-cluster-relocation` submodule. These are *local* changes — they are not committed from PocketQuake. If you want the cluster to become a permanent member of the framework, open a PR against [seismoseo/korea-cluster-relocation](https://github.com/seismoseo/korea-cluster-relocation) with those files.

## GitHub structure rationale

Why submodules and not pip-from-git or vendored copies?

| | submodules ✅ | pip-from-git | vendored copy |
|---|---|---|---|
| Works without packaging upstream | ✅ | ❌ (eq-cycle has no `pyproject.toml` yet) | ✅ |
| Preserves upstream history | ✅ | ✅ | ❌ |
| Single `git clone` brings everything | ✅ (`--recurse-submodules`) | ✅ | ✅ |
| Upstream fixes are one command away | `git submodule update --remote` | `pip install -U` | manual merge |
| End-user surface | needs a `--recurse-submodules` clone | cleanest | smoothest |

Submodules win for this case because the two upstreams have asymmetric packaging and PocketQuake is a thin orchestrator. If `korea-cluster-relocation` ever ships a `pyproject.toml`, we can switch to pip-from-git transparently.

## See also

- [`docs/workflow.md`](docs/workflow.md) — annotated walkthrough of the changnyeong run.
- [seismoseo/necis-downloader](https://github.com/seismoseo/necis-downloader) — NECIS scraper + ZIP extractor.
- [seismoseo/korea-cluster-relocation](https://github.com/seismoseo/korea-cluster-relocation) — the relocation pipeline.

## License

MIT
