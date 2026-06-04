# External tools

PocketQuake's default pipeline (`./pocketquake.sh CATALOG SLUG`) runs:
**PhaseNet+ picker → HypoInverse → HypoDD → SKHASH focal mechanism**.
That chain depends on a handful of programs that are not pip-installable; you
must install them on your `PATH` (or point at them with the env var noted below)
before the default pipeline can run end-to-end.

## At-a-glance: what you must install

| Tool | Required for | How to get it | Where it must end up |
|---|---|---|---|
| `hyp1.40` (HypoInverse-2000) | **default** — absolute location | USGS source build | on `$PATH` |
| `ph2dt` + `hypoDD` | **default** — relative location | Waldhauser source build | on `$PATH` |
| `mseed2sac` | **default** — NECIS → SAC | IRIS source build | on `$PATH` |
| `bsdtar` | **default** — multi-part ZIP from NECIS | `conda install -c conda-forge libarchive` (provided by `environment.yml`) | on `$PATH` |
| **EQNet + PhaseNet+ weights** | **default picker** | `git clone` (steps below) | `EQNET_DIR` env var |
| **SKHASH** | **default focal-mechanism stage** | `git clone` (steps below) | `SKHASH_DIR` env var |
| `stp-client.pl` | only `--source stp` / `mixed` | contact SGTL lab @ SNU | `STP_PERL_SCRIPT` env var or on `$PATH` |
| Helvetica fonts | only nicer plot text | optional — DejaVu Sans fallback | `HELVETICA_DIR` env var |

The default pipeline assumes you have everything except STP and Helvetica.
If you want a minimum-viable run without focal mechanisms, see [INSTALL.md](INSTALL.md) §6.

---

## Compiled binaries (Fortran / C — `make`)

### hyp1.40 (HypoInverse-2000)

- Source: <https://www.usgs.gov/software/hypoinverse-earthquake-location>
- Build:
  ```bash
  tar xf hyp1.40.tar.gz && cd hyp1.40/source
  make           # uses gfortran by default
  cp hyp1.40 ~/bin/      # somewhere on $PATH
  ```
- Verify: `hyp1.40` prints its banner.

### HypoDD utilities (`ph2dt` + `hypoDD`)

- Source: <https://www.ldeo.columbia.edu/~felixw/hypoDD.html>
  (Felix Waldhauser's HypoDD distribution; also mirrored at
  <https://github.com/fwaldhauser/HypoDD>)
- Build:
  ```bash
  tar xf HYPODD_1.3.tar.gz && cd HYPODD/src
  # edit src/hypoDD/Makefile if your gfortran is non-standard
  make
  cp HYPODD/src/hypoDD/hypoDD HYPODD/src/ph2dt/ph2dt ~/bin/
  ```
- Verify: `which hypoDD ph2dt` returns both paths.

### mseed2sac

- Source: <https://github.com/iris-edu/mseed2sac>
- Build:
  ```bash
  git clone https://github.com/iris-edu/mseed2sac.git
  cd mseed2sac && make
  cp mseed2sac ~/bin/
  ```
- Verify: `mseed2sac -V` prints version.

### bsdtar (via libarchive)

- The bundled `environment.yml` already pulls this in (`conda install -c conda-forge libarchive`).
- If you skip conda: `apt install libarchive-tools` (Ubuntu/Debian) or `brew install libarchive` (macOS).
- Verify: `bsdtar --version`.

---

## Required Python clones (research code, not on PyPI)

These two are needed by the **default pipeline**. PocketQuake imports them via
`sys.path` insertion at the call site, not via `pip install`, because both
projects are research-staging code that doesn't have stable releases.

### EQNet (PhaseNet+ — the default picker)

The default `--picker phasenet_plus` runs the EQNet implementation of PhaseNet+.
You need the EQNet repo on disk and pointed at via `EQNET_DIR`. Weights are
bundled inside the repo at `docs/model_phasenet_plus/model_99.pth`.

```bash
# 1. Clone EQNet next to PocketQuake
cd ~/works           # or any location you like
git clone https://github.com/AI4EPS/EQNet.git
cd EQNet
pip install -r requirements.txt   # PhaseNet+ extras (PyTorch is already in the pocketquake env)

# 2. Point PocketQuake at it
echo "EQNET_DIR=$PWD" >> ~/works/PocketQuake/.env

# 3. (Optional) Override weights path if you have alternate weights
# echo "EQNET_WEIGHTS=$PWD/docs/model_phasenet_plus/model_99.pth" >> .env

# 4. Verify
python -c "import os, sys; sys.path.insert(0, os.environ['EQNET_DIR']); import eqnet; print('EQNet OK')"
ls $EQNET_DIR/docs/model_phasenet_plus/model_99.pth      # weights present
```

If you would rather use a SeisBench picker (no external clone), pass
`--picker stead` on every `./pocketquake.sh` invocation. The default,
recommended path is PhaseNet+ — it emits the first-motion polarity + per-pick
amplitude that SKHASH needs.

### SKHASH (focal mechanism stage)

The `focal_mechanism` stage at the end of the default pipeline runs SKHASH.

```bash
# 1. Clone SKHASH (USGS GitLab)
cd ~/works
git clone https://code.usgs.gov/esc/SKHASH.git
cd SKHASH/SKHASH       # the inner dir that contains SKHASH.py

# 2. SKHASH's deps are already covered by environment.yml (numpy + scipy + pandas).

# 3. Point PocketQuake at the inner dir
echo "SKHASH_DIR=$PWD" >> ~/works/PocketQuake/.env

# 4. Verify
python -c "import os; assert os.path.exists(os.path.join(os.environ['SKHASH_DIR'], 'SKHASH.py')), 'SKHASH.py not at SKHASH_DIR'; print('SKHASH OK')"
```

If you want to skip the focal-mechanism stage entirely, run with
`--skip-focal-mechanism` (in development) or invoke the lower-level CLI through
`stage-from picking --through dtcc`.

---

## STP client (`stp-client.pl`)

Only required when fetching pre-2020 waveforms via `--source stp` or
`--source mixed`. The Perl client lives at SGTL (Seoul National University) and
isn't publicly hosted — contact the lab for the client + an account.

```bash
# Option A — put the script on $PATH
mv stp-client.pl ~/bin/ && chmod +x ~/bin/stp-client.pl
# Option B — point at it explicitly
echo "STP_PERL_SCRIPT=/path/to/stp-client.pl" >> .env
# Option C — a fully custom command line
echo "STP_CMD=/opt/perl/5.38/bin/perl /path/to/stp-client.pl" >> .env
```

---

## Helvetica fonts (optional)

Plot text prefers Helvetica when available, otherwise falls back to DejaVu
Sans. Skipping this is harmless — plots still render.

```bash
echo "HELVETICA_DIR=/path/to/Helvetica" >> .env
```

---

## One-shot verification

```bash
# Required externals (default pipeline)
which hyp1.40 ph2dt hypoDD mseed2sac bsdtar
test -d "$EQNET_DIR"   && echo "EQNET_DIR  OK : $EQNET_DIR"
test -d "$SKHASH_DIR"  && echo "SKHASH_DIR OK : $SKHASH_DIR"

# Optional
test -x "$STP_PERL_SCRIPT" && echo "STP        OK : $STP_PERL_SCRIPT"
test -d "$HELVETICA_DIR"   && echo "HELVETICA  OK : $HELVETICA_DIR"
```

The `chungju` smoke test in [INSTALL.md §6](INSTALL.md) exercises the full
default chain (NECIS → PhaseNet+ → HypoInverse → HypoDD → SKHASH).
