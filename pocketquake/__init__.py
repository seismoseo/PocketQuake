"""PocketQuake — from an event-catalog CSV to a relocation-summary notebook in one command.

PocketQuake is a thin meta-orchestrator. The heavy work lives in two upstream projects we use as
git submodules under `external/`:

- `seismoseo/necis-downloader` — KMA NECIS waveform downloader (Playwright + requests).
- `seismoseo/korea-cluster-relocation` — HypoDD relocation + SKHASH focal-mechanism pipeline.

Workflow (see `pocketquake.orchestrate.orchestrate`):

    catalog CSV
        → scaffold cluster dir tree under the eq-cycle submodule
        → necis-downloader fills `kma_waveforms/`
        → register the cluster (write `pipeline/clusters/<name>.py`, edit `CLUSTER_NAMES`)
        → eq-cycle pipeline (picking → hypoinverse → ph2dt → dtct → xcorr → dtcc → focal_mechanism)
        → build & execute `03_results_<cluster>.ipynb`
"""

__version__ = "1.7.0"            # single source of truth — pyproject.toml reads this via setuptools dynamic

import os

# Repository root (the directory that contains this `pocketquake/` package).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# Submodule paths
NECIS_DIR = os.path.join(ROOT, "external", "necis-downloader")
EQCYCLE_DIR = os.path.join(ROOT, "external", "korea-cluster-relocation")

# Bundled assets
STATIONS_KP = os.path.join(ROOT, "stations", "KP_station_list.csv")
