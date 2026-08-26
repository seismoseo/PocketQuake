# External tools

PocketQuake relocates two ways (see the README's *Two ways to relocate*):

- **Fortran mode** (default, `./pocketquake.sh CATALOG SLUG`): HypoInverse → HypoDD.
- **Python mode** (`--python`): HypoSVI + EikoNet → relocDD-py — **no Fortran build**.

The picker (PhaseNet+) and focal mechanisms (SKHASH) are the **same in both modes**. None of
these tools are pip-installable; the `Needed for` column tells you which mode needs what — you
only install **one** relocation mode's tools.

## At-a-glance: what you must install

| Tool | Needed for | How to get it | Where it must end up |
|---|---|---|---|
| **EQNet + PhaseNet+ weights** | **both modes** — picker | `git clone` (steps below) | `EQNET_DIR` env var |
| **SKHASH** | **both modes** — focal mechanisms | `git clone` (steps below) | `SKHASH_DIR` env var |
| `mseed2sac` | **both modes** — NECIS → SAC | IRIS source build | on `$PATH` |
| `bsdtar` | **both modes** — multi-part ZIP from NECIS | `conda install -c conda-forge libarchive` (in `environment.yml`) | on `$PATH` |
| `hyp1.40` (HypoInverse-2000) | **Fortran mode** — absolute location | USGS source build | on `$PATH` |
| `ph2dt` + `hypoDD` | **Fortran mode** — relocation | Waldhauser source build | on `$PATH` |
| **relocDD-py** | **Python mode** (`--python`) — relocation | `git clone` (steps below) | `RELOCDD_PY_DIR` env var |
| **HypoSVI + EikoNet** | **Python mode** (`--python`) — location | `git clone` ×2 + `fetch_eikonet` weights | `HYPOSVI_DIR`, `EIKONET_DIR` env vars |
| `stp-client.pl` | only `--source stp` / `mixed` | contact SGTL lab @ SNU | `STP_PERL_SCRIPT` env var or on `$PATH` |
| Helvetica fonts | only nicer plot text | optional — DejaVu Sans fallback | `HELVETICA_DIR` env var |

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
You need the EQNet repo on disk and pointed at via `EQNET_DIR`. The PhaseNet+
weights are **no longer bundled in the EQNet repo** -- download `model_99.pth`
(~18 MB) from the EQNet *PhaseNet-Plus-v1* release and place it at the path
PocketQuake expects, `docs/model_phasenet_plus/model_99.pth` inside EQNET_DIR.

```bash
# 1. Clone EQNet next to PocketQuake
cd ~/works           # or any location you like
git clone https://github.com/AI4EPS/EQNet.git
cd EQNet
pip install -r requirements.txt   # PhaseNet+ extras (PyTorch is already in the pocketquake env)

# 1b. Fetch the PhaseNet+ weights (not bundled since mid-2026)
mkdir -p docs/model_phasenet_plus
gh release download PhaseNet-Plus-v1 --repo AI4EPS/EQNet \
   --pattern model_99.pth --dir docs/model_phasenet_plus
# (or download model_99.pth from the release page in a browser)

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
cd SKHASH/src/SKHASH   # the dir that contains SKHASH.py
# (older SKHASH checkouts used SKHASH/SKHASH/ -- SKHASH_DIR must simply be
#  whichever directory holds SKHASH.py)

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

## Python relocation backends (optional — a Fortran-free pipeline)

The default chain uses the compiled Fortran tools (`hyp1.40`, `ph2dt` + `hypoDD`).
If you can't build those, PocketQuake can swap in pure-Python equivalents. They are
**opt-in** and selected per run:

```bash
# Fortran-free relative relocation (drop-in for ph2dt + hypoDD)
./pocketquake.sh catalog.csv myslug --reloc-backend relocdd_py
# Fortran-free absolute location (drop-in for hyp1.40) — needs a trained EikoNet
./pocketquake.sh catalog.csv myslug --loc-backend hyposvi --reloc-backend relocdd_py
```

The default (`--loc-backend hypoinverse --reloc-backend hypodd`) is unchanged and
remains the supported reference path; the Python chain is a different solver and
will not be bit-identical.

### relocDD-py (`--reloc-backend relocdd_py`)

A Python port of hypoDD v1.3.

```bash
# 1. Clone next to PocketQuake
git clone https://github.com/katie-biegel/relocDD-py.git
# 2. Point PocketQuake at it
echo "RELOCDD_PY_DIR=$PWD/relocDD-py" >> .env
# 3. Deps (numpy/scipy/pandas) are already covered by environment.yml.
```

PocketQuake templates relocDD-py's `run.inp` / `hypoDD.inp` for you and parses its
`hypoDD.reloc` back into the same 24-column schema the Fortran path produces, so the
results notebook is identical. **It pins `ISTART=2` (start from catalog locations)
and `ISOLV=2` (LSQR)** internally to avoid two crashes in the current relocDD-py
release (the `ISTART=1` and `ISOLV=1` code paths are broken upstream); you don't need
to configure anything.

### HypoSVI + EikoNet (`--loc-backend hyposvi`)

A Stein-variational hypocenter locator. Unlike hyp1.40 it doesn't take a layered
velocity model directly — it calls a **pre-trained EikoNet** (a neural travel-time
field) that you train once per velocity model.

```bash
# 1. Clone next to PocketQuake
git clone https://github.com/Ulvetanna/HypoSVI.git
git clone https://github.com/Ulvetanna/EikoNet.git
echo "HYPOSVI_DIR=$PWD/HypoSVI" >> .env
echo "EIKONET_DIR=$PWD/EikoNet" >> .env
# 2. Fetch the pretrained EikoNet weights (kim1983 + kim2011) — one command:
python -m pipeline.core.fetch_eikonet
#    (the backend auto-discovers them; no HYPOSVI_EIKONET_P/S needed.)
# 3. Run:  ./pocketquake.sh catalog.csv slug --python
```

> **Status (v1.8.0):** both backends are wired and validated. On chungju the Fortran
> and Python pipelines agree to ~190 m (absolute) / ~150 m horizontal (final). Use
> `--python`, or `--compare` to see them side by side. Full recipe (including training
> your own velocity model with `--vel-csv`): **docs/python_backend/README.md**.

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
