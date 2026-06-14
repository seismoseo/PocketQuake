# PocketQuake

**From an event-catalog CSV to a relocation-summary notebook in one command.**

!!! info inline end "Version"
    **v1.12.0** &middot; [Changelog](https://github.com/seismoseo/PocketQuake/blob/main/CHANGELOG.md) &middot; [Releases](https://github.com/seismoseo/PocketQuake/releases)

PocketQuake glues two projects into a single reproducible workflow for Korean earthquake sequences:

- **[necis-downloader](https://github.com/seismoseo/necis-downloader)** — fetches KMA NECIS waveforms for an event list (with STP fallback for pre-2020 events).
- **[korea-cluster-relocation](https://github.com/seismoseo/korea-cluster-relocation)** — the picking → relocation → focal-mechanism pipeline.

Give it a catalog CSV:

```csv
Year,Month,Day,Hour,Minute,Second,Latitude,Longitude,Magnitude,Depth
2025,2,7,2,35,34,37.14,127.76,3.1,9
2025,2,7,2,54,38,37.14,127.76,1.4,6
```

…and one command scaffolds a cluster, downloads the waveforms, runs the chain, and produces an executed `03_results_<cluster>.ipynb` with epicenter maps, depth sections, fault-frame sections, bootstrap 95% error bars, and focal-mechanism beachballs — plus a uniform, presentation-ready **beamer PDF run summary** (`runs/<cluster>/summary/<cluster>_summary.pdf`):

```bash
./pocketquake.sh examples/chungju/chungju_catalog.csv chungju --fg
```

## Two ways to relocate

PocketQuake ships **two interchangeable relocation modes** — same picks, same outputs, same notebook (relative locations agree to ~1 m):

| | **Fortran mode** *(default)* | **Python mode** (`--python`) |
|---|---|---|
| Absolute location | HYPOINVERSE (`hyp1.40`) | HypoSVI + EikoNet |
| Relocation | `ph2dt` + `hypoDD` | relocDD-py |
| Setup | 3 compiled Fortran binaries | 3 Python clones — **no compiler** |

See [Two relocation modes](relocation-modes.md).

## Get started

<div class="grid cards" markdown>

- :material-rocket-launch: **[Quickstart](quickstart.md)** — install and run the chungju example
- :material-cog: **[Installation](INSTALL.md)** — environment, externals, accounts
- :material-console: **[CLI reference](cli.md)** — every `pocketquake.sh` option
- :material-language-python: **[Python backend](python-backend.md)** — the Fortran-free path
- :material-wrench: **[Troubleshooting](TROUBLESHOOTING.md)** — fresh-clone error map

</div>

!!! tip "Slides"
    A beamer **[tutorial PDF](tutorial/PocketQuake_manual.pdf)** walks through install → run → outputs.
