"""Incremental cluster augmentation: add new catalog events to an already-processed run.

Given an augmented catalog CSV for an existing cluster, download / gather / pick / locate
ONLY the new events, reuse every existing per-event artifact (picks, SAC pick headers,
per-pair dt.cc files, xcorr interp cache), and re-run the cheap whole-cluster stages to
produce a fully relocated N-event result.

Reuse guarantees and the mechanisms behind them:
  - Event identity is pinned by `runs/<cluster>/event_manifest.csv` (evmap.pin_manifest):
    existing events keep their current cuspids byte-identically, new events append after —
    so cached .sum/event.dat/dt.ct/dt.cc content stays valid even for events that interleave
    in time with the existing ones.
  - Existing events are NEVER re-gathered or re-picked (`--events` subsets); re-picking
    already-rereferenced SACs is a documented data-degradation gotcha.
  - HYPOINVERSE re-runs over the whole cluster (hyp1.40 locates each event independently,
    so existing solutions reproduce) and that is VERIFIED against a pre-augment snapshot
    (pipeline.core.augment.verify_sums, tolerances 5 ms / 1e-4 deg / 0.05 km); any event
    that moved gets its cached dt.cc pairs invalidated and recomputed.
  - rereference skips SACs already at the .sum origin (2 ms tolerance), preserving mtimes
    for the interp cache; xcorr runs with --xcorr-resume so only new-vs-all and new-vs-new
    pairs are computed (existing C(N,2) pairs are reused).
  - dt.ct / dt.cc HypoDD inversions, focal mechanisms, the results notebook, and the PDF
    report re-run over the full augmented cluster (they are cheap); stale bootstrap error
    caches are cleared (and are also event-set-tagged upstream).

Policy: augmentation is strictly ADDITIVE. If the new catalog is missing events that exist
in the run, the augment aborts listing them — removing events is a deliberate fresh-run
decision, not an augment.
"""
from __future__ import annotations

import os
import sys
import shutil
from dataclasses import dataclass, field, replace as dc_replace
from datetime import datetime
from glob import glob

from pocketquake import EQCYCLE_DIR
from pocketquake.necis_bridge import download_events
from pocketquake import source_dispatch


def _pipeline():
    """Import the eq-cycle `pipeline` package (submodule root on sys.path)."""
    if EQCYCLE_DIR not in sys.path:
        sys.path.insert(0, EQCYCLE_DIR)
    from pipeline import config as pcfg
    from pipeline.core import waveforms as pwf, evmap, xcorr
    from pipeline.core import augment as paug
    return pcfg, pwf, evmap, xcorr, paug


# --------------------------------------------------------------- planning
@dataclass
class AugmentPlan:
    existing_ids: list          # event_ids with a processed waveform dir in runs/<c>/
    new_ids: list               # catalog event_ids without a processed dir -> to add
    missing_ids: list           # processed event_ids ABSENT from the new catalog -> abort
    changed_ids: list = field(default_factory=list)   # common ids whose catalog row changed
    catalog_csv: str = ""       # the new (augmented) catalog path


def plan_augment(cfg, catalog_csv: str) -> AugmentPlan:
    """Diff the new catalog against the processed run (waveform dirs are ground truth).

    Event ids are derived with the pipeline's own loader (identical KST-9h semantics)."""
    pcfg, pwf, *_ = _pipeline()
    new_rows = {r["event_id"]: r for r in
                pwf.load_catalog(dc_replace(cfg, event_catalog_csv=catalog_csv))}
    old_rows = {r["event_id"]: r for r in pwf.load_catalog(cfg)}
    existing = sorted(os.path.basename(d)
                      for d in glob(os.path.join(pcfg.waveforms_dir(cfg), "20*")))
    changed = [e for e in existing
               if e in new_rows and e in old_rows and any(
                   abs(new_rows[e][k] - old_rows[e][k]) > 1e-9
                   for k in ("lat", "lon", "depth", "mag"))]
    return AugmentPlan(
        existing_ids=existing,
        new_ids=sorted(set(new_rows) - set(existing)),
        missing_ids=sorted(set(existing) - set(new_rows)),
        changed_ids=changed,
        catalog_csv=catalog_csv,
    )


def write_merged_catalog(cfg, plan: AugmentPlan) -> tuple[str, str]:
    """Backup + merge the cluster catalog; write the new-events-only download subset.

    The merged catalog keeps the OLD rows for existing events (guards .phs stability even
    if KMA later revised their metadata — revisions are warned, not applied) and appends
    the new catalog's rows for the new events, time-sorted. Returns (merged, subset)."""
    import pandas as pd
    pcfg, pwf, *_ = _pipeline()
    old_csv = cfg.event_catalog_csv
    backup = old_csv + ".pre_augment_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(old_csv, backup)
    print(f"[augment] catalog backup -> {backup}")

    old_df = pd.read_csv(old_csv, encoding="utf-8-sig")
    new_df = pd.read_csv(plan.catalog_csv, encoding="utf-8-sig")
    # align the new catalog's columns to the old one's (case-insensitive)
    lc_new = {c.strip().lower(): c for c in new_df.columns}
    try:
        new_aligned = new_df[[lc_new[c.strip().lower()] for c in old_df.columns]]
    except KeyError as e:
        raise SystemExit(f"[augment] new catalog is missing column {e} present in the "
                         f"cluster catalog ({old_csv})")
    new_aligned.columns = old_df.columns

    # row index -> event_id maps, via the pipeline's own loader
    old_ids = [r["event_id"] for r in pwf.load_catalog(cfg)]
    new_ids = [r["event_id"] for r in
               pwf.load_catalog(dc_replace(cfg, event_catalog_csv=plan.catalog_csv))]
    # idempotency: a re-run after an interrupted augment finds the previous merge already in
    # the cluster catalog — keep only rows outside new_ids there, then append fresh new rows
    keep = [i for i, e in enumerate(old_ids) if e not in set(plan.new_ids)]
    old_keep = old_df.iloc[keep]
    add_rows = new_aligned.iloc[[i for i, e in enumerate(new_ids) if e in set(plan.new_ids)]]

    merged = pd.concat([old_keep, add_rows], ignore_index=True)
    merged["_eid"] = [old_ids[i] for i in keep] + [e for e in new_ids if e in set(plan.new_ids)]
    merged = merged.sort_values("_eid").drop(columns="_eid")
    merged.to_csv(old_csv, index=False)
    print(f"[augment] merged catalog: {len(old_keep)} existing + {len(add_rows)} new rows "
          f"-> {old_csv}")

    subset = os.path.join(os.path.dirname(old_csv), "event_catalog_augment.csv")
    add_native = new_df.iloc[[i for i, e in enumerate(new_ids) if e in set(plan.new_ids)]]
    add_native.to_csv(subset, index=False)
    return old_csv, subset


# --------------------------------------------------------------- preflight
def _preflight(cfg, cluster: str, velmodel: str, picker: str) -> None:
    pcfg, *_ = _pipeline()
    module = os.path.join(EQCYCLE_DIR, "pipeline", "clusters", f"{cluster}.py")
    if not os.path.exists(module):
        raise SystemExit(f"[augment] no cluster module {module} — --augment requires a "
                         f"previously scaffolded + processed cluster (run without --augment first)")
    dirs = sorted(glob(os.path.join(pcfg.waveforms_dir(cfg), "20*")))
    if len(dirs) < 2:
        raise SystemExit(f"[augment] runs/{cluster}/waveforms_100km has {len(dirs)} event "
                         f"dirs — nothing to augment (run the normal pipeline first)")
    sum_path = pcfg.sum_file(cfg, velmodel)
    if not os.path.exists(sum_path):
        raise SystemExit(f"[augment] {sum_path} missing — the previous run did not complete "
                         f"the hypoinverse stage for {velmodel}")
    no_picks = [os.path.basename(d) for d in dirs
                if not os.path.exists(pcfg.picks_csv(cfg, os.path.basename(d)))]
    if no_picks:
        raise SystemExit(f"[augment] {len(no_picks)} existing events have no picks CSV "
                         f"(e.g. {no_picks[:3]}) — previous run incomplete, refusing")
    if picker == "phasenet_plus":
        with open(pcfg.picks_csv(cfg, os.path.basename(dirs[0]))) as f:
            header = f.readline()
        if "Polarity" not in header:
            print(f"[augment] WARN existing picks lack a Polarity column — the previous run "
                  f"probably used --picker stead; new events will be picked with "
                  f"{picker}, mixing pick styles")


# --------------------------------------------------------------- downloads
def _download_new(cfg, cluster: str, subset_csv: str) -> None:
    """Fetch waveforms for the new events only, honoring the cluster's wf_source."""
    from pocketquake.orchestrate import _download_stp_for_cluster
    src_root = cfg.src_root
    networks = ("KS",) if cfg.wf_source == "kma_archive" else ("KS", "KG")
    if cfg.wf_source == "stp_sac":
        _download_stp_for_cluster(cluster, networks=networks, catalog_csv_override=subset_csv)
    elif cfg.wf_source == "mixed":
        stp_sac_root = os.path.join(src_root, "stp_download", "SAC")
        _download_stp_for_cluster(cluster, networks=networks, catalog_csv_override=subset_csv)
        failed = source_dispatch.find_failed_events(stp_sac_root, subset_csv)
        if len(failed):
            fb = os.path.join(src_root, "event_catalog", "event_catalog_augment_necis.csv")
            source_dispatch.write_subset(failed, fb)
            download_events(catalog_csv=fb, out_root=os.path.join(src_root, "kma_waveforms"),
                            data_types=("a", "v"), convert_sac=True)
    else:                                              # "kma_archive" -> NECIS
        download_events(catalog_csv=subset_csv,
                        out_root=os.path.join(src_root, "kma_waveforms"),
                        data_types=("a", "v"), convert_sac=True)


# --------------------------------------------------------------- the driver
def augment_cluster(catalog_csv: str, cluster: str, *,
                    picker: str = "phasenet_plus",
                    velmodel: str = "kim1983",
                    cores: int | None = None,
                    run_focal_mechanism: bool = True,
                    skip_download: bool = False,
                    dry_run: bool = False) -> dict:
    """Add the new events of `catalog_csv` to the processed cluster and re-relocate all."""
    from pocketquake.orchestrate import _run_eqcycle_stage, _execute_notebook
    from pocketquake import build_results_nb
    pcfg, pwf, evmap, xcorr, paug = _pipeline()

    import importlib
    cfg = importlib.import_module(f"pipeline.clusters.{cluster}").CONFIG
    _preflight(cfg, cluster, velmodel, picker)

    # 1-3. snapshot + diff
    snapshot = paug.sum_snapshot(cfg)
    plan = plan_augment(cfg, catalog_csv)
    n_old, n_new = len(plan.existing_ids), len(plan.new_ids)
    print(f"[augment] {cluster}: {n_old} existing events, {n_new} new, "
          f"{len(plan.missing_ids)} missing from the new catalog")
    if plan.missing_ids:
        raise SystemExit(
            f"[augment] ABORT — the new catalog is missing {len(plan.missing_ids)} events "
            f"that exist in the processed run:\n    " + "\n    ".join(plan.missing_ids)
            + "\n  Augmentation is strictly additive. To remove events, run a fresh cluster.")
    for e in plan.changed_ids:
        print(f"[augment] WARN catalog metadata changed for existing event {e} — keeping "
              f"the ORIGINAL row (guards location reproducibility); revise via a fresh run")
    if not plan.new_ids:
        print("[augment] nothing to add — the catalog matches the processed run.")
        return dict(new_events=[], notebook=None)
    if dry_run:
        print("[augment] DRY RUN — new events that would be added:")
        for e in plan.new_ids:
            print(f"    {e}")
        return dict(new_events=plan.new_ids, notebook=None, dry_run=True)

    # 4. pin event identity BEFORE anything else (appended ids are inert until their
    # waveform dirs appear, so this is safe pre-download)
    mp = evmap.pin_manifest(cfg, plan.new_ids)
    print(f"[augment] cuspids pinned: {n_old} existing frozen + {n_new} appended -> {mp}")

    # 5. merge catalog + write the download subset
    _, subset_csv = write_merged_catalog(cfg, plan)

    # 6. download new events only
    if skip_download:
        print("[augment] --skip-download set; assuming new-event waveforms are in place")
    else:
        print(f"\n[augment] downloading {n_new} new events ({cfg.wf_source})")
        _download_new(cfg, cluster, subset_csv)

    # 6b. availability check: very recent events may not be served yet (e.g. NECIS's
    # processing delay). Proceed with what arrived; pending events are retried simply by
    # re-running the same --augment later (they will still diff as "new").
    from pipeline.core import stations as pstations
    available = [e for e in plan.new_ids if pstations.event_raw_dir(cfg, e) is not None]
    pending = sorted(set(plan.new_ids) - set(available))
    if pending:
        print(f"[augment] WARN {len(pending)}/{n_new} new events have no waveforms from "
              f"{cfg.wf_source} yet (not served?) — proceeding without them; re-run the "
              f"same --augment later to pick them up:")
        for e in pending:
            print(f"    {e}")
    if not available:
        print("[augment] none of the new events are available from the waveform source yet "
              "— nothing to add this round; re-run later.")
        return dict(new_events=[], pending=pending, notebook=None)
    n_new = len(available)

    # 7. gather + pick the new events only (existing SACs/picks untouched)
    ev_arg = ",".join(available)
    _run_eqcycle_stage(cluster, stage_from="stations", through="picking",
                       picker=picker, extra=["--events", ev_arg])

    # 8. whole-cluster absolute location + catalog double-difference
    _run_eqcycle_stage(cluster, stage_from="hypoinverse", through="dtct",
                       picker=picker, extra=["--arc-velmodel", velmodel])

    # 9. verify existing solutions reproduced; invalidate moved events' cached pairs
    moved = paug.verify_sums(cfg, snapshot)
    movers = sorted({e for eids in moved.values() for e in eids})
    if movers:
        n_inv = xcorr.invalidate_pairs(cfg, movers)
        print(f"[augment] {len(movers)} existing events moved beyond tolerance — "
              f"invalidated {n_inv} cached dt.cc pair files (will recompute)")

    # 10. stale-cache hygiene
    for p in paug.clear_bootstrap_caches(cfg):
        print(f"[augment] cleared stale bootstrap cache {p}")

    # 11. dt.cc chain with pair reuse
    pre_pairs = len(glob(os.path.join(pcfg.dtcc_dir(cfg), "dt.cc_P", "dt.cc_P_*")))
    extra = ["--arc-velmodel", velmodel, "--xcorr-resume"]
    if cores is not None:
        extra += ["--cores", str(cores)]
    _run_eqcycle_stage(cluster, stage_from="rereference", through="dtcc",
                       picker=picker, extra=extra)
    post_pairs = len(glob(os.path.join(pcfg.dtcc_dir(cfg), "dt.cc_P", "dt.cc_P_*")))

    # 12. tail: focal mechanisms + results notebook + PDF report (full cluster)
    if run_focal_mechanism:
        _run_eqcycle_stage(cluster, stage_from="focal_mechanism", through="focal_mechanism",
                           picker=picker, extra=["--fm-velmodel", velmodel])
    # bootstraps were cleared in step 10 (event set changed) — recompute them OUTSIDE the
    # notebook, where no nbconvert per-cell timeout applies (2x1000 replicas can far exceed
    # it on a big cluster / loaded box)
    print("\n[augment] precomputing the bootstrap error bars (outside the notebook)")
    from pocketquake.orchestrate import _precompute_bootstraps
    _precompute_bootstraps(cluster)
    print("\n[augment] generating + executing the results notebook")
    nb_path = build_results_nb.build(cluster, velmodel=velmodel)
    _execute_notebook(nb_path)
    _run_eqcycle_stage(cluster, stage_from="report", through="report",
                       picker=picker, extra=["--fm-velmodel", velmodel])

    # 13. reuse summary
    total = n_old + n_new
    print(f"\n[augment] === {cluster} augmentation summary ===")
    print(f"  events:      {n_old} reused + {n_new} added = {total}"
          + (f"  ({len(pending)} pending — not served yet, re-run to retry)" if pending else ""))
    print(f"  picks:       {n_old} reused (never re-picked)")
    print(f"  xcorr pairs: {pre_pairs} reused + {post_pairs - pre_pairs} computed "
          f"= {post_pairs} (full set C({total},2) = {total * (total - 1) // 2})")
    for vm, eids in moved.items():
        print(f"  {vm} .sum:  existing rows reproduced {n_old - len(eids)}/{n_old}")
    return dict(new_events=available, pending=pending, notebook=nb_path,
                pairs_reused=pre_pairs, pairs_computed=post_pairs - pre_pairs, moved=moved)
