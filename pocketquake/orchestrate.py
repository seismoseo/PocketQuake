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
from pocketquake import source_dispatch


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


def _located_count(cluster: str) -> int:
    """Events located across the cluster's HYPOINVERSE/HypoSVI `.sum` files (header-only = 0).
    Used to bail clearly when nothing was located rather than crash downstream."""
    import glob
    pat = os.path.join(EQCYCLE_DIR, "pipeline", "runs", cluster, "1.HypoInv", "*", "*.sum")
    n = 0
    for p in glob.glob(pat):
        try:
            n = max(n, sum(1 for _ in open(p)) - 1)   # minus the header line
        except OSError:
            pass
    return max(0, n)


def _load_cluster_cfg(cluster: str):
    """Re-load the just-written cluster config so we get the ClusterConfig (with
    stp_sac_root / radius_km / etc.), not the bare ClusterSpec."""
    import importlib
    if EQCYCLE_DIR not in sys.path:
        sys.path.insert(0, EQCYCLE_DIR)
    cluster_mod = importlib.import_module(f"pipeline.clusters.{cluster}")
    return cluster_mod.CONFIG


def _download_stp_for_cluster(cluster: str, *, networks: tuple[str, ...],
                              catalog_csv_override: str | None = None) -> None:
    """Single-source STP fetch — used directly by `--source stp` and as the first half
    of mixed mode. `catalog_csv_override` lets the mixed orchestrator point STP at a
    subset CSV (cutoff-eligible events only) instead of the full cluster catalog."""
    cfg = _load_cluster_cfg(cluster)
    if catalog_csv_override:
        # stp_bridge reads from cfg.event_catalog_csv; override transiently via dataclasses.replace
        from dataclasses import replace as dc_replace
        cfg = dc_replace(cfg, event_catalog_csv=catalog_csv_override)
    download_events_via_stp(cfg, networks=networks)


def _download_mixed_for_cluster(cluster: str, *, spec, info: dict,
                                catalog_csv: str, stp_cutoff: str | None) -> None:
    """Mixed-source orchestration: STP for the early subset, NECIS for the rest.

    Two modes:
      - `stp_cutoff` set → split catalog by UTC origin time first; STP gets the < cutoff
        events, NECIS gets the ≥ cutoff events. No wasted STP round-trips.
      - `stp_cutoff` None → try STP over the FULL catalog (STP silently returns nothing
        for late events), then determine which event_ids came back empty and fetch those
        via NECIS. Robust to drift in STP's coverage frontier without manual tuning.
    """
    src_root = info["src_root"]
    stp_sac_root = os.path.join(src_root, "stp_download", "SAC")
    necis_root = os.path.join(src_root, "kma_waveforms")
    tmp_dir = os.path.join(src_root, "event_catalog")
    stp_sub_csv = os.path.join(tmp_dir, "event_catalog_stp.csv")
    necis_sub_csv = os.path.join(tmp_dir, "event_catalog_necis.csv")

    if stp_cutoff:
        print(f"\n[pocketquake] mixed mode — strict date cutoff at {stp_cutoff} (UTC)")
        stp_df, necis_df = source_dispatch.split_by_cutoff(catalog_csv, stp_cutoff)
        print(f"  STP-eligible (UTC origin < {stp_cutoff}): {len(stp_df)} events")
        print(f"  NECIS-only   (UTC origin ≥ {stp_cutoff}): {len(necis_df)} events")
        source_dispatch.write_subset(stp_df, stp_sub_csv)
        source_dispatch.write_subset(necis_df, necis_sub_csv)
        if len(stp_df):
            print(f"\n[pocketquake] fetching {len(stp_df)} early events via STP → {stp_sac_root}")
            _download_stp_for_cluster(cluster, networks=tuple(spec.networks),
                                      catalog_csv_override=stp_sub_csv)
        if len(necis_df):
            print(f"\n[pocketquake] fetching {len(necis_df)} late events via NECIS → {necis_root}")
            download_events(catalog_csv=necis_sub_csv, out_root=necis_root,
                            data_types=("a", "v"), convert_sac=True)
        return

    # Default mode: try STP over the full catalog, NECIS-fallback for events that came back empty.
    print(f"\n[pocketquake] mixed mode — try-STP-first, NECIS fallback (no cutoff)")
    print(f"[pocketquake] attempting STP for all {sum(1 for _ in open(catalog_csv)) - 1} events → {stp_sac_root}")
    _download_stp_for_cluster(cluster, networks=tuple(spec.networks))
    failed = source_dispatch.find_failed_events(stp_sac_root, catalog_csv)
    print(f"\n[pocketquake] STP empty for {len(failed)} events — falling back to NECIS")
    if len(failed):
        source_dispatch.write_subset(failed, necis_sub_csv)
        download_events(catalog_csv=necis_sub_csv, out_root=necis_root,
                        data_types=("a", "v"), convert_sac=True)
    else:
        print("  (every event got SACs from STP — no NECIS fetch needed)")


# --------------------------------------------------------------- the orchestrator
def orchestrate(catalog_csv: str, cluster: str, epicenter: tuple[float, float],
                region_bounds: tuple[float, float, float, float], *,
                region: str | None = None,
                networks: Iterable[str] | None = None,
                picker: str = "phasenet_plus",
                dtct_isolv: int = 1,
                wf_backend: str = "necis",
                loc_backend: str = "hypoinverse",
                reloc_backend: str = "hypodd",
                stp_cutoff: str | None = None,
                run_focal_mechanism: bool = True,
                skip_download: bool = False,
                skip_pipeline: bool = False,
                cores: int | None = None) -> dict:
    """End-to-end: scaffold → waveform download → register → eq-cycle pipeline → results notebook.

    `wf_backend` picks the waveform source:
      - "necis": KMA NECIS event-segment archive (post-2020 events, the default).
      - "stp":   SNU SAC Transfer Protocol via the sgtlab account (older events that NECIS
                 no longer serves as downloadable segments).
      - "mixed": split per-event between STP and NECIS so a single catalog can span the
                 transition. Default routing is **try-STP-first with NECIS fallback** for
                 every event; pass `stp_cutoff="YYYY-MM-DD"` to instead skip STP for events
                 with UTC origin ≥ cutoff (no failed-STP round-trips for known-late events).

    `networks` is the station-network roster. **`None` resolves to a backend-appropriate default**:
      - `wf_backend="necis"` → `("KS",)`  — NECIS only bundles KS in its event-segment zips.
      - `wf_backend="stp"`   → `("KS", "KG")`  — STP serves BOTH networks for the same event,
        and dropping KG would lose ~60 stations of azimuthal coverage on every cluster, which
        matters most for focal-mechanism inversions. Pass `networks=("KS",)` to revert to the
        v1.4.2 single-network behaviour.
      - `wf_backend="mixed"` → `("KS", "KG")` — the STP-half of the catalog gains KG just like
        a pure STP cluster; the NECIS-half is KS-only natively (NECIS event ZIPs do not bundle
        KG). The eq-cycle station table comes from STP so it's the historical-inclusive roster.

    Returns paths/handles of the produced artifacts."""
    if networks is None:
        networks = ("KS",) if wf_backend == "necis" else ("KS", "KG")
    region = region or cluster.capitalize()
    spec = ClusterSpec(
        name=cluster, region=region, catalog_csv=catalog_csv,
        epicenter=tuple(epicenter), region_bounds=tuple(region_bounds),
        networks=tuple(networks), dtct_isolv=dtct_isolv, wf_backend=wf_backend,
        loc_backend=loc_backend, reloc_backend=reloc_backend,
    )

    # 1. scaffold + register (idempotent)
    info = scaffold_all(spec)
    if wf_backend == "stp":
        waveforms_dir = os.path.join(info["src_root"], "stp_download", "SAC")
    elif wf_backend == "mixed":
        # Mixed clusters live in BOTH trees; report the STP root as the "primary" handle
        # but the orchestrator fetches into both below.
        waveforms_dir = os.path.join(info["src_root"], "stp_download", "SAC")
    else:
        waveforms_dir = os.path.join(info["src_root"], "kma_waveforms")
    print(f"[pocketquake] cluster scaffolded at {info['src_root']}")
    print(f"[pocketquake] cluster module:  {info['module']}")
    print(f"[pocketquake] config.py changes:  names={info['names_changed']}  src_dirs={info['src_dirs_changed']}")
    print(f"[pocketquake] wf_backend:     {wf_backend}"
          + (f"  (stp_cutoff={stp_cutoff})" if wf_backend == "mixed" and stp_cutoff else ""))
    print(f"[pocketquake] loc_backend:    {loc_backend}    reloc_backend:  {reloc_backend}")

    # 2. waveform download
    if not skip_download:
        catalog_in_cluster = os.path.join(info["src_root"], "event_catalog", "event_catalog.csv")
        if wf_backend == "stp":
            print(f"\n[pocketquake] fetching waveforms via STP → {waveforms_dir}")
            _download_stp_for_cluster(cluster, networks=tuple(spec.networks))
        elif wf_backend == "mixed":
            _download_mixed_for_cluster(cluster, spec=spec, info=info,
                                        catalog_csv=catalog_in_cluster,
                                        stp_cutoff=stp_cutoff)
        else:
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

        # Guard: if 0 events were located (e.g. --skip-download with no waveforms on disk,
        # or every pick below threshold), the .sum is header-only and the focal-mechanism +
        # notebook stages have nothing to read. Stop with a clear, actionable message instead
        # of crashing deep inside a reader.
        if _located_count(cluster) == 0:
            print("\n[pocketquake] ✗ 0 events located — nothing to relocate or plot.\n"
                  "    Most likely: no waveforms on disk. If you passed --skip-download, the\n"
                  f"    waveforms must already be under {waveforms_dir} — drop --skip-download\n"
                  "    to fetch them, or point at the slug that already has them.\n"
                  "    (Also check picks cleared threshold: see the 'picking: N picks' line above.)")
            return dict(src_root=info["src_root"], cluster_module=info["module"],
                        waveforms_dir=waveforms_dir, notebook=None)

        # 4. focal mechanisms (separate stage; PhaseNet+ picks already exist)
        if run_focal_mechanism:
            print("\n[pocketquake] running the focal_mechanism stage")
            _run_eqcycle_stage(cluster, stage_from="focal_mechanism",
                               through="focal_mechanism", picker=picker)

    # 5. build + execute the results notebook (only when the pipeline ran — the notebook
    # reads the sum files the pipeline produces; skipping the pipeline + executing the
    # notebook is guaranteed to FileNotFoundError on Yeongyang.sum / etc.)
    if not skip_pipeline:
        print("\n[pocketquake] generating + executing the results notebook")
        nb_path = build_results_nb.build(cluster)
        _execute_notebook(nb_path)
    else:
        print("\n[pocketquake] --skip-pipeline set; skipping the results notebook too "
              "(it requires sum files the pipeline produces)")
        nb_path = None

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
    ap.add_argument("--loc-backend", default="hypoinverse", choices=("hypoinverse", "hyposvi"),
                    help="Absolute-location backend: hypoinverse (Fortran hyp1.40, default) | "
                         "hyposvi (Python, needs a trained EikoNet via HYPOSVI_EIKONET_P/S)")
    ap.add_argument("--reloc-backend", default="hypodd", choices=("hypodd", "relocdd_py"),
                    help="Relative-relocation backend: hypodd (Fortran ph2dt+hypoDD, default) | "
                         "relocdd_py (Python port, needs the clone via RELOCDD_PY_DIR)")
    ap.add_argument("--no-focal-mechanism", action="store_true", help="Skip the focal_mechanism stage")
    ap.add_argument("--skip-download", action="store_true",
                    help="Skip waveform download (waveforms already exist in the cluster dir)")
    ap.add_argument("--skip-pipeline", action="store_true",
                    help="Skip the eq-cycle pipeline run (debugging the scaffolding / notebook only)")
    ap.add_argument("--wf-backend", default="necis", choices=("necis", "stp", "mixed"),
                    help="Waveform source: necis (KMA NECIS, default, post-2020 events) | "
                         "stp (SNU SAC Transfer Protocol, older events) | "
                         "mixed (per-event dispatch; default try-STP-first with NECIS fallback, "
                         "or strict date split via --stp-cutoff)")
    ap.add_argument("--stp-cutoff", default=None,
                    help="Only meaningful with --wf-backend=mixed. ISO date (e.g. 2024-10-01); "
                         "events with UTC origin ≥ this date skip STP and go straight to NECIS. "
                         "Omit to use try-STP-first with NECIS fallback for every event.")
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
        loc_backend=args.loc_backend,
        reloc_backend=args.reloc_backend,
        stp_cutoff=args.stp_cutoff,
        run_focal_mechanism=not args.no_focal_mechanism,
        skip_download=args.skip_download,
        skip_pipeline=args.skip_pipeline,
        cores=args.cores,
    )


if __name__ == "__main__":
    main()
