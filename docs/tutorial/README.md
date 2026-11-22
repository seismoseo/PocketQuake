# PocketQuake Beamer tutorial

A self-contained walkthrough from a fresh clone to the executed
results notebook. Aimed at first-time users.

## Build the PDF

### Locally (tectonic)

```bash
cd docs/tutorial
tectonic pocketquake_tutorial.tex
```

Tectonic fetches the required Beamer, Metropolis, and font packages on the first build.
The canonical output is `pocketquake_tutorial.pdf`, linked from the documentation home.

### On Overleaf (no local LaTeX)

The tutorial directory is self-contained — figures are bundled under
`figures/` and `\includegraphics{figures/...}` paths are relative.

1. Zip `docs/tutorial/` (or download as a folder).
2. Overleaf → New Project → Upload Project → drop in the zip.
3. Set the main document to `pocketquake_tutorial.tex`
   (Menu → Compiler if not auto-detected).
4. Hit Recompile. The Metropolis theme + listings are part of Overleaf's
   default TeX Live, no extra config needed.

The bundled PDF in this directory (`pocketquake_tutorial.pdf`) is the
canonical output; rebuild it whenever the slides change.
