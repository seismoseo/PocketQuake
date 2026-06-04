# External tools

PocketQuake glues together a few seismology programs that are not pip-installable.
Install each one on your `PATH` (or set the env var noted below) before running.

| Tool | Required for | Env var override |
|---|---|---|
| `hyp1.40` (HypoInverse-2000) | absolute location (every run) | — must be on `$PATH` |
| `ph2dt` (HypoDD utilities) | relative location | — must be on `$PATH` |
| `hypoDD` | relative location | — must be on `$PATH` |
| `mseed2sac` | NECIS → SAC conversion | — must be on `$PATH` |
| `bsdtar` | NECIS multi-part ZIP extraction | — must be on `$PATH` |
| `stp-client.pl` | STP (`--source stp`/`mixed`) | `STP_PERL_SCRIPT` or `STP_CMD` |
| EQNet (PhaseNet+ weights) | `--picker phasenet_plus` | `EQNET_DIR`, optionally `EQNET_WEIGHTS` |
| SKHASH | focal mechanisms | `SKHASH_DIR` |
| Helvetica fonts | nicer plot text (optional) | `HELVETICA_DIR` |

---

## hyp1.40 (HypoInverse-2000)

Standard USGS HypoInverse, used for absolute relocation.

- Source: <https://www.usgs.gov/software/hypoinverse-earthquake-location> (Fortran, build with `gfortran`)
- Verify: `which hyp1.40` returns a path, and `hyp1.40` launches.

## ph2dt + hypoDD

HypoDD relative-relocation toolkit (Felix Waldhauser).

- Source: <https://github.com/fwaldhauser/HypoDD> or the original double-difference web page
- Build with `make` (Fortran). Put `ph2dt` and `hypoDD` on `$PATH`.

## mseed2sac

IRIS converter — turns NECIS miniSEED into per-trace SAC.

- Source: <https://github.com/iris-edu/mseed2sac>
- Build with `make`; copy `mseed2sac` to a `$PATH` dir.

## bsdtar (libarchive)

NECIS occasionally ships split-volume ZIPs that Python's `zipfile` cannot handle.
`bsdtar` (from libarchive) does.

- Ubuntu/Debian: `apt install libarchive-tools`
- macOS: `brew install libarchive` (then `ln -s` into `$PATH` or use the keg-only path)
- conda: `conda install -c conda-forge bsdtar`

## STP client (`stp-client.pl`)

Used when fetching pre-2020 waveforms from SNU's STP server (`mara.snu.ac.kr:46804`).
Contact the SGTL lab at SNU for the Perl client + an account. Then either:

```bash
# option A: put the script on $PATH and PocketQuake will find it
mv stp-client.pl ~/bin/ && chmod +x ~/bin/stp-client.pl

# option B: point at it explicitly
echo 'STP_PERL_SCRIPT=/path/to/stp-client.pl' >> .env
```

For a fully custom command line (e.g. wrapping in a particular perl install):

```bash
STP_CMD='/opt/perl/5.38/bin/perl /path/to/stp-client.pl'
```

## EQNet / PhaseNet+

Only needed when running `--picker phasenet_plus`. The default picker is SeisBench
PhaseNet (no external setup).

- Source: <https://github.com/AI4EPS/EQNet>
- Clone it somewhere convenient, then:
  ```bash
  echo 'EQNET_DIR=/path/to/EQNet' >> .env
  ```
- Weights: the bundled `model_99.pth` is under `EQNET_DIR/docs/model_phasenet_plus/`.
  Override with `EQNET_WEIGHTS=...` if you have alternate weights.

## SKHASH

HASH-style focal-mechanism solver. Used by the `focal_mechanism` pipeline stage.

- Source: <https://code.usgs.gov/esc/SKHASH>
- Clone it, then:
  ```bash
  echo 'SKHASH_DIR=/path/to/SKHASH/SKHASH' >> .env  # the dir that contains SKHASH.py
  ```

## Helvetica (optional)

Plot text uses Helvetica when available, else falls back to DejaVu Sans. If you
have Helvetica TTFs:

```bash
echo 'HELVETICA_DIR=/path/to/Helvetica' >> .env
```

Skipping this is harmless — plots still render.

---

## Verifying

After install:

```bash
which hyp1.40 ph2dt hypoDD mseed2sac bsdtar     # should all return paths
test -n "$EQNET_DIR" && ls $EQNET_DIR           # if you set it
test -n "$SKHASH_DIR" && ls $SKHASH_DIR         # if you set it
```

The chungju example exercises the picker → HypoInverse → HypoDD chain end-to-end.
