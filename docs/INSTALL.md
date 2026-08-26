# PocketQuake installation

End-to-end install guide for a fresh clone. After following this, the
`examples/chungju` smoke test should run.

The default pipeline is **PhaseNet+ → HypoInverse → HypoDD → SKHASH focal
mechanism**, so this guide installs everything that chain needs. STP is
optional (only for pre-2020 waveforms).

## Installing without git (Windows-friendly ZIP)

GitHub's automatic "Download ZIP" of this repository ships **empty** submodule
directories, so it does not produce a runnable tree. Instead, download
**`PocketQuake-<version>-full-source.zip`** from the
[Releases page](https://github.com/seismoseo/PocketQuake/releases) — it bundles
PocketQuake plus both submodules (korea-cluster-relocation, necis-downloader)
at their pinned versions, contains no symlinks (safe to extract on Windows),
and records the exact commit SHAs in `BUNDLE_INFO.txt`. The ~700 MB of
generated per-cluster result notebooks are excluded (the pipeline regenerates
them; browse the committed ones on GitHub). After extracting, continue with
the conda environment setup below exactly as for a git checkout.

## 0. Prerequisites

- **OS**: Linux or macOS (wrapper is bash; Windows users need WSL)
- **glibc ≥ 2.28** — Ubuntu 20.04+, RHEL/Rocky 8+, Debian 10+, or any newer
  distro. Playwright's bundled Node binary requires `GLIBC_2.27/2.28`,
  `CXXABI_1.3.11`, `GLIBCXX_3.4.21`; older systems like CentOS 7 / RHEL 7
  (glibc 2.17, gcc 4.8) **cannot run the NECIS downloader**. On such boxes,
  do the NECIS download on a newer machine, rsync the cluster dir, then
  run the relocation stages locally (no Playwright needed).
- **Python**: 3.10+ (pinned by `environment.yml`)
- **conda or mamba** (Miniforge / Miniconda / Mambaforge — any works)
- **git** with submodule support
- **C and Fortran toolchain** (`gcc`, `gfortran`, `make`) for the compiled
  external binaries (`hyp1.40`, `ph2dt`, `hypoDD`, `mseed2sac`). gcc ≥ 9.3
  recommended.
- **Network**: HTTPS access to github.com, code.usgs.gov, and conda-forge
- **Disk**: ~10 GB free (~2 GB conda env + ~500 MB Playwright Chromium +
  waveform downloads that scale with catalog size)

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
plotly, jupyter, and `libarchive` (which provides `bsdtar`).

**GPU is recommended.** It accelerates **two** stages: the **default `dt.cc` cross-correlation**
(`xcorr`, `cctorch_gpu_batched` backend — ~3× at cluster scale) **and** the `--python` / HypoSVI
locate (~10–20× per event; a 15k-event catalog is ~15 h on GPU vs ~1–2 weeks on CPU). After
activating the env, install a CUDA PyTorch wheel matching your card from
<https://pytorch.org/get-started/locally/> (e.g. `cu128` for Blackwell sm_120):

```bash
pip install --upgrade --index-url https://download.pytorch.org/whl/cu128 torch
python -c "import torch; print('sm_120' in torch.cuda.get_arch_list(), torch.cuda.get_device_name(0))"
```

This is **optional** — both GPU stages auto-fall-back to CPU (the default Fortran path and CPU
HypoSVI run fine without it). But the GPU is used **only when the env you launch with has a torch
that supports your card**: PocketQuake runs whatever `python3` it finds (or `$POCKETQUAKE_PYTHON`),
so a GPU newer than that env's torch (e.g. **sm_120 on a cu124 wheel**) cleanly falls back to CPU.
If you keep a separate GPU env, point the wrapper at it without activating:
`POCKETQUAKE_PYTHON=/path/to/gpu-env/bin/python ./pocketquake.sh …`. Each run prints
**`GPU xcorr: ACTIVE`** or **`GPU xcorr: UNAVAILABLE in this env → CPU fallback`** up front so you
can tell at a glance. See [Python backend → GPU](python-backend.md#gpu-recommended) and
[Troubleshooting → GPU not used](TROUBLESHOOTING.md#gpu-xcorr-unavailable-in-this-env-cpu-fallback).

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
# SKHASH_DIR = the directory that contains SKHASH.py
# (current upstream: SKHASH/src/SKHASH; older checkouts: SKHASH/SKHASH)
echo "SKHASH_DIR=$PWD/SKHASH/src/SKHASH" >> ~/works/PocketQuake/.env
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
./pocketquake.sh examples/chungju/chungju_catalog.csv chungju_smoke
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
./pocketquake.sh examples/chungju/chungju_catalog.csv chungju_smoke \
    --picker stead --skip-pipeline-stage focal_mechanism
```

(The `--skip-pipeline-stage` flag is wired through to
`pipeline.cli.run_pipeline --through dtcc`.)

## What we don't ship yet

- A Docker / conda-pack image (planned).
- Native Windows support — use WSL.
- PyPI release — install from source for now.
