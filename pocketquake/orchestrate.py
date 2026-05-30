"""PocketQuake top-level orchestrator: catalog CSV → relocation summary notebook.

Pipeline:
  1. Scaffold the cluster directory inside the eq-cycle submodule's working tree.
  2. Download per-event waveforms from KMA NECIS into the cluster's `kma_waveforms/`.
  3. Register the cluster in the eq-cycle (write `pipeline/clusters/<name>.py`, edit `config.py`).
  4. Run the eq-cycle pipeline (`stations → … → dtcc [+ focal_mechanism]`).
  5. Build `pipeline/notebooks/03_results_<cluster>.ipynb` and execute it headless.

CLI:
  pocketquake examples/changnyeong/changnyeong_catalog.csv --cluster changnyeong \
              --epicenter 35.463,128.427 --region-bounds 35.3,35.65,128.25,128.65

Standing assumptions: NECIS_USER/NECIS_PASS in .env or env; `hyp1.40`, `ncsn2pha`, `ph2dt`,
`hypoDD`, `mseed2sac` on PATH; `EQNET_DIR` + `EQNET_WEIGHTS` for PhaseNet+; `SKHASH_DIR` for
focal mechanisms.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from typing import Iterable

from pocketquake import EQCYCLE_DIR
from pocketquake.scaffold import ClusterSpec, scaffold_all
from pocketquake.necis_bridge import download_events
from pocketquake import build_results_nb


# --------------------------------------------------------------- helpers
def _run(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> int:
    """Run a subprocess, streaming stdout/stderr live. Raises on non-zero exit."""
    pretty = " ".join(shlex.quote(c) for c in cmd)
    print(f"\n$ (cwd={cwd or '.'}) {pretty}", flush=True)
    proc = subprocess.run(cmd, cwd=cwd, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed (exit {proc.returncode}): {pretty}")
    return proc.returncode


def _run_eqcycle_stage(cluster: str, stage_from: str | None = None,
                       through: str | None = None,
                       picker: str = "phasenet_plus", extra: list[str] | None = None) -> None:
    """Invoke the eq-cycle CLI for a stage range."""
    cmd = [sys.executable, "-m", "pipeline.cli.run_pipeline", "--cluster", cluster, "--picker", picker]
    if stage_from:
        cmd += ["--stage-from", stage_from]
    if through:
        cmd += ["--through", through]
    if extra:
        cmd += extra

    # The CLI imports from `pipeline.*`, so the eq-cycle root must be on sys.path.
    env = os.environ.copy()
    env["PYTHONPATH"] = EQCYCLE_DIR + os.pathsep + env.get("PYTHONPATH", "")
    _run(cmd, cwd=EQCYCLE_DIR, env=env)


def _execute_notebook(path: str, timeout: int = 3600) -> None:
    """jupyter nbconvert --execute --inplace, fail on non-zero exit."""
    _run(["jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
          f"--ExecutePreprocessor.timeout={timeout}", path])


# --------------------------------------------------------------- the orchestrator
def orchestrate(catalog_csv: str, cluster: str, epicenter: tuple[float, float],
                region_bounds: tuple[float, float, float, float], *,
                region: str | None = None,
                networks: Iterable[str] = ("KS",),
                picker: str = "phasenet_plus",
                dtct_isolv: int = 1,
                run_focal_mechanism: bool = True,
                skip_download: bool = False,
                skip_pipeline: bool = False) -> dict:
    """End-to-end: scaffold → NECIS download → register → eq-cycle pipeline → results notebook.

    Returns paths/handles of the produced artifacts."""
    region = region or cluster.capitalize()
    spec = ClusterSpec(
        name=cluster, region=region, catalog_csv=catalog_csv,
        epicenter=tuple(epicenter), region_bounds=tuple(region_bounds),
        networks=tuple(networks), dtct_isolv=dtct_isolv,
    )

    # 1. scaffold + register (idempotent)
    info = scaffold_all(spec)
    waveforms_dir = os.path.join(info["src_root"], "kma_waveforms")
    print(f"[pocketquake] cluster scaffolded at {info['src_root']}")
    print(f"[pocketquake] cluster module:  {info['module']}")
    print(f"[pocketquake] config.py changes:  names={info['names_changed']}  src_dirs={info['src_dirs_changed']}")

    # 2. NECIS download (per-event SAC layout the eq-cycle reads natively)
    if not skip_download:
        catalog_in_cluster = os.path.join(info["src_root"], "event_catalog", "event_catalog.csv")
        print(f"\n[pocketquake] downloading waveforms via NECIS → {waveforms_dir}")
        download_events(catalog_csv=catalog_in_cluster, out_root=waveforms_dir,
                        data_types=("a", "v"), convert_sac=True)
    else:
        print("[pocketquake] --skip-download set; assuming waveforms are already in place")

    # 3. eq-cycle pipeline through dt.cc
    if not skip_pipeline:
        print("\n[pocketquake] running the eq-cycle relocation chain")
        _run_eqcycle_stage(cluster, through="dtcc", picker=picker)

        # 4. focal mechanisms (separate stage; PhaseNet+ picks already exist)
        if run_focal_mechanism:
            print("\n[pocketquake] running the focal_mechanism stage")
            _run_eqcycle_stage(cluster, stage_from="focal_mechanism",
                               through="focal_mechanism", picker=picker)

    # 5. build + execute the results notebook
    print("\n[pocketquake] generating + executing the results notebook")
    nb_path = build_results_nb.build(cluster)
    _execute_notebook(nb_path)

    return dict(src_root=info["src_root"], cluster_module=info["module"],
                waveforms_dir=waveforms_dir, notebook=nb_path)


# --------------------------------------------------------------- CLI
def _parse_pair(s: str, n: int, name: str) -> tuple[float, ...]:
    vals = [v.strip() for v in s.split(",") if v.strip()]
    if len(vals) != n:
        raise argparse.ArgumentTypeError(f"{name} must be {n} comma-separated floats, got {len(vals)}: {s!r}")
    return tuple(float(v) for v in vals)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="PocketQuake — catalog CSV to relocation summary, end-to-end.")
    ap.add_argument("catalog", help="Event catalog CSV (KMA columns: Year,Month,Day,Hour,Minute,Second,Latitude,Longitude,Magnitude,Depth — KST)")
    ap.add_argument("--cluster", required=True, help="Cluster slug (lowercase, no spaces), e.g. changnyeong")
    ap.add_argument("--region", default=None, help="Display name (default: cluster.capitalize())")
    ap.add_argument("--epicenter", required=True, type=lambda s: _parse_pair(s, 2, "--epicenter"),
                    help="Cluster centroid as 'lat,lon' (e.g. 35.463,128.427)")
    ap.add_argument("--region-bounds", required=True,
                    type=lambda s: _parse_pair(s, 4, "--region-bounds"),
                    help="Box as 'lat0,lat1,lon0,lon1' (e.g. 35.3,35.65,128.25,128.65)")
    ap.add_argument("--networks", default="KS",
                    help="Comma-separated station networks to bundle (default: KS)")
    ap.add_argument("--picker", default="phasenet_plus", choices=("stead", "phasenet_plus"),
                    help="PhaseNet weights to use for picking")
    ap.add_argument("--dtct-isolv", type=int, default=1, choices=(1, 2),
                    help="HypoDD dt.ct inversion: 1=SVD (small clusters), 2=LSQR (large)")
    ap.add_argument("--no-focal-mechanism", action="store_true", help="Skip the focal_mechanism stage")
    ap.add_argument("--skip-download", action="store_true",
                    help="Skip NECIS download (waveforms already exist in the cluster dir)")
    ap.add_argument("--skip-pipeline", action="store_true",
                    help="Skip the eq-cycle pipeline run (debugging the scaffolding / notebook only)")
    args = ap.parse_args(argv)

    orchestrate(
        catalog_csv=args.catalog,
        cluster=args.cluster,
        epicenter=args.epicenter,
        region_bounds=args.region_bounds,
        region=args.region,
        networks=tuple(s.strip() for s in args.networks.split(",") if s.strip()),
        picker=args.picker,
        dtct_isolv=args.dtct_isolv,
        run_focal_mechanism=not args.no_focal_mechanism,
        skip_download=args.skip_download,
        skip_pipeline=args.skip_pipeline,
    )


if __name__ == "__main__":
    main()
