# PocketQuake installation

End-to-end install guide for a fresh clone. After following this, the
`examples/chungju` smoke test should run.

The default pipeline is **PhaseNet+ → HypoInverse → HypoDD → SKHASH focal
mechanism**, so this guide installs everything that chain needs. STP is
optional (only for pre-2020 waveforms).

## 0. Prerequisites

- Linux or macOS (the wrapper is bash; Windows users need WSL)
- conda or mamba (Miniforge / Miniconda / Mambaforge — any works)
- git with submodule support
- A working C and Fortran toolchain (`gcc`, `gfortran`, `make`) for the
  compiled external binaries listed below
- ~10 GB free disk (Playwright Chromium + example waveforms)

## 1. Clone with submodules

```bash
git clone --recurse-submodules https://github.com/seismoseo/PocketQuake.git
cd PocketQuake
# If you cloned without --recurse-submodules:
git submodule update --init --recursive
```

## 2. Conda environment (one command)

```bash
conda env create -f environment.yml
conda activate pocketquake
pip install -e . -e external/necis-downloader
playwright install chromium      # one-time, ~200 MB
```

`environment.yml` installs Python, obspy, seisbench, playwright, pytorch (CPU),
plotly, jupyter, and `libarchive` (which provides `bsdtar`). If you need GPU
PyTorch for PhaseNet+, install the matching CUDA wheel from <https://pytorch.org>
*after* activating the env.

## 3. External binaries (compiled)

These are NOT pip-installable. The defaults rely on them being on `$PATH`.
Detailed build instructions live in [EXTERNAL_TOOLS.md](EXTERNAL_TOOLS.md);
the short form:

- **`hyp1.40`** — HypoInverse-2000 (USGS Fortran source build)
- **`ph2dt`** + **`hypoDD`** — Waldhauser's HypoDD distribution (Fortran)
- **`mseed2sac`** — IRIS C source build

If you already have these, skip ahead. Otherwise, follow
[EXTERNAL_TOOLS.md §Compiled binaries](EXTERNAL_TOOLS.md#compiled-binaries-fortran--c--make).

## 4. EQNet (PhaseNet+ picker) — required for the default

PhaseNet+ is the default picker because it emits first-motion polarity +
per-pick amplitudes that SKHASH consumes.

```bash
cd ~/works     # or wherever you want EQNet
git clone https://github.com/AI4EPS/EQNet.git
cd EQNet
pip install -r requirements.txt    # PocketQuake's env already has PyTorch
echo "EQNET_DIR=$PWD" >> ~/works/PocketQuake/.env
```

The PhaseNet+ weights are bundled in the EQNet repo at
`docs/model_phasenet_plus/model_99.pth` — no separate download needed.

If you prefer the SeisBench PhaseNet picker (no extra clone), pass
`--picker stead` on every run. The default `phasenet_plus` is recommended
because the focal-mechanism stage needs polarity / amplitude data only
PhaseNet+ produces.

## 5. SKHASH (focal mechanism) — required for the default

```bash
cd ~/works
git clone https://code.usgs.gov/esc/SKHASH.git
echo "SKHASH_DIR=$PWD/SKHASH/SKHASH" >> ~/works/PocketQuake/.env
```

SKHASH's Python deps (numpy, scipy, pandas) are already in the `pocketquake`
conda env.

## 6. Credentials

```bash
cp .env.example .env
# then edit:
#   NECIS_USER, NECIS_PASS — required (see below)
#   STP_USER, STP_PASS     — only if you use --source stp / mixed
```

### NECIS

1. Apply at <https://necis.kma.go.kr>. Research / institutional accounts
   only; approval takes 1–5 days.
2. Fill `NECIS_USER` / `NECIS_PASS` in `.env`.

### STP (optional — only for `--source stp` or `--source mixed`)

Contact the SGTL lab at SNU for credentials. STP fetches pre-2020 waveforms
that NECIS no longer serves as packaged event archives.

## 7. Smoke test — chungju example

```bash
./pocketquake.sh examples/chungju/catalog.csv chungju_smoke
```

Expected end-state (default pipeline, ~30 min for the 4-event chungju
catalog):

- `external/korea-cluster-relocation/chungju_smoke_cluster/kma_waveforms/` —
  NECIS-downloaded SACs per event
- `external/korea-cluster-relocation/pipeline/runs/chungju_smoke/1.HypoInv/kim1983/Chungju_smoke.sum`
  — HypoInverse absolute locations
- `external/korea-cluster-relocation/pipeline/runs/chungju_smoke/2.HypoDD/.../hypoDD.reloc`
  — relative-relocated catalog
- `external/korea-cluster-relocation/pipeline/runs/chungju_smoke/3.focal_mechanism/`
  — SKHASH solutions
- `external/korea-cluster-relocation/pipeline/notebooks/03_results_chungju_smoke.ipynb`
  — executed results notebook with maps, sections, and focal mechanisms

If you want to skip the relocation pipeline and only verify the download
path, append `--skip-pipeline`.

## 8. Troubleshooting

If anything breaks, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — it maps
the common fresh-clone errors (missing python, missing externals, NECIS
credentials, Playwright Chromium) to one-line fixes.

## Minimum-viable install (no focal mechanism, no PhaseNet+)

If you don't want to install EQNet + SKHASH and are OK with absolute +
relative location only:

```bash
# In .env, leave EQNET_DIR and SKHASH_DIR unset.
# Then for every run, force the SeisBench PhaseNet picker:
./pocketquake.sh examples/chungju/catalog.csv chungju_smoke \
    --picker stead --skip-pipeline-stage focal_mechanism
```

(The `--skip-pipeline-stage` flag is wired through to
`pipeline.cli.run_pipeline --through dtcc`.)

## What we don't ship yet

- A Docker / conda-pack image (planned).
- Native Windows support — use WSL.
- PyPI release — install from source for now.
