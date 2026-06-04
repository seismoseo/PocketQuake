# PocketQuake installation

End-to-end install guide for a fresh clone. After following this, the `examples/chungju`
smoke test should run.

## Prerequisites

- Linux or macOS (the wrapper is bash; Windows users need WSL)
- Python 3.10 or newer (3.11 recommended)
- git with submodule support
- ~10 GB free disk (Playwright Chromium is large; example downloads add more)

## 1. Clone with submodules

```bash
git clone --recurse-submodules https://github.com/seismoseo/PocketQuake.git
cd PocketQuake
```

If you cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

## 2. Python environment

A venv or conda env is recommended. Then:

```bash
pip install -e .                         # PocketQuake itself
pip install -e external/necis-downloader  # NECIS waveform downloader
pip install -r requirements.txt           # shared deps (obspy, seisbench, etc.)
```

The eq-cycle pipeline under `external/korea-cluster-relocation/` has no `pyproject.toml`;
its runtime needs (`obspy`, `seisbench`, `plotly`, `kaleido`) are already covered by
`requirements.txt`.

## 3. Browser for the NECIS downloader

The NECIS portal is a JavaScript single-page app, so the downloader uses Playwright.
Install Chromium one-time (~200 MB):

```bash
playwright install chromium
```

## 4. External binaries

PocketQuake calls **out-of-process** to a handful of seismology tools that are not
pip-installable. See [EXTERNAL_TOOLS.md](EXTERNAL_TOOLS.md) for sources, install
recipes, and env-var conventions:

- `hyp1.40` (HypoInverse)
- `ph2dt`, `hypoDD`
- `mseed2sac`, `bsdtar` (for unpacking NECIS archives)
- `EQNet` (only if you use `--picker phasenet_plus`)
- `SKHASH` (only if you run focal mechanisms)

Place the binaries on your `PATH`. PocketQuake checks at first use and prints
actionable errors if anything is missing.

## 5. Credentials

KMA-side waveforms are not freely browsable; you need accounts.

### NECIS (KMA)

1. Apply at <https://necis.kma.go.kr> — research or institutional accounts only.
   Approval takes 1–5 days.
2. Once approved, copy `.env.example` to `.env` and fill in:
   ```bash
   NECIS_USER=your-id
   NECIS_PASS=your-password
   ```

### STP (SNU, optional)

Only needed if you want pre-2020 waveforms via `--source stp` or `--source mixed`.
Contact the SGTL lab at SNU for credentials. Then in `.env`:

```bash
STP_USER=your-stp-id
STP_PASS=your-stp-password
```

## 6. Smoke test — chungju example

```bash
./pocketquake.sh examples/chungju/catalog.csv chungju_smoke --skip-pipeline
```

Expected: NECIS download starts; cluster scaffold lands at
`external/korea-cluster-relocation/chungju_smoke_cluster/`. No "command not
found" errors. Run without `--skip-pipeline` for the full HypoInverse → HypoDD →
focal-mechanism → results-notebook pipeline (under ~30 min for the chungju
catalog).

## Troubleshooting

If anything breaks, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — it covers the
common fresh-clone errors (Python not found, missing STP client, missing
binaries, Playwright Chromium, NECIS credentials).

## What we don't ship yet

- A Docker / conda-pack image (planned).
- Native Windows support — use WSL.
- PyPI release — install from source for now.
