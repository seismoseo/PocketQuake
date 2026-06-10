# Changelog

Versioning follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).
The single source of truth is `pocketquake.__version__`; `pyproject.toml` reads it via setuptools dynamic.

## 1.11.1 — 2026-06-10

**Docs**
- Document the **waveform-similarity** results (1.11.0 feature) in the beamer tutorial — new
  *"Output 4 — Waveform similarity"* slide showing the full-waveform gather + the Z CC matrix
  (chronological + hierarchical) — and in the mkdocs **Workflow** page (Step 5 results notebook and
  Step 6 beamer run-summary now list the gather + CC matrices). Tutorial PDF recompiled.

## 1.11.0 — 2026-06-10

**Added**
- **Per-cluster waveform-similarity figures in the results notebook + beamer report.** New results
  section "3. Waveform similarity per dt.cc sub-cluster" (single-cluster runs are shown without a
  sub-cluster index). For each dt.cc sub-cluster (hypoDD `cid`), at the **station nearest to (and
  common to) the sub-cluster's events**:
    - a **waveform gather** of every event's **full waveform (P + S + coda)**, P-aligned at t=0 (red)
      with the **S pick as a blue bar**, ordered top→bottom = past→present (no stack), so a
      near-repeating family reads as near-identical rows;
    - a **waveform NCC matrix** over the same full window, shown both in **chronological** order
      (shares the gather's order) and in **hierarchical-clustering** order (with dendrogram) so
      repeating sub-families gather into bright blocks regardless of when they occurred.
  Bandpass **5–20 Hz** (the dt.cc band). New `pipeline.analysis.similarity.{nearest_common_station,
  cluster_events_by_cid, cluster_cc_matrix}` + `pipeline.viz.{plot_cluster_similarity_gather,
  plot_cluster_cc_matrix}`. Sub-clusters whose era has no station recording every event relax to the
  max-coverage station (warned, never aborts). Verified end-to-end on `west_jeju` (notebook 0 errors;
  slides in the summary PDF).

## 1.10.2 — 2026-06-10

**Fixed**
- **A valid run no longer crashes when a cluster has 0 focal mechanisms.** A small cluster can locate
  events but yield no mechanisms (too few first-motion polarities for SKHASH), leaving a header-only
  `mechanisms.csv`. The results notebook's `_FM_OK` guard only checks that the file *exists*, so
  `viz.map_mechanisms` ran on an empty table — the centroid `mean()` of an empty frame is `NaN`, and
  `set_xlim(NaN)` raised *“Axis limits cannot be NaN or Inf”*, which propagated out of the
  results-notebook stage and **aborted the whole run before the beamer `report` stage** (so no summary
  PDF was produced). `map_mechanisms` now returns a labelled placeholder when the mechanism table is
  empty. Verified on a 10-event / 0-mechanism cluster (`west_jeju`): the results notebook executes
  with 0 errors and the beamer summary compiles.

## 1.10.1 — 2026-06-09

**Fixed**
- **relocDD-py bootstrap no longer recomputes a cached result.** The results-notebook bootstrap
  cell re-ran all `N_BOOT` inversions on every run — overrunning the 3600 s per-cell timeout and
  failing the `report`/notebook stage — because the cache match required `backend=relocdd_py` in the
  errors-CSV header, which legacy (and Fortran-written) caches lack. The check now accepts a missing
  backend tag as a legacy match, so a valid existing result is reused (a Yeongyang run went from a
  >3600 s timeout to **1 m 18 s**).

**Changed**
- **Bootstrap parallelism fixed for many-core hosts.** Each replica subprocess is now pinned to a
  single BLAS/OpenMP thread, and the worker pool is sized from new `ClusterConfig.bootstrap_cores`
  (default **30**) instead of `num_cores` (10) — so cold-cache bootstraps use cores as a true count
  rather than oversubscribing the machine (N workers × many BLAS threads each).

## 1.10.0 — 2026-06-09

A uniform, presentation-ready **beamer PDF run summary** as a first-class workflow product,
compiled automatically alongside the results notebook at the end of every run.

**Added**
- **`report` stage** (`pipeline.reporting.make_run_summary`) compiles a per-cluster beamer deck to
  `runs/<cluster>/summary/<cluster>_summary.pdf`: a stats overview (events located /
  dt.cc-relocated, period, depth range for **both** HYPOINVERSE and dt.cc, magnitude range, median
  RMS/gap, focal-mechanism count by quality), relocated epicenters, depth sections, the
  focal-mechanism map, a best-quality **beachball** (per-station first-motion polarities + S/P
  amplitude ratios), cumulative seismicity, and a **time-lapse** of the sequence embedded both as a
  static key frame and a real `\animategraphics` animation. Compiled with **tectonic**.
- **`pipeline.cli.make_summary`** standalone CLI (`--no-animate` to skip the GIF).
- The orchestrator runs `report` after the notebook, so `./pocketquake.sh` emits the summary
  automatically. The stage is **failure-safe** — a missing tectonic / bad figure logs
  `report: SKIPPED` and never fails the scientific run.

## 1.9.1 — 2026-06-09

**Added**
- **dt.cc interpolation disk cache** (`runs/<cluster>/wf_interp_cache/`): the 100→1000 Hz Lanczos
  trace interpolation that dominates xcorr prep is cached to disk (keyed by source mtime/size +
  filter band), so re-runs skip it and recompute only new pairs — byte-identical results. Toggle
  with `cfg.xcorr_interp_cache` (default on).

## 1.9.0 — 2026-06-09

A GPU dt.cc cross-correlation backend that fills the GPU across event-pairs — the new default,
**bit-exact** to the obspy CPU baseline and **memory-safe by construction** (the previous cctorch
GPU path always OOM'd).

**Added**
- **`cctorch_gpu_batched`** xcorr backend (`--xcorr-backend` / `cfg.xcorr_backend`): a single-process
  PyTorch FFT executor with VRAM-aware batch sizing, a hard memory cap, OOM-retry-halving, and a CPU
  fallback so a run always completes. ~3× faster at cluster scale; **auto-falls-back to `obspy`**
  with no usable CUDA GPU, so CPU-only runs are unaffected.

**Changed**
- Default xcorr backend is now `cctorch_gpu_batched` (was `obspy`); the obspy CPU core is unchanged.

## 1.8.2 — 2026-06-06

**Added**
- **`--velmodel {kim1983|kim2011}`** selects the model driving relocation, focal mechanisms, and the
  results notebook (the location stage always computes both).

## 1.8.1 — 2026-06-06

**Changed**
- Robustness fixes across the run wrapper, plus the CLI-options documentation.

## 1.8.0 — 2026-06-05

A fully **Fortran-free** relocation path: HypoSVI + EikoNet for absolute location and
relocDD-py for relative relocation, opt-in alongside the unchanged default Fortran chain
(`hyp1.40` + `ph2dt` + `hypoDD`). It reproduces the Fortran workflow: on chungju the
**relative** (translation-removed) locations match `hypoDD` to **1 m horizontal / 3 m
depth**, and on identical input the relocators agree to ~1.3 m. The absolute epicentre can
differ (HypoSVI vs HypoInverse) — that centroid offset is expected and not constrained by
the data.

**Added**
- **`--python`** shortcut (= `--loc-backend hyposvi --reloc-backend relocdd_py`) and
  **`--compare`**, which runs both pipelines on the same picks and builds an executed
  `04_compare_<slug>.ipynb` (HYPOINVERSE vs HypoSVI; ff vs pp; absolute + final).
- **HypoSVI backend** (`pipeline/core/hyposvi_backend.py`): picks → HypoSVI/EikoNet →
  HYPOINVERSE-format `.sum`. SVGD particles are seeded inside each cluster's `region_bounds`.
- **relocDD-py backend** (`pipeline/core/relocdd_py_backend.py`): Fortran-free `phase.dat`
  generation from any `.sum` + picks → relocDD-py's own ph2dt → hypoDD.
- **Solver parity with Fortran**: SVD up to the `hypoDD` `MAXDATA0` limit (10000 diff-times,
  probed from the binary), then automatic LSQR with the condition-number (CND→40–80) adaptive
  damping search — the same SVD→LSQR fallback the Fortran path uses.
- **Bootstrap 95% uncertainties** (`relocdd_py_backend.bootstrap_relocation`): resample the
  differential times and re-invert with the inversion held fixed — the same headline error
  bars as the Fortran workflow (HypoDD's formal LSQR errors underestimate). The results
  notebook dispatches the bootstrap engine on the relocation backend.
- **relocDD-py hardening** (`_ensure_relocdd_patches`, idempotent, no subrepo edits): fixes
  upstream bugs that surface on real dense data — chiefly an `int8` event-pair-count overflow
  (>127 diff-times/pair wraps negative and corrupts clustering) plus divide-by-zero guards in
  the statistics routines, the SVD `resstat()` arg, an empty-`.reloc` fallback, and `ISTART=1`.
- **Pretrained EikoNet weights** for kim1983 + kim2011, shipped via the `eikonet-weights-v1`
  GitHub release; `python -m pipeline.core.fetch_eikonet` downloads them and the backend
  auto-discovers them (no `.env` editing).
- **`pipeline/core/eikonet_train.py`**: train any 1-D model, including your own via
  `--vel-csv depth_km,vp_kms,vs_kms`; `--device auto` uses the GPU.
- Config knobs: `loc_backend`, `reloc_backend`, `hyposvi_*`, `relocdd_py_dir`.

**Fixed**
- `run_dtcc` for `relocdd_py` now uses the Fortran-free path (was dispatching to a route
  that fed relocDD-py the Fortran `event.dat`, which its parser can't read).
- The `ph2dt` stage is skipped for `relocdd_py` (it required a HYPOINVERSE `.arc` HypoSVI
  doesn't produce); relocDD-py rebuilds `dt.ct` from the `.sum` in its dtct/dtcc stages.

**Notes**
- Default `hypoinverse` / `hypodd` path is byte-for-byte unchanged.
- `pocketquake.sh` fails fast if the interpreter lacks `playwright` (NECIS/mixed runs), and
  on a missing `RELOCDD_PY_DIR` / bundled EikoNet weights for the `--python` path.

## 1.4.0 — 2026-06-01

Adds a cumulative seismicity time-lapse animation in the same 4-panel fault-frame
layout as `viz.fault_sections`. Driven by the Buyeo cluster, where 14 events over
3.3 years show a bursty temporal pattern that a static snapshot can't capture.

**Added**
- **`viz.animate_seismicity(cfg, velmodel=None, *, frame_from, mech_select, fps=8,
  frames=None, out_path=None, return_html=False)`** — `matplotlib.animation.FuncAnimation`
  in the same 2×2 layout as `fault_sections` (fault-plane map / along-strike depth /
  across-strike depth / fault-plane view). Each frame is the cumulative set of events
  with origin time ≤ t, where t walks the full time-span in ~`2·n_events` equal steps
  (capped at 60 frames). The strike + dip line, beachball, and dip-line are static;
  hypocentre scatter + title clock evolve with t. Saves an animated GIF via
  `PillowWriter` (no ffmpeg/imageio needed) and optionally returns embeddable HTML.
- **New "Seismicity time-lapse" cell in the generated notebook** between section 4
  (`fault_sections`) and section 5 (`plot_3d_plane`). Every freshly-scaffolded
  cluster gets it automatically.

**Docs**
- `external/korea-cluster-relocation/CLAUDE.md` updated to document
  `viz.BOOT_DROP_VERT_KM` (v1.3.1) and the `mech_select` parameter on
  `fault_sections` / `plot_3d_plane` (v1.3.2). These were absent from the
  framework's living docs even after the features shipped.

**Verified**
- Buyeo notebook re-executed (37 cells, 0 errors). `runs/buyeo/buyeo_seismicity.gif`
  is 481 KB, 26 frames at 8 fps (~3.2 s playback); the inline HTML5 player renders
  in JupyterLab; the static overlays (strike line, beachball, dip line) match
  section 4's `fault_sections` output.

## 1.3.2 — 2026-06-01

Fixes the focal-mechanism selection used by `fault_sections` and `plot_3d_plane` so a
**small grade-A** mechanism is preferred to a **larger grade-B** one. The v1.3.1
`_fault_ref` picked the largest magnitude inside the unified A+B pool, ignoring the
A-vs-B distinction; for clusters with mixed grades the resulting beachball + section
plane could come from the less reliable solution.

Found via the Hampyeong notebook: a grade-A M1.2 (strike 68° / dip 78°) was being
ignored in favour of a grade-B M1.4 (strike 213° / dip 87°). 145° difference in
strike, completely different fault geometry.

**Added**
- **`mech_select`** kwarg on `viz._fault_ref`, `viz._mechanism_plane`,
  `viz.fault_sections`, `viz.plot_3d_plane`. Accepted values:
  - `"highest_quality"` (NEW DEFAULT): scan grades A → B → C → D; within the
    best-available grade, largest magnitude wins. Quality always beats magnitude.
  - `"largest_magnitude"`: legacy v1.3.1 behaviour. Largest magnitude inside
    `cfg.fm_quality_keep` (typically A+B as a unified pool); use this if you
    specifically want the mainshock regardless of grade.
- **`MECH_SELECT` exposed in the notebook params block** (template + Hampyeong)
  with documentation pointing to the v1.3.1 vs v1.3.2 behaviour difference.

**Changed (backward-incompatible default flip)**
- For any cluster where the largest-magnitude A+B event is grade B and a smaller
  grade-A event exists, the beachball + section header + 3-D centring will change
  to use the grade-A event. Set `MECH_SELECT = "largest_magnitude"` in the params
  block to keep the v1.3.1 behaviour exactly.

**Verified**
- Hampyeong notebook re-executed (35 cells, 0 errors). fault_sections title was
  "mechanism 213°/87° (B)" under v1.3.1, now correctly shows
  "mechanism 68°/78° (A)" — the grade-A M1.2 from 2025-01-01.
- `_fault_ref` regression check on clusters whose mainshock IS grade A (gwangyang,
  sangju, haman) → unchanged selection (mainshock is the grade-A AND the largest;
  both modes agree).

## 1.3.1 — 2026-06-01

Adds a vertical (depth) component to the bootstrap "under-constrained" drop filter — the
v1.3.0 behaviour only checked horizontal half-width, but the depth uncertainty is
systematically much larger and often the deciding factor on shallow / one-sided clusters
(haman: 80–300 m horizontal vs 500–1400 m vertical). Driven by the Taean notebook, where
one event passed the horizontal cap at 93.7 m but had ez95 = 187 m and was kept anyway.

**Added**
- **`viz.BOOT_DROP_VERT_KM`** module constant (default `0.1` km, symmetric with the
  horizontal cap). Extends `viz._boot_underconstrained` to OR in `ez95/1000 > BOOT_DROP_VERT_KM`.
  Set `viz.BOOT_DROP_VERT_KM = None` to disable vertical filtering and keep the v1.3.0
  behaviour exactly.
- **`BOOT_DROP_HORIZ_KM` / `BOOT_DROP_VERT_KM` exposed in the notebook params block** with
  in-cell wiring `viz.BOOT_DROP_HORIZ_KM = BOOT_DROP_HORIZ_KM` etc., so every cluster can
  override per-notebook without touching the framework.
- **`horiz_ok` / `vert_ok` / `nboot_ok` breakdown columns in the bootstrap diagnostic table**
  (the cell right after the cached-bootstrap summary). The table now explicitly says WHY
  each event was dropped — `dropped=True` paired with `vert_ok=False` flags a depth-only
  failure mode the v1.3.0 table couldn't surface.

**Changed (potentially breaking)**
- The 100 m default for `BOOT_DROP_VERT_KM` is strict and **will drop additional events** on
  any cluster with realistic depth uncertainty above 100 m (most non-doublet clusters).
  Already-scaffolded notebooks (haman, uiseong, sangju, chungju, …) that don't override
  the constant will see new drops on re-execute. To keep v1.3.0 behaviour, set
  `BOOT_DROP_VERT_KM = None` in the params block of the affected notebook.

**Verified**
- Taean re-executed (35 cells, 0 errors, 13 s with cached bootstrap). Event 200010 with
  horiz=93.7 m / ez95=187 m newly drops on vertical; events 200000 + 200015 still drop on
  horizontal; the well-located events (200012, 200007, 200003, 200013, 200002) all keep
  the `True/True/True/False` pattern and stay.

## 1.3.0 — 2026-05-31

Two features driven by the haman + uiseong notebooks.

**Added**
- **`viz.link_map(cfg, branch="dtcc"|"dtct", min_obs=1, …)`** and
  **`viz.link_maps(cfg, velmodel=…)`** (side-by-side dt.ct + dt.cc) — overlay HypoDD
  inter-event links on the relocation map, each line drawn between the two relocated
  epicenters and **coloured + thickened by the number of differential-time observations**
  (P + S combined) for that pair. The title reports `events / pairs / obs / unreloc-dropped`
  so pruned pairs are surfaced. Sparse pairs are kept by default; `min_obs=N` declutters
  big clusters. New cell in the generated results notebook ("HypoDD link map — inter-event
  differential-time connectivity") right after the Summary view block, so every freshly
  scaffolded cluster gets the panel automatically.
- **`FRAME_FROM` parameter exposed in the notebook params block** (was already a kwarg on
  `viz.fault_sections` / `viz.plot_3d_plane`, but not threaded through the call sites in
  the generated notebook). Accepted values: `"auto"` (default, mainshock NP1/NP2 matched
  to SVD strike when a grade-A/B mechanism exists, else SVD fallback); `"svd"` (always the
  data-driven SVD best-fit plane — for Uiseong-type cases where the relocation forms a
  clear lineation but the mechanism is small/unreliable and disagrees); `"mechanism"`
  (always the mainshock plane). Section-4 markdown updated to document the choices.

**Fixed**
- The uiseong notebook (and any already-scaffolded notebook) had `FRAME_FROM = "svd"` in
  the params but it was an unused variable because the call sites still read
  `viz.fault_sections(cfg, VELMODEL)` without `frame_from=`. The template now passes
  through; uiseong's three call sites patched in this release.

**Verified**
- Haman notebook (35 cells, 0 errors, 8.5 s re-execute with cached bootstrap; link map
  shows the 2021 doublet at 16 obs and the 2021↔2024 pair at 14 obs as the strongest
  bonds, weak inter-decade links visible).
- Uiseong notebook (10.8 s; `FRAME_FROM="svd"` rotates the 2×2 sections to strike 219° /
  dip 72° (SVD), with the grade-B M1.5 mechanism (185°/87°) shown as the inset beachball
  for comparison only; 34° rotation from the auto pick).

## 1.2.0 — 2026-05-31

Four feature requests from inspecting the post-v1.1.4 Sangju notebook:

**Added**
- **`viz.map_catalog(..., include_all=False, show_errors=True)`** and
  **`viz.depth_sections(..., include_all=False, show_errors=True)`** — when
  `include_all=True`, events that HypoDD's clustering or the bootstrap dropped get
  overlaid as **hollow squares at their HypoInverse (.sum) absolute locations** on top of
  the dt.cc-relocated set, so you can see the whole catalog in one view. `show_errors=False`
  skips the bootstrap error bars / ellipsoids — useful for a clean summary plot.
- **New "Summary view" cell in the generated notebook** (`build_results_nb.py`) using the
  above kwargs: map + depth sections with every event in the catalog, hollow squares for
  the events dt.cc dropped, no error bars. Sits right after the bootstrap-filtered headline
  plot so both are visible side-by-side.
- **Per-stage timing summary in `pipeline.core.pipeline:run_cluster`**: each stage is
  individually timed with a `time.perf_counter()` context manager; per-stage seconds are
  appended to each stage's log line, and a stage-by-stage table prints at the end of the
  run (e.g. `picking 32.1s 41.2%` + a `TOTAL` row). The timings dict is also returned in
  the result under the `_timings` key for downstream consumption.

**Fixed**
- **S/P amplitude colormap contrast** in `plot_custom_beachball`. The previous clip was
  fixed at `(-2, +2)` for `log10(S/P)`, but the actual data range for sangju / chungju is
  only **-0.3 to +0.8** (median ≈ 0). All markers compressed into the middle of the
  viridis ramp → every circle looked the same teal-green shade. Now uses a **diverging
  RdBu_r colormap centred at 0**, **auto-ranged to the 95th-percentile** of `|log10(S/P)|`
  in the actual data (with the `sp_log_clip` kwarg acting as an OUTER bound to cap
  outliers). The Sangju M3.9 beachball now visibly distinguishes stations with high
  S/P (red), low S/P (blue), and near-balance (white).

**Verified**
- Sangju + chungju + changnyeong notebooks regenerated (33 / 33 / 33 cells, 0 errors each).
- Sangju mainshock-treated `_main` notebook (34 cells, 0 errors).
- The summary view in the sangju notebook now shows all 6 events (4 relocated + 2 hollow
  squares for the 2018 + 2022 events HypoDD dropped from clustering).
- The Sangju focal-mechanism gallery (`03_beachball_gallery.png`) and individual M3.9
  detail figure regenerated to use the new diverging S/P colormap.

## 1.1.4 — 2026-05-31

Fixes a stale-derivation bug in `viz.fault_sections`'s B-B' across-strike depth section.

**Fixed**
- The dashed "Dip N°" line in panel 3 (B-B') was being drawn from the **SVD normal** of the
  relocated cloud, while the rotation `th` and the label used `used_strike`/`used_dip` from
  the chosen mechanism plane. So the drawn slope was tan(SVD_dip) — for sangju 73.8°, while
  the label said 79°. The line also anchored at the cloud centroid rather than the mainshock
  hypocenter. Both wrong when frame_from selected the mechanism plane (v1.1.2+ default).
- Now the dip line is drawn directly from `used_dip`: slope = -tan(used_dip), passing through
  (across, depth) = (0, 0) — i.e. the mainshock hypocenter (per the v1.1.2 centring contract).
  Label and drawn slope now always agree.

**Verified**
- Sangju default + `_main` notebooks regenerated (31 / 32 cells, 0 errors). The B-B' panel's
  dashed line now passes through the mainshock and dips at exactly the labelled 79°.
- Chungju notebook regenerated similarly (its mechanism dip 89.5° → near-vertical line, also
  now correctly anchored at the mainshock hypocenter).

## 1.1.3 — 2026-05-31

Fixes a wrong default in v1.1.2: the user confirmed that for Sangju the M3.9's **NP2**
(aux, E-W) is the actual fault plane, not NP1 (N-S). The dt.cc-relocated 2019 swarm
clearly elongates E-W (~360 m vs ~140 m N-S), which is the visual signal that picks the
correct plane — exactly the SVD-strike match heuristic I had in the first v1.1.2
implementation but oversimplified away to "always NP1". Restored.

**Changed**
- `pipeline/viz.py:_mechanism_plane` now disambiguates NP1 vs NP2 by **matching the
  reference mechanism's nodal-plane strike to the SVD strike of the relocated cloud**
  (circular distance mod 180°, since strike is bidirectional). The plane whose strike is
  closer to the cloud's elongation direction wins. Falls back to NP1 only when no SVD
  strike is available.
- Result for **sangju**: now picks NP2 (strike **104.2°**, dip 79.3°) — only **0.7° off**
  the cloud's SVD strike of 103.5°. NP1 was 88° off, wrong.
- Result for **chungju**: also now picks NP2 (strike 113.7°, dip 89.5°) — its cloud's
  SVD strike is 125.2°, closer to NP2 (12°) than NP1 (88°). If you've reasoned out NP1 as
  the actual rupture plane for chungju, pass explicit `strike=`/`dip=` to `fault_sections`
  / `plot_3d_plane`.

**Verified**
- Sangju default + `_main` notebooks regenerated (31 cells / 32 cells, 0 errors). Fault-frame
  sections now use NP2 of the M3.9 mainshock, anchored at the mainshock hypocenter.
- Chungju fault_sections demo figure refreshed for docs consistency.

## 1.1.2 — 2026-05-31

Three follow-ups from inspecting the v1.1.1 Sangju notebook.

**Added**
- `viz.fault_sections(..., frame_from=...)` + `viz.plot_3d_plane(..., frame_from=...)` — the
  fault-frame 2×2 figure and the 3-D plotly view now default to the **mainshock's NP1**
  (the SKHASH-reported nodal plane) as the fault plane, anchored at the mainshock
  hypocenter, instead of the SVD best-fit plane of the relocated cloud. SVD is unstable
  on tight swarms (its strike is dominated by noise when the cloud is ~50 m across);
  for clusters with a clear mainshock, the focal-mechanism plane is the right geometric
  reference. `frame_from` options: `"auto"` (default — mechanism plane when a
  high-confidence FM is available, SVD otherwise), `"svd"` (always SVD — v1.1.1 behavior),
  `"mechanism"` (force mechanism plane; raises if no FM or the mainshock isn't in the reloc).
  Explicit `strike=` / `dip=` kwargs still win when provided (use them to plot NP2 instead).

**Fixed**
- `pocketquake/stp_bridge.py:fetch_stp_station_table` deduplicates by `(Network, Code)`,
  keeping the higher-elevation row. STP's `sta` command lists each station twice — once
  with elevation in metres (e.g. `KS,ADO2,...,320`) and once in km
  (`KS,ADO2,...,0.324`, a unit bug in STP's own output, not two separate sensors). Without
  the dedup, `used_stations_100km.csv` got duplicate codes (113 in the Sangju run), which
  broke per-station Sensor lookups in `viz.plot_3c` (returned a Series instead of a
  scalar, so the SAC-file glob expanded with `"Code\nADO2  EL\n..."` and matched nothing —
  the Sangju notebook's sample-event panel rendered three empty axes labelled "(none)").
- `viz.plot_3c` now scalar-coerces the `Sensor` lookup defensively so any future
  duplicate-row station table can't recreate the empty-axes failure.

**Verified — Sangju re-run end-to-end**
- Default pipeline (deduped station table): 6 events located, 502 picks (vs 703 with
  duplicated stations — the duplicated stations contributed false-positive picks). dt.cc
  tightens the 2019 swarm (event 200000 dropped by HypoDD clustering, same as v1.1.1).
- Focal mechanisms: M3.9 grade A (strike 194.8°, dip 86.6°, rake -169.3°), plus 3 more
  grade-A in the 2019/2022 set.
- Default notebook 31 cells / 0 errors; sample-event 3-c plot now renders real waveforms.
- Gwangyang-style mainshock treatment re-applied via the v1.1.1 `--mainshock-only` path:
  the 2019 swarm shifts ~30 m south, ~500 m west, depth-shifts ~30 m shallower relative
  to the untreated v1.1.2 baseline. `_main` notebook 32 cells / 0 errors.
- Fault-frame and 3-D plots now show the M3.9 NP1 (strike 195°, dip 87°, N–S right-lateral)
  passing through the mainshock hypocenter — geologically the actual fault.

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
