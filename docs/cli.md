# CLI reference

```bash
./pocketquake.sh CATALOG SLUG [options]
```

`CATALOG` is a KMA-style CSV; `SLUG` names the cluster (its outputs land in `runs/<slug>/`). Run `./pocketquake.sh --help` for the authoritative list.

## Options

| Option | What it does |
|---|---|
| `--python` | pure-Python backend (= `--loc-backend hyposvi --reloc-backend relocdd_py`) |
| `--compare` | run Fortran **and** Python on the same picks → side-by-side `04_compare_<slug>.ipynb` |
| `--loc-backend {hypoinverse\|hyposvi}` | absolute-location backend (default `hypoinverse`) |
| `--reloc-backend {hypodd\|relocdd_py}` | relocation backend (default `hypodd`) |
| `--source {necis\|stp\|mixed}` | waveform source (default `necis`; use `stp`/`mixed` for **pre-2020** events) |
| `--stp-cutoff YYYY-MM-DD` | with `--source mixed`: events on/after this date skip STP, go straight to NECIS |
| `--skip-download` | reuse waveforms already on disk — skip the (slow) download stage |
| `--skip-pipeline` | scaffold + download only (skip relocation + notebook) |
| `--mainshock UTC_YYYYMMDDHHMMSS` | add Gwangyang-style mainshock treatment (builds a `_main` notebook) |
| `--mainshock-only` | re-run only the mainshock treatment on an existing cluster |
| `--picker {phasenet_plus\|stead}` | picker model (default `phasenet_plus`; `stead` needs no EQNet) |
| `--velmodel {kim1983\|kim2011}` | velocity model for relocation + focal mechanisms + notebook (default `kim1983`) |
| `--cores N` | cap xcorr workers (default per-cluster, ~10; lower it on small-RAM boxes) |
| `--epi LAT,LON` | override the auto-derived epicenter (catalog centroid) |
| `--bounds LAT0,LAT1,LON0,LON1` | override the auto-derived region (catalog bbox + 0.2°) |
| `--fg` | run in the foreground (default: background via `nohup`, logs to `<slug>_run.log`) |

## `--skip-download`, explained

Skips **only** the download stage; everything downstream still runs (gather existing SAC → re-pick → re-locate → re-relocate → notebook). The waveforms must already be under the cluster's source dir:

- `--source necis` → `kma_waveforms/`
- `--source stp` / `mixed` → `stp_download/SAC/`

If 0 waveforms are found the run stops with a clear message (often the wrong `--source` — pre-2020 data is STP-served).

## Velocity model

The location stage always computes **both** kim1983 and kim2011; `--velmodel` selects which one drives the **relocation**, **focal mechanisms**, and the **results notebook**. It fully selects the model for the Fortran path; with `--python`, HypoSVI keeps its bundled EikoNet weights for location while relocation + notebook follow `--velmodel`.

## Examples

```bash
# default Fortran run
./pocketquake.sh ~/my_catalog.csv myswarm

# pure Python, kim2011, foreground
./pocketquake.sh ~/my_catalog.csv myswarm --python --velmodel kim2011 --fg

# pre-2020 sequence (STP), reusing already-downloaded waveforms
./pocketquake.sh ~/2019_catalog.csv myslug --source stp --skip-download

# override epicenter / bounds for a wide catalog
./pocketquake.sh ~/my_catalog.csv myswarm --epi 35.46,128.43 --bounds 35.3,35.65,128.25,128.65

# mainshock treatment
./pocketquake.sh ~/my_catalog.csv myswarm --mainshock 20240912144719
```
