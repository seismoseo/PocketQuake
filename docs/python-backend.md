# Python backend (`--python`)

Locate and relocate **without a Fortran toolchain**. The default chain (`hyp1.40` + `ph2dt` + `hypoDD`) stays the supported reference; this is an opt-in, pure-Python alternative:

- **HypoSVI + EikoNet** — absolute location by Stein-variational inference over a neural-network travel-time field.
- **relocDD-py** — Katherine Biegel's Python port of `hypoDD` for the double-difference relocation.

```bash
./pocketquake.sh catalog.csv myslug --python
```

## Setup

```bash
# clone the three tools (not on PyPI) and point .env at them
git clone https://github.com/katie-biegel/relocDD-py.git && echo "RELOCDD_PY_DIR=$PWD/relocDD-py" >> .env
git clone https://github.com/Ulvetanna/HypoSVI.git        && echo "HYPOSVI_DIR=$PWD/HypoSVI"       >> .env
git clone https://github.com/Ulvetanna/EikoNet.git        && echo "EIKONET_DIR=$PWD/EikoNet"       >> .env

# pretrained EikoNet weights (kim1983 + kim2011, P & S)
python -m pipeline.core.fetch_eikonet
```

`environment.yml` already includes the extra deps these clones import (`seaborn`, `scikit-learn`, `scikit-fmm`, plus PyTorch + pyproj). Set them up once and `--python` runs anywhere.

## Faithful to the Fortran chain

| | Fortran | Python backend |
|---|---|---|
| absolute location | `hyp1.40` | **HypoSVI** + EikoNet |
| relocation | `hypoDD` | **relocDD-py** |
| solver | SVD, auto→LSQR + adaptive damping above MAXDATA0 | **same** crossover + condition-number (CND→40–80) damping search |
| 95% uncertainty | bootstrap (resample dt, re-invert) | **same** procedure + the same `bootstrap_errors.csv` / `bootstrap_samples.npz` |

On chungju the **relative** (translation-removed) locations match `hypoDD` to **1 m horizontal / 3 m depth**; on *identical* inputs the relocators agree to ~1.3 m. The absolute centroid can differ (HypoSVI vs HYPOINVERSE) — expected, and not what double-difference constrains.

## GPU (recommended)

HypoSVI location runs on the GPU **automatically** — `hyposvi_device` defaults to `auto`, which smoke-tests a real CUDA op and uses the GPU when it works, falling back to CPU otherwise (so a GPU newer than the installed PyTorch — e.g. Blackwell sm_120 on an older wheel — cleanly uses CPU instead of crashing). The GPU path is a pure acceleration: locations match the CPU run to within SVGD's own run-to-run scatter (~6 m in depth on chungju).

It is **much** faster. On an RTX PRO 6000 Blackwell the per-event SVGD locate is **~3.5 s vs ~37 s on CPU (~10–20×)** — so a 15,000-event catalog drops from **~1–2 weeks to ~15 hours**. For anything beyond a small cluster, GPU is the difference between practical and not.

To enable it, install a CUDA PyTorch wheel matching your card from [pytorch.org](https://pytorch.org/get-started/locally/) (e.g. `cu128` for Blackwell sm_120):

```bash
pip install --upgrade --index-url https://download.pytorch.org/whl/cu128 torch
# verify your card is supported (must print True + your GPU name):
python -c "import torch; print('sm_120' in torch.cuda.get_arch_list(), torch.cuda.get_device_name(0))"
```

No GPU? Nothing to do — the pipeline runs on CPU automatically.

## Train your own velocity model

```bash
python -m pipeline.core.eikonet_train --vel-csv depth_km,vp_kms,vs_kms ... --device auto
```

## More

Full recipe, per-stage detail, and the developer "under-the-hood" notes (EikoNet `+units=km`, the relocDD-py hardening, the SVGD init box) live in the eq-cycle repo:
[`docs/python_backend/README.md`](https://github.com/seismoseo/korea-cluster-relocation/blob/main/docs/python_backend/README.md).
