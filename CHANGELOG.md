# Changelog

Versioning follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).
The single source of truth is `pocketquake.__version__`; `pyproject.toml` reads it via setuptools dynamic.

## 0.5.2 — 2026-05-30

`plot_record_section` was temporally mis-aligned in v0.5.1 — the y-axis used **epicentral** distance
(`sac.dist`) but the overlaid moveout line was drawn at `t = epi / V`, which ignores the focal-depth
contribution to slant distance. For shallow events at close stations, hypocentral can be ~2× the
epicentral, so the picks landed visibly to the right of the (wrongly-drawn) moveout line — looking
"wrong" even when they were correct. Fixed by mirroring the Ridgecrest reference implementation at
`12.Ridgecrest/scripts/02_phase_picking.py:894, 1296`.

**Fixed**
- `pipeline.viz.plot_record_section` now uses **hypocentral distance** for both the y-axis and the
  predicted moveout: `hypo = sqrt(epi² + evdp²)`, where `evdp` is the **per-event catalog depth**
  (via `pipeline.core.waveforms.load_catalog`), falling back to `cfg.pick_window["evdp"]`.
- Origin-relative time axis computed Ridgecrest-style: `origin_abs = starttime − sac.b + sac.o`,
  `t_rel = tr.times() + (starttime − origin_abs)`. Picks from the CSV are subtracted by the same
  per-station `origin_abs`, so absolute UTC pick times align with the trace times even after the
  `rereference` stage has shifted the SAC reference (`nz*`).
- Predicted-moveout lines now start at `hypo = evdp` (the closest a station can be in slant range),
  not at zero — a station directly above the source has hypocentral distance = depth, not 0.
- Title now annotates `depth = X km` so the reader knows which depth was used.

**Added**
- `03_results_chungju.ipynb` ships as a worked example: same builder, but with the dt.cc / focal-
  mechanism / fault-frame sections gracefully empty (chungju's pipeline crashes at dtct on the v0.5.1
  HypControl issue — separate fix; the notebook still shows locations + picks + record sections so
  you can see what a "what does the QC look like before per-cluster HypControl tuning" looks like).

**Verified**
- changnyeong: notebook regenerated; the closest-station predicted P moveout moved from `epi/Vp` to
  `hypo/Vp` (factor 1.6× at the closest station), and the picks now sit on the dashed line.
- chungju: AGSA (epi 6.85 km, depth 7 km, hypo 9.79 km) predicted P = 1.66 s; the actual pick at
  +2.48 s now reads as a clean +0.8 s residual (consistent with the +1 s origin-time offset seen
  across all chungju events), where v0.5.1 showed it as +1.3 s — same data, correctly aligned.

## 0.5.1 — 2026-05-30

Picking-window fix + distance-record-section QC. Driven by the **chungju self-test** revealing that the
eq-cycle picking window was computed from a hardcoded global focal depth (`evdp=15 km`) regardless of
catalog depth — for shallow events (chungju 6–9 km) at close stations the window starts seconds AFTER the
true P arrival, so PhaseNet+ misses P and labels later phases (S, coda) as P.

**Added**
- `pipeline.viz.plot_record_section(cfg, event_id, prob_min=None, max_dist_km=100, ...)` — distance
  record section per event: Z-component traces ordered by epicentral distance with AI picks
  overlaid as vertical ticks (P=red, S=blue) and predicted P/S moveout curves (red/blue dashed)
  for at-a-glance pick QC. Defaults to the picker's own thresholds (`cfg.p_threshold`, `cfg.s_threshold`)
  so every emitted pick shows. Lives in the eq-cycle submodule (local working-tree edit).
- `pocketquake/build_results_nb.py` now auto-includes a **Picks QC** section in every generated
  `03_results_<cluster>.ipynb` — one record section per event in the catalog.

**Fixed**
- `pipeline.core.picking.pick_event` and `pick_event_pnplus` now read the per-event catalog depth
  (`ev["depth"]`) as `evdp` for the picking window, falling back to the cluster default if the catalog
  entry is missing/non-positive. Window offsets widened (`-2 / +6 s` vs `-1 / +4 s`) to absorb residual
  depth/velocity uncertainty. Local working-tree edit in the eq-cycle submodule.

**Verified**
- changnyeong: filtered RMS, depths, and dt.cc reloc identical to v0.5.0 (3-event 2024-09-12 swarm at
  35.5432/128.4868/~10.2 km, mainshock treatment still applied). Notebook 30 cells, 0 errors, 3
  record-section figures.
- chungju (the canary): picks are visibly improved — close-station P now appears with median residual
  ~+0.75 s vs predicted moveout (was missing entirely), AGSA's P pick at 2.48 s now exists. Distance
  record section shows the picks aligned along the predicted Vp moveout line.
- **Note**: even with the picking fix, chungju ph2dt still rejects all event-pair phases (residuals
  ~+0.8–1 s exceed the default HypoInverse RMS scale of 0.12 s). For chungju to relocate end-to-end, the
  user also needs a cluster-specific `HypControl(RMS=(4, 0.50, 2, 4), ZTR=(7,"T"), DIS=(4,100,1,3))`
  override in `pipeline/clusters/chungju.py` — documented as an example in `docs/workflow.md`. This is a
  per-cluster tuning decision, not a framework default.

## 0.5.0 — 2026-05-30

First versioned cut. Verified end-to-end on the bundled 3-event Changnyeong catalog (≈13 min
wall-clock; NECIS download dominates). Includes the Gwangyang-style mainshock-treatment chain.

**Added**
- `pocketquake/` package: `orchestrate.py` (CLI + `orchestrate()`), `scaffold.py`
  (`ClusterSpec`, `scaffold_all`, `register_cluster`), `necis_bridge.py` (`download_events`,
  `auth_ping`), `build_results_nb.py` (generates `03_results_<cluster>.ipynb`).
- `pocketquake.sh` — friendly one-command wrapper. Auto-derives epicenter (catalog centroid)
  and bounds (catalog bbox + 0.2°); preflight checks the catalog schema, slug uniqueness,
  `.env`, and python env; `--mainshock UTC_ID` chains the Gwangyang-style treatment.
- Submodules under `external/`: `seismoseo/necis-downloader@320d519`,
  `seismoseo/korea-cluster-relocation@5684b4a`.
- Bundled `stations/KP_station_list.csv` (404 KS + 61 KG; the same file
  `necis-downloader/download_events.py` references) — `scaffold` converts to per-cluster
  `Network,Code,Latitude,Longitude,Elevation` tables on the fly.
- `examples/changnyeong/changnyeong_catalog.csv` — 3-event 2024-09-12 test fixture.
- `tests/test_changnyeong_smoke.py` — import + submodule + KP→eq-cycle conversion checks;
  optional NECIS auth ping behind `POCKETQUAKE_TEST_NECIS=1`.
- `docs/workflow.md` — annotated walkthrough.

**Fixed**
- `build_results_nb.py` now also rewrites `RUN_SUFFIX = "_pnplus"` → `RUN_SUFFIX = ""` in the
  generated notebook — the eq-cycle template defaults to the `_pnplus` side-by-side suffix
  used by the four source clusters; PocketQuake clusters run with the default `runs/<cluster>/`.
