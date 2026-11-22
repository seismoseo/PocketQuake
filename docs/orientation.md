# Time-dependent orientation and S on T

Use `--orientation-csv` to correct each sensor's horizontal orientation at the event's
UTC origin time and measure S differential times on the transverse component T:

```bash
./pocketquake.sh catalog.csv myswarm --orientation-csv orientation.csv --fg
```

P is correlated on Z. Without these options, S keeps the existing best-of-N/E
measurement. `--s-on-t` alone selects T using nominal N/E orientation (zero correction).
An orientation CSV implies `--s-on-t`.

This brings the time-dependent rotation used in the Haenam project into the reusable
pipeline. The option accepts user-supplied orientation measurements; it does not estimate
misorientation from the catalog or bundle Haenam's station corrections.

## Orientation table

The following values are **illustrative**, not station calibration data:

```csv
network,station,sensor,start,end,theta_deg
XX,DEMO,HH,2020-01-01,2020-05-23,120.0
XX,DEMO,HH,2020-05-24,2020-12-31,10.0
```

| Column | Meaning |
|---|---|
| `network`, `station` | Exact network and station codes (`net` and `sta` are accepted aliases); identical station codes in different networks stay separate |
| `sensor` | Two-character channel prefix, such as `HH`, `HG`, `EL`, or another sensor present in the run |
| `start`, `end` | Validity interval in UTC; date-only values cover whole days inclusively |
| `theta_deg` | Horizontal misorientation in degrees; `theta_M_apply` is also accepted |
| `location` (optional) | Location code; blank or `*` matches any location |
| `flip_n`, `flip_e`, `swap_ne` (optional) | Explicit horizontal wiring repairs; use `1`/`true`/`yes` to enable, or blank/`0`/`false`/`no` to disable (case-insensitive) |

Use explicit UTC timestamps when an instrument changes within a day. Timestamp intervals
are half-open: `start <= origin < end`. For example, rows ending and starting at
`2020-05-24T12:00:00Z` meet at noon without overlapping. A date-only end of `2020-05-23`
includes that entire UTC day. Invalid values, overlapping epochs, or ambiguous matches
stop the run rather than silently selecting a row. Event times come from the re-referenced
SAC origin, not the catalog's local-date label.

With a configured table, every horizontal sensor used for T must have a matching epoch by
default. Choose a different policy explicitly when coverage is incomplete:

| Option | Missing-epoch behavior |
|---|---|
| `--orientation-missing error` | Default: stop and identify the missing correction |
| `--orientation-missing zero` | Warn and use nominal orientation for that sensor/event |
| `--orientation-missing skip` | Omit that sensor/event's T measurement; keep its original Z/N/E |

The pipeline does not extend the first or last measured angle beyond the table's epochs.
If extending an estimate is scientifically justified, record that decision in the table's
explicit `start` and `end` dates.

Validation covers every row in the supplied table, including stations outside the run.
Review overlapping historical epochs or export a validated subset before using a master
orientation table.

## Rotation convention

After applying any recorded wiring repairs, PocketQuake uses ObsPy's N/E-to-R/T convention:

```python
effective_baz = (back_azimuth - theta_deg) % 360
R, T = rotate_ne_rt(N, E, effective_baz)
```

`back_azimuth` points from the station toward the source. By default the source is each
event's SAC coordinates. Use a common source point to keep one rotation frame across a
compact sequence, as in the Haenam application:

```bash
./pocketquake.sh catalog.csv myswarm \
    --orientation-csv orientation.csv --rotation-reference 34.6611,126.4049 --fg
```

The reference coordinates above are Haenam's shared source point; choose coordinates
appropriate to your own sequence. A fixed source point is optional, and is separate from
the station-selection centroid.

A rotation angle cannot repair an individual reversed channel or a swapped pair by itself.
Repairs run in this order: `swap_ne` first, then `flip_n`/`flip_e`, then rotation. Supply
`theta_deg` calibrated **after** those repairs. Original Z/N/E waveforms remain available;
the derived R/T records retain the origin and phase-pick timing needed by the correlation
stage. A run must select one horizontal sensor per network/station/event; ambiguous inputs
stop rather than combining different sensors.

When importing a Haenam table with `net`, `sta`, and `theta_M_apply`, carry over its
separate wiring rules into explicit `swap_ne`/`flip_n`/`flip_e` columns and their correct
epochs. The angle table alone may omit those repairs; the pipeline does not infer them
from a station name.

For global catalogs, FDSN metadata may already have rotated arbitrary instrument axes into
geographic Z/N/E. The table must describe the **residual** misorientation of those inputs;
do not apply the metadata orientation a second time. The same pipeline configuration works
with PocketQuake-global's external waveform source.

## Existing clusters and reruns

For an existing cluster, edit its `pipeline/clusters/<slug>.py` configuration in
`external/korea-cluster-relocation/`:

```python
CONFIG = config.tune(
    CONFIG,
    rotate_for_xcorr=True,
    orientation_csv="/absolute/path/to/orientation.csv",
    orientation_missing="error",
    rotation_reference=(34.6611, 126.4049),  # omit for per-event source coordinates
    xcorr={"s_comps": ("T",)},
)
```

Then run the affected stages from the pipeline checkout, with its environment active:

```bash
cd external/korea-cluster-relocation
python -m pipeline.cli.run_pipeline --cluster myswarm \
    --stage-from xcorr --through dtcc --arc-velmodel kim1983
```

Use the same velocity model as the original relocation. Rebuild uncertainty estimates and
the results notebook/report for the new relocation before interpreting them. Full workflow
runs do this through PocketQuake; editing a config and running only xcorr/dtcc does not
refresh every downstream product.

New-cluster scaffolding copies the supplied table into
`<src_root>/station_table/orientation.csv`, so the cluster records the calibration it uses.
Rotation provenance is written to `2.HypoDD/02.dt.cc/orientation/rotation.csv` and
`rotation.json`; each derived R/T SAC also records the applied angle (`user0`), effective
back azimuth (`user1`), and geographic component orientation headers.

Orientation and component settings participate in correlation-cache validation, so changing
them cannot silently resume old N/E or differently corrected T pairs. The cache state lives
in `2.HypoDD/02.dt.cc/xcorr_inputs.json`. Keep the rotation provenance with the run's `dt.cc`
products and archive the input table with the study.
`--augment` reuses the stored cluster configuration and rejects orientation-option changes;
change the config and remeasure all affected pairs before resuming incremental additions.

Older integrations that supply corrected T traces can keep `xcorr={"s_comps": ("T",)}`
without the new rotation settings: their precomputed traces are preserved. The CLI options
set `rotate_for_xcorr=True`; a configured orientation table or rotation reference also
requests generation of R/T. For nominal rotation in a hand-written cluster config, set
`rotate_for_xcorr=True` explicitly.

Enabling this option changes the S measurements and can change accepted links and the
relocation. Validate the result on the stations and epochs relevant to your catalog.
