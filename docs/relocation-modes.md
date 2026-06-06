# Two relocation modes

PocketQuake relocates two ways. They take the **same picks**, write the **same files**, and build the **same summary notebook** — and agree on *relative* locations to ~1 m. Picking (PhaseNet+) and focal mechanisms (SKHASH) are identical either way.

| | **Fortran mode** *(default)* | **Python mode** (`--python`) |
|---|---|---|
| Absolute location | HYPOINVERSE (`hyp1.40`) | HypoSVI + EikoNet |
| Relocation | `ph2dt` + `hypoDD` | relocDD-py |
| Setup | 3 compiled Fortran binaries | 3 Python clones — **no compiler** |
| Good when… | you have the binaries / want the long-trusted reference | no Fortran toolchain (or you want GPU location) |

```bash
./pocketquake.sh catalog.csv myrun              # Fortran  (default)
./pocketquake.sh catalog.csv myrun --python     # pure Python
./pocketquake.sh catalog.csv myrun --compare    # run BOTH → side-by-side comparison notebook
```

!!! info "Absolute vs relative"
    The absolute epicentre can differ between modes (HypoSVI vs HYPOINVERSE) — that centroid offset is normal and **not** what double-difference relocation constrains. The *relative* structure is what matches.

## Fortran mode (default)

Needs `hyp1.40`, `ph2dt`, `hypoDD` on `$PATH` — see [External tools](EXTERNAL_TOOLS.md). The long-trusted reference path.

## Python mode (`--python`)

A Fortran-free chain — clone three Python tools (no compiler) and set them in `.env`:

```bash
git clone https://github.com/katie-biegel/relocDD-py.git && echo "RELOCDD_PY_DIR=$PWD/relocDD-py" >> .env
git clone https://github.com/Ulvetanna/HypoSVI.git        && echo "HYPOSVI_DIR=$PWD/HypoSVI"       >> .env
git clone https://github.com/Ulvetanna/EikoNet.git        && echo "EIKONET_DIR=$PWD/EikoNet"       >> .env
python -m pipeline.core.fetch_eikonet            # pretrained kim1983 + kim2011 weights
```

It reproduces the Fortran workflow — same SVD→LSQR adaptive-damping solver, same bootstrap 95% error bars — and matches `hypoDD` to ~1 m relative. Full recipe + internals: [Python backend](python-backend.md).

## `--compare`

Runs the Fortran pipeline, then re-runs the Python backend on the **same picks**, and builds an executed `04_compare_<slug>.ipynb` (HYPOINVERSE vs HypoSVI; ff vs pp; absolute + relative sections).
