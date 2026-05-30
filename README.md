# PocketQuake

**From an event-catalog CSV to a relocation-summary notebook in one command.**

PocketQuake glues two existing projects:

- **[seismoseo/necis-downloader](https://github.com/seismoseo/necis-downloader)** — downloads KMA NECIS waveforms for a given event list.
- **[seismoseo/korea-cluster-relocation](https://github.com/seismoseo/korea-cluster-relocation)** — HypoDD relocation + SKHASH focal-mechanism pipeline.

Given just a catalog CSV like

```
Year,Month,Day,Hour,Minute,Second,Latitude,Longitude,Magnitude,Depth
2024,9,12,23,47,19,35.46,128.43,2.6,16
…
```

PocketQuake scaffolds a cluster, downloads the event waveforms, runs the picking → HypoDD → focal-mechanism chain, and produces an executed `03_results_<cluster>.ipynb` with epicenter maps, depth sections, fault-frame sections, bootstrap error bars, and beachballs.

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

```bash
git clone --recurse-submodules git@github.com:seismoseo/PocketQuake.git
cd PocketQuake
pip install -e .
pip install -e external/necis-downloader
playwright install chromium       # one-time, for NECIS scraping

cp .env.example .env              # then edit NECIS_USER / NECIS_PASS

# One-command wrapper (auto-derives epicenter + bounds from the catalog;
# runs in nohup background by default; pass --fg for foreground; --help for options):
./pocketquake.sh examples/changnyeong/changnyeong_catalog.csv mytest

# Full CLI form (when you want explicit control):
pocketquake examples/changnyeong/changnyeong_catalog.csv \
    --cluster changnyeong \
    --epicenter 35.463,128.427 \
    --region-bounds 35.3,35.65,128.25,128.65
```

`pocketquake.sh` is the friendly one-liner; it auto-derives the epicenter (catalog centroid)
and region bounds (catalog bbox + 0.2°), checks credentials, and chains the optional
Gwangyang-style mainshock treatment when you pass `--mainshock UTC_YYYYMMDDHHMMSS`.

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
