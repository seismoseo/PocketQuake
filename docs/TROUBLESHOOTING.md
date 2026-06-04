# PocketQuake troubleshooting

Common errors on a fresh clone, mapped to fixes. If you hit something not listed
here, file an issue at <https://github.com/seismoseo/PocketQuake/issues>.

## `python interpreter not found (PY='...')`

The wrapper couldn't find Python. Either put `python3` on your `PATH`, or:

```bash
echo 'export POCKETQUAKE_PYTHON=/path/to/python' >> ~/.bashrc
```

## `STP client not found. Set STP_PERL_SCRIPT=...`

You're using `--source stp` or `--source mixed` and the Perl client isn't reachable.
Either put `stp-client.pl` on `$PATH`, or set `STP_PERL_SCRIPT` in `.env`. See
[EXTERNAL_TOOLS.md](EXTERNAL_TOOLS.md).

## `STP credentials missing — set STP_USER and STP_PASS in .env`

Same workflow as NECIS — you need SNU/SGTL credentials. Email the SGTL lab.

## `NECIS_USER is empty` / Playwright login failure

- Confirm `.env` exists at the repo root.
- Confirm `NECIS_USER` and `NECIS_PASS` are set without quotes.
- Confirm the account is approved at <https://necis.kma.go.kr> (approval takes
  a few days).

## `Executable doesn't exist at .../chromium`

Run once:

```bash
playwright install chromium
```

## `bsdtar not found on PATH`

NECIS occasionally splits ZIPs into volumes that Python's `zipfile` cannot
handle. Install libarchive:

- Ubuntu/Debian: `apt install libarchive-tools`
- macOS: `brew install libarchive`
- conda: `conda install -c conda-forge bsdtar`

## `mseed2sac not found on PATH`

Build from <https://github.com/iris-edu/mseed2sac> and put the binary on `$PATH`.

## `hyp1.40` / `hypoDD` / `ph2dt`: command not found

Build from source (Fortran). See [EXTERNAL_TOOLS.md](EXTERNAL_TOOLS.md).

## `EQNet (PhaseNet+) requires EQNET_DIR`

PhaseNet+ is the **default** picker. Two fixes:

- **Install EQNet** (recommended — required for the default focal-mechanism stage):
  ```bash
  git clone https://github.com/AI4EPS/EQNet.git ~/works/EQNet
  echo "EQNET_DIR=$HOME/works/EQNet" >> .env
  ```
  Weights ship inside the clone at `docs/model_phasenet_plus/model_99.pth`.
- **Or fall back to SeisBench**: pass `--picker stead` on every run (no extra
  install; loses polarity / amplitude so SKHASH won't work).

## `Focal-mechanism stage requires SKHASH_DIR`

The default pipeline runs SKHASH at the end. Two fixes:

- **Install SKHASH**:
  ```bash
  git clone https://code.usgs.gov/esc/SKHASH.git ~/works/SKHASH
  echo "SKHASH_DIR=$HOME/works/SKHASH/SKHASH" >> .env
  ```
- **Or skip the stage**: end the pipeline at `dtcc` instead of
  `focal_mechanism`. Pass through the lower-level CLI (`pipeline.cli.run_pipeline`)
  with `--through dtcc`. PocketQuake wrapper exposes this via
  `--skip-pipeline-stage focal_mechanism` (in development).

## `No module named 'pipeline'`

The eq-cycle submodule isn't on `PYTHONPATH`. PocketQuake's wrapper handles this
automatically — if you're invoking pipeline modules directly, run from the repo
root or `export PYTHONPATH=$(pwd)/external/korea-cluster-relocation`.

## Submodule empty / missing files under `external/`

You cloned without `--recurse-submodules`. Fix:

```bash
git submodule update --init --recursive
```

## Pipeline finishes but `03_results_<slug>.ipynb` is empty / errors out

Re-execute the notebook directly to see the error:

```bash
cd external/korea-cluster-relocation/pipeline/notebooks
jupyter nbconvert --to notebook --execute --inplace 03_results_<slug>.ipynb
```
