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
from pocketquake.stp_bridge import download_events_via_stp
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
                networks: Iterable[str] | None = None,
                picker: str = "phasenet_plus",
                dtct_isolv: int = 1,
                wf_backend: str = "necis",
                run_focal_mechanism: bool = True,
                skip_download: bool = False,
                skip_pipeline: bool = False,
                cores: int | None = None) -> dict:
    """End-to-end: scaffold → waveform download → register → eq-cycle pipeline → results notebook.

    `wf_backend` picks the waveform source:
      - "necis": KMA NECIS event-segment archive (post-2020 events, the default).
      - "stp":   SNU SAC Transfer Protocol via the sgtlab account (older events that NECIS
                 no longer serves as downloadable segments).

    `networks` is the station-network roster. **`None` resolves to a backend-appropriate default**:
      - `wf_backend="necis"` → `("KS",)`  — NECIS only bundles KS in its event-segment zips.
      - `wf_backend="stp"`   → `("KS", "KG")`  — STP serves BOTH networks for the same event,
        and dropping KG would lose ~60 stations of azimuthal coverage on every cluster, which
        matters most for focal-mechanism inversions. Pass `networks=("KS",)` to revert to the
        v1.4.2 single-network behaviour.

    Returns paths/handles of the produced artifacts."""
    if networks is None:
        networks = ("KS", "KG") if wf_backend == "stp" else ("KS",)
    region = region or cluster.capitalize()
    spec = ClusterSpec(
        name=cluster, region=region, catalog_csv=catalog_csv,
        epicenter=tuple(epicenter), region_bounds=tuple(region_bounds),
        networks=tuple(networks), dtct_isolv=dtct_isolv, wf_backend=wf_backend,
    )

    # 1. scaffold + register (idempotent)
    info = scaffold_all(spec)
    if wf_backend == "stp":
        waveforms_dir = os.path.join(info["src_root"], "stp_download", "SAC")
    else:
        waveforms_dir = os.path.join(info["src_root"], "kma_waveforms")
    print(f"[pocketquake] cluster scaffolded at {info['src_root']}")
    print(f"[pocketquake] cluster module:  {info['module']}")
    print(f"[pocketquake] config.py changes:  names={info['names_changed']}  src_dirs={info['src_dirs_changed']}")
    print(f"[pocketquake] wf_backend:     {wf_backend}")

    # 2. waveform download
    if not skip_download:
        if wf_backend == "stp":
            print(f"\n[pocketquake] fetching waveforms via STP → {waveforms_dir}")
            # Re-load the cluster config we just wrote so we get the proper ClusterConfig
            # with stp_sac_root / radius_km / etc., not the bare ClusterSpec.
            import importlib, sys
            if EQCYCLE_DIR not in sys.path:
                sys.path.insert(0, EQCYCLE_DIR)
            cluster_mod = importlib.import_module(f"pipeline.clusters.{cluster}")
            cfg = cluster_mod.CONFIG
            # Pass the resolved networks tuple so the STP `win` commands include KG (default
            # for stp backend) — otherwise stp_bridge.download_events_via_stp's own default
            # of ("KS","KG") could silently disagree with the scaffold's station-table coverage.
            download_events_via_stp(cfg, networks=tuple(spec.networks))
        else:
            catalog_in_cluster = os.path.join(info["src_root"], "event_catalog", "event_catalog.csv")
            print(f"\n[pocketquake] downloading waveforms via NECIS → {waveforms_dir}")
            download_events(catalog_csv=catalog_in_cluster, out_root=waveforms_dir,
                            data_types=("a", "v"), convert_sac=True)
    else:
        print("[pocketquake] --skip-download set; assuming waveforms are already in place")

    # 3. eq-cycle pipeline through dt.cc
    if not skip_pipeline:
        extra = ["--cores", str(cores)] if cores is not None else None
        print("\n[pocketquake] running the eq-cycle relocation chain"
              + (f"  (xcorr workers capped at {cores})" if cores is not None else ""))
        _run_eqcycle_stage(cluster, through="dtcc", picker=picker, extra=extra)

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
    ap.add_argument("--networks", default=None,
                    help="Comma-separated station networks to bundle. "
                         "Default depends on --wf-backend: NECIS → 'KS' (only network NECIS bundles); "
                         "STP → 'KS,KG' (both networks are in the STP archive, and KG roughly "
                         "doubles azimuthal coverage on the southeastern peninsula). "
                         "Pass --networks=KS to force single-network on either backend.")
    ap.add_argument("--picker", default="phasenet_plus", choices=("stead", "phasenet_plus"),
                    help="PhaseNet weights to use for picking")
    ap.add_argument("--dtct-isolv", type=int, default=1, choices=(1, 2),
                    help="HypoDD dt.ct inversion: 1=SVD (small clusters), 2=LSQR (large)")
    ap.add_argument("--no-focal-mechanism", action="store_true", help="Skip the focal_mechanism stage")
    ap.add_argument("--skip-download", action="store_true",
                    help="Skip waveform download (waveforms already exist in the cluster dir)")
    ap.add_argument("--skip-pipeline", action="store_true",
                    help="Skip the eq-cycle pipeline run (debugging the scaffolding / notebook only)")
    ap.add_argument("--wf-backend", default="necis", choices=("necis", "stp"),
                    help="Waveform source: necis (KMA NECIS, default, post-2020 events) | "
                         "stp (SNU SAC Transfer Protocol, older events)")
    ap.add_argument("--cores", type=int, default=None,
                    help="Worker cap for the eq-cycle xcorr stage. Forwarded as `--cores N` to "
                         "`pipeline.cli.run_pipeline`, which uses a ProcessPoolExecutor capped at "
                         "min(N, |sched_getaffinity|). Default (None) → uses each cluster's "
                         "`cfg.num_cores` (typically 10). Set lower on memory-constrained boxes "
                         "(observed: ~24 GB / worker on Yeoncheon's dt.cc xcorr).")
    args = ap.parse_args(argv)

    orchestrate(
        catalog_csv=args.catalog,
        cluster=args.cluster,
        epicenter=args.epicenter,
        region_bounds=args.region_bounds,
        region=args.region,
        networks=(tuple(s.strip() for s in args.networks.split(",") if s.strip())
                  if args.networks else None),
        picker=args.picker,
        dtct_isolv=args.dtct_isolv,
        wf_backend=args.wf_backend,
        run_focal_mechanism=not args.no_focal_mechanism,
        skip_download=args.skip_download,
        skip_pipeline=args.skip_pipeline,
        cores=args.cores,
    )


if __name__ == "__main__":
    main()
