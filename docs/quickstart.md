# Quickstart

Run the bundled **chungju** example (4 events, Feb 2025) end-to-end.

## 1. Environment

```bash
git clone --recurse-submodules https://github.com/seismoseo/PocketQuake.git
cd PocketQuake
conda env create -f environment.yml
conda activate pocketquake
pip install -e . -e external/necis-downloader
playwright install chromium          # NECIS portal driver
```

## 2. External programs

The default pipeline calls a few non-pip tools — see [Installation](INSTALL.md) and [External tools](EXTERNAL_TOOLS.md):

- `hyp1.40`, `ph2dt`, `hypoDD`, `mseed2sac` on `$PATH`
- **EQNet** (PhaseNet+ picker) and **SKHASH** (focal mechanisms), via two clones + `EQNET_DIR` / `SKHASH_DIR` in `.env`

!!! note "No Fortran toolchain?"
    Use [Python mode](relocation-modes.md) (`--python`) — HypoSVI + EikoNet + relocDD-py replace the Fortran binaries.

## 3. Credentials

```bash
cp .env.example .env        # then set NECIS_USER / NECIS_PASS
```

## 4. Run

```bash
./pocketquake.sh examples/chungju/chungju_catalog.csv chungju --fg
```

`pocketquake.sh` auto-derives the epicenter (catalog centroid) and region (bbox + 0.2°), checks credentials, downloads waveforms, runs **PhaseNet+ → HypoInverse → HypoDD → SKHASH**, and builds + executes the results notebook (~15 min on a 16-core box).

## 5. Look at the output

```bash
jupyter lab external/korea-cluster-relocation/pipeline/notebooks/03_results_chungju.ipynb
```

You get: relocated epicenter map, three orthogonal depth sections, fault-frame sections, **bootstrap 95% error bars**, a per-event beachball gallery, and a cumulative time-lapse animation.

## Next

- [Two relocation modes](relocation-modes.md) — Fortran vs Python, and `--compare`
- [CLI reference](cli.md) — `--source`, `--skip-download`, `--velmodel`, `--mainshock`, …
