# Changelog

Versioning follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).
The single source of truth is `pocketquake.__version__`; `pyproject.toml` reads it via setuptools dynamic.

## 1.1.1 — 2026-05-31

Surgical follow-up to v1.1.0. Adds `pocketquake.sh --mainshock-only` and applies the
Gwangyang-style mainshock treatment to the Sangju 2019 swarm.

**Added**
- `pocketquake.sh --mainshock-only` flag — skips the default pipeline pass entirely and
  runs only the mainshock treatment block (snapshot + cluster-module patch + xcorr→dtcc
  + `_main` notebook). Useful for re-running treatment on an already-completed cluster
  without redoing scaffold / download / picking / location. Requires `--mainshock` to be
  set; preflights that `runs/<cluster>/2.HypoDD/02.dt.cc/hypoDD.reloc` already exists.

**Verified**
- **Sangju** — applied the Gwangyang-style treatment for the 2019-07-21 M3.9 mainshock
  (`mainshock_event_id="20190721020418"`, narrow ±0.05 s / 1–40 Hz xcorr window on
  mainshock-paired events). Re-ran only xcorr → dtcc; picking + HypoInverse unchanged from
  v1.1.0. Result: the 2019 swarm latitude tightens 250 → 140 m, depth shifts ~400 m
  shallower (13.9 km vs 14.3 km untreated). Notebook `03_results_sangju_main.ipynb`
  built and executed cleanly (32 cells, 0 errors). The 2018 event (200000) was dropped
  from the treated reloc by HypoDD's `OBSCC=4` clustering threshold — it had zero cc
  pairs in both runs, only dt.ct connections, and the narrow-window reshuffle pushed it
  below the cluster-membership threshold. Documented in the `_main` notebook header.

## 1.1.0 — 2026-05-31

**STP waveform source for older events.** v1.0.0 only fetched via KMA NECIS, which limited
PocketQuake to events from ~2020 onwards (NECIS's event-segment archive doesn't go further
back). v1.1.0 adds **STP** (Seoul National University's SAC Transfer Protocol at
`mara.snu.ac.kr:46804`) as an alternative waveform source, opening the whole 2000s+ archive
to the same one-command flow. The user's Sangju Feb-2018 / Jul-2019 / Jul-2022 sequence
is the new headline example — its M3.9 mainshock + aftershocks (all 2019) aren't reachable
via NECIS but come through STP cleanly.

**Added**
- `pocketquake/stp_bridge.py` — STP automation: `fetch_stp_station_table` (writes the
  historical-inclusive station roster from STP's `sta` command, **505 KS + 70 KG = 575
  stations vs 465 in the modern bundled `KP_station_list.csv` — +110 stations that were
  active before 2020 but since retired**) and `download_events_via_stp` (generates the
  Gyeongju-2017-pattern batch and pipes it into `stp` with credentials).
- `pipeline/clusters/_base.py:stp_cluster()` — sibling factory of `kma_cluster()`. Identical
  defaults except `wf_source="stp_sac"`, `stp_sac_root=<src>/stp_download/SAC`, and the
  per-sensor glob the existing eq-cycle framework already consumes (Gyeongju 2017 has been
  using this layout since before PocketQuake existed).
- `pocketquake.sh` new `--source {necis|stp}` flag (default `necis`); STP preflight checks
  `STP_USER` / `STP_PASS` in `.env`.
- `pocketquake/orchestrate.py:--wf-backend` CLI flag + dispatch on the chosen backend.
- `pocketquake/scaffold.py:ClusterSpec.wf_backend` — toggles between the two cluster
  factories at scaffold time; STP path also routes the station table through STP instead
  of slicing the modern bundle.
- `examples/sangju/README.md` — the new STP worked example (6 events, 2018–2022, M3.9
  mainshock); 5 figures generated from the executed notebook.
- `.env.example` documents `STP_USER` / `STP_PASS` alongside the existing `NECIS_USER` /
  `NECIS_PASS`.

**Fixed**
- `pipeline/core/pipeline.py:run_cluster` now guards the relative-relocation chain
  (ph2dt + dtct + xcorr + dtcc) against single-event input. The previous behavior crashed
  with `SIGFPE` deep in `ph2dt.f` when only one event was located (e.g. a partial NECIS
  download); now the chain logs `"only N event(s) located -- skipping ph2dt/dtct/xcorr/dtcc"`
  and continues straight to `focal_mechanism` (which can still produce a single-event
  solution if PhaseNet+ wrote polarities).

**Verified**
- **sangju via STP** (the new headline example): 6/6 events fetched (207–273 SACs each),
  117 stations within radius (vs 57 with the modern bundled roster), 703 picks. HypoInverse
  locates all 6 events (5 grade B, 1 grade C). dt.cc tightens the 2019 swarm to ±50 m at
  depth 14.5 km. **4 grade-A focal mechanisms** — the M3.9 mainshock, two of its 2019
  aftershocks, AND the 2022 M1.4 recurrence three years later — all on the same
  near-vertical N–S right-lateral strike-slip plane (strike 194–225°, dip 84–87°, rake
  ≈ -168°). Notebook 31 cells, 0 errors.
- **gyeongju regression** — the existing 2017 STP cluster (hand-assembled `ClusterConfig`,
  pre-dates the new `stp_cluster()` factory) still loads correctly; `wf_source="stp_sac"`,
  `stp_sac_root` resolves to `201704_Gyeongju_swarm/stp_download/SAC`, `phs_weight_scheme`
  stays `"distance"` (source-cluster default unchanged).
- **chungju + changnyeong regression** — both still `wf_source="kma_archive"`,
  `phs_weight_scheme="probability"`. NECIS path unchanged.
- **Source-cluster suite** (gwangyang / jangsung / kimcheon) — all still `wf=kma_archive`,
  `scheme=distance`. No `.phs` regression on the v0.5.0 baselines.

**Notes**
- The user spotted a subtle data-loss bug during planning: the modern
  `stations/KP_station_list.csv` doesn't include stations retired between the catalog epoch
  and now, so a 2017-era event lookup using it would silently miss stations that *were*
  recording then but aren't on the modern roster. STP's `sta` command returns the
  historical-inclusive list, which we now use for `--source stp` clusters. The Sangju test
  found 117 in-radius stations vs 57 with the modern bundle alone — twice the data.

## 1.0.0 — 2026-05-31

The 1.0 milestone. Two framework features land — AI-pick-probability HypoInverse weighting
and polarity-/S-P-overlay beachballs — plus the Chungju Feb-2025 sequence becomes the
canonical PocketQuake example in the docs.

**Added**
- `pipeline/core/hypoinverse.py:_weight_prob` + `_load_picks_csv`, and a refactored
  `write_phs` that consults per-event picks CSVs to set the `.phs` weight code (column 18)
  from the PhaseNet+ pick probability instead of epicentral-distance bins. Falls back to
  distance per-pick if a probability is missing.
- `pipeline/config.py:ClusterConfig.phs_weight_scheme` (`"distance"` | `"probability"`) and
  `phs_prob_weight_bins` (defaults to `((0.90, 0), (0.70, 1), (0.50, 2), (0.30, 3), (0.00, 4))`,
  descending threshold → weight code).
- `pipeline/viz.py:plot_custom_beachball(cfg, event_id, ...)` — wraps ObsPy `beach()` and
  overlays the SKHASH per-station inversion data: red ▲ for upward first motion, blue ▼ for
  downward (sized by polarity weight), with a small offset circle per station colored by
  log₁₀(S/P) on the viridis ramp. Lower-hemisphere equal-area projection; takeoff > 90°
  rays are antipodal-flipped per HASH convention. `out_polinfo.csv` (cuspid-keyed) is
  translated via `mechanisms.csv` so callers can pass either the UTC event_id or the cuspid.
- `examples/chungju/README.md` — the canonical PocketQuake walkthrough featuring the
  4-event Feb 2025 chungju sequence: stage table, expected locations / focal-mechanism
  grades, and the per-event beachball gallery as the headline visualisation.
- README.md headline example switched to chungju (with the 4-event catalog block) plus a
  "Worked example: chungju" section with the location / RMS / FM grade summary.

**Changed**
- `pocketquake/scaffold.py` now emits `replace(CONFIG, phs_weight_scheme="probability")` in
  every auto-generated `pipeline/clusters/<name>.py`. PocketQuake-scaffolded clusters opt
  into probability weighting by default; existing source clusters (gwangyang, jangsung,
  kimcheon, gyeongju) keep `"distance"` so the v0.5.0 baseline stays byte-identical.
- `pocketquake/build_results_nb.py` — the per-event focal-mechanism gallery cell now calls
  `viz.plot_custom_beachball()` instead of embedding the SKHASH PNGs raw. The cell explains
  the new overlay legend (▲/▼ for polarity, colored circles for S/P ratio) so a notebook
  reader can interpret the per-station fit at a glance.

**Verified**
- **chungju** (the headline example): re-run end-to-end with probability weighting. 423 picks
  weighted from probability (0 distance fallbacks). 4 events at (37.142, 127.760), depths
  7.3–10.2 km, RMS 0.22–0.28 s, all grade B at HypoInverse. dt.cc tightens to ±100 m around
  (37.142, 127.759, 7.2 km). Focal mechanisms: 3 grade A/B near-vertical strike-slip
  (strike 188–204°, dip 83–87°, rake near ±180°); M1.6 multi-solution C/D (13 polarities,
  13.5 % polarity-misfit visible in the new beachball). Notebook 31 cells, 0 errors.
- **changnyeong** (mainshock-treatment example): re-run with probability weighting. 302 picks
  weighted from probability. M2.6 grade A (strike 192°, dip 88°, rake -178°), conjugate
  aftershocks grade A/B. Notebook 31 cells, 0 errors.
- **Source clusters byte-identity**: gwangyang / jangsung / kimcheon / gyeongju all confirmed
  on `phs_weight_scheme="distance"` — no `.phs` changes.

## 0.5.5 — 2026-05-30

Changnyeong mainshock-treatment notebook regenerated against the v0.5.3 CRH-fix baseline. The
pre-v0.5.3 `03_results_changnyeong_main.ipynb` was generated when HypoInverse was running with
no velocity model (the dangling-CRH bug), so its mechanisms.csv lat/lon for the M2.6 mainshock
read (35.5392, 128.4728, 10.04 km) — the same off-by-9 km artifact the default notebook also
had until 0.5.3. This release also refreshes `mechanisms.csv` itself, which had been stuck on
the pre-0.5.3 SKHASH output (the v0.5.3+ pipeline never re-ran the focal_mechanism stage for
changnyeong).

**Regenerated**
- `pipeline/runs/changnyeong/3.FocalMech/kim1983/mechanisms.csv` — now reads correct
  HypoInverse-locations (35.4626 / 128.4293 / 14.26 km for the M2.6) from the post-CRH-fix
  `.sum`. 3 events, **3 high-confidence (grade A+B)**: M2.6 grade A (strike 191.6 / dip 86.9 /
  rake -178.5 — near-vertical strike-slip), the two aftershocks grade B with the conjugate
  geometry the cluster's tight cloud predicts.
- `pipeline/notebooks/03_results_changnyeong.ipynb` (30 cells, 0 errors).
- `pipeline/notebooks/03_results_changnyeong_main.ipynb` (31 cells, 0 errors). Includes a
  prepended markdown cell explaining the treatment, and references the new
  `hypoDD.reloc.untreated` snapshot for direct before/after comparison.

**Snapshotted**
- `pipeline/runs/changnyeong/2.HypoDD/02.dt.cc/hypoDD.reloc.untreated` — dt.cc relocation
  produced with default ±0.5 s / 5–20 Hz xcorr windows across **all** pairs (xcorr_pair_overrides
  temporarily stripped from `changnyeong.py`, then restored). The treated vs untreated
  comparison shows sub-10 m horizontal differences per event for this tight 3-event cloud — the
  mainshock treatment matters less for absolute positions here than for fault-plane direction
  consistency.

## 0.5.4 — 2026-05-30

Two follow-ups after v0.5.3.

**Added**
- `pipeline/runs/chungju/3.FocalMech/kim1983/mechanisms.csv` — chungju's focal-mechanism stage
  now runs end-to-end (previously the notebook reported "no mechanisms.csv yet"). 4 events,
  3 high-confidence (grade A/B) solutions, all showing consistent strike-slip on a near-vertical
  ~N-S striking fault (strike 187–207°, dip 83–88°, rake ±180°). Event 200003 (M1.6, the smallest)
  gets two grade C/D solutions because of fewer usable picks.

**Changed**
- `pipeline/viz.py:plot_record_section` — the predicted P/S moveout lines now use the
  **depth-averaged vertical velocity through the HypoInverse velocity model** (`cfg.fm_velmodel`,
  default `kim1983`), integrated from the surface down to the event's catalog depth, rather than
  the fixed `cfg.pick_window["vp"]=5.9 / vs=3.0`. Still a single straight line per phase
  (constant velocity), now consistent with the model that produced the absolute locations.
  Examples: chungju at 7 km depth — Vp = 5.98, Vs = 3.40 (within kim1983's first layer);
  events at 20 km — Vp = 6.08 (mixed first + second layer). The picking-window scheme is
  **unchanged** — picking still reads `cfg.pick_window["vp"]/["vs"]`.

**Verified**
- chungju: notebook regenerated; record-section moveouts now labelled `kim1983 avg to 7.3 km`
  (Vp 5.98, Vs 3.40), mechanisms panel populated.
- changnyeong: notebook regenerated; moveouts at 14–16 km depth (still within kim1983 first
  layer) render at Vp 5.98 / Vs 3.40 — visually nearly identical to v0.5.3 (which used 5.9/3.0).

## 0.5.3 — 2026-05-30

The big one. Chungju never relocated end-to-end in 0.5.0–0.5.2; changnyeong's "v0.5.0 baseline"
locations (35.5432 / 128.4868 / 10.2 km) also turned out to be wrong. Both clusters were running
hyp1.40 with **no velocity model** — `pipeline/core/hypoinverse.py:_provision_crh` was creating
broken symlinks to `<Cluster>_cluster/1.HypoInv/<model>/<model>_{p,s}.crh`, a directory PocketQuake's
scaffold never populated. hyp1.40 printed `*** ERROR - CRUST FILE DOES NOT EXIST` and silently fell
through with a built-in default. Changnyeong's well-distributed network made the locations
*look* plausible (off by 9 km from catalog 35.46 / 128.43 / 14–16 km, not enough to raise alarms);
chungju's tighter geometry exposed it — AGSA at 6.9 km from epicenter became the "closest station
to first P arrival" hyp1.40 falls back to for trial location, the (lat, lon) Jacobian collapsed
because the velocity model wasn't constraining anything, and DLAT = DLON = 0 in every iteration
([chungju/1.HypoInv/kim1983/Chungju.prt:56-78](external/korea-cluster-relocation/pipeline/runs/chungju/1.HypoInv/kim1983/Chungju.prt)).

**Fixed**
- `pipeline/core/hypoinverse.py:_provision_crh` now checks whether the source CRH file actually
  exists before symlinking, and falls back to writing the CRH from the in-config `p_rows` /
  `s_rows` when it doesn't. Local working-tree edit in the eq-cycle submodule.
- `pipeline/viz.py:plot_record_section` auto-fits `ylim` to the actual data range (was fixed to
  `(0, max_h * 1.05)` so deep / sparse-near-field clusters showed huge empty top and bottom);
  per-trace `dscale` now sizes to the median inter-station gap instead of `0.04 * max_h` so
  adjacent traces don't overlap on clusters where the gap is ~1–3 km but the max distance is ~100 km.

**Verified**
- **chungju** (the canary, finally end-to-end): all 4 events relocate at HypoInverse to
  (37.1427, 127.7596–127.7602), depths 6.85–7.31 km, RMS 0.16–0.20 s, ERH 0.1–0.2 km, all
  grade B — matches catalog (37.14, 127.76, depths 6–9 km) within ±300 m horizontally. ph2dt
  produces 479 `dt.ct` entries (was 0 before). dt.cc converges to a tight cluster at
  (37.142, 127.759, ~7.2 km depth) with ±100 m spread. Notebook 30 cells, 0 errors.
- **changnyeong**: re-located on the now-correct kim1983 model. New .sum: 35.4626 / 128.4293 /
  14.26 km (event 1), matching the user's catalog (35.46 / 128.43 / 14–16 km) within ±0.001°.
  Previous v0.5.0–0.5.2 .sum (35.5432 / 128.4868 / 10.2 km) is **superseded** — it was the
  no-velocity-model default. dt.cc reloc + focal mechanism re-computed on the corrected
  baseline. ~302 P picks across 3 events with the `--stage-from waveforms` re-run.
- **No regression on the source clusters** (gwangyang / jangsung / kimcheon / gyeongju): those
  source-roots have their own hand-curated `1.HypoInv/<model>/*.crh` files, so
  `_provision_crh` still symlinks the same way it did before — byte-identical inputs and
  outputs.

**Notes**
- The `--stage-from picking` partial-rerun gotcha (picking on already-rereferenced SACs drops
  close-station P arrivals because SAC `nz*` headers were shifted by an earlier rereference)
  remains a pipeline subtlety — use `--stage-from waveforms` for a full re-pick.
- Documentation: HypoInverse output paths now listed explicitly in `docs/workflow.md` and the
  README's "What you get" section so users know where to look when a relocation looks wrong.

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
