"""Stage a manually-downloaded NECIS bulk ZIP into a cluster's kma_waveforms/ tree.

NECIS's event-search UI supports bulk "add to cart" downloads that arrive as one ZIP of
per-event archives (`<NECIS_ID>.a.zip` / `<NECIS_ID>.v.zip`, each a flat set of miniSEED
files). This is the manual fallback when the automated per-event downloader can't serve an
event (e.g. very recent events, or rows buried deep in NECIS's paginated search results).

Each archive's miniSEED member names encode the event's UTC origin second
(`KS.ADOA.BGE.2026.227.19.58.07` -> event_id 20260815195807), so events are identified
without any NECIS-page lookup and matched against the cluster's catalog. Only catalog
events are staged (by default only those whose waveforms are missing). The miniSEED is
converted to band-sorted SAC with the NECIS downloader's own converter, producing the
exact layout the pipeline expects:

    <src_root>/kma_waveforms/<event_id>/<NECIS_ID>.a/{MSEED/, SAC/<band>/}
    <src_root>/kma_waveforms/<event_id>/<NECIS_ID>.v/{MSEED/, SAC/<band>/}

Non-event members (station-specific zips, documents) are ignored and reported.

Usage:
    python -m pocketquake.necis_zip 422892_xxx.zip --cluster 2026_Haenam [--dry-run]

Typical workflow with augmentation: stage the ZIP, then
    ./pocketquake.sh NEW_CATALOG SLUG --augment --skip-download
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from glob import glob
from pathlib import Path

from pocketquake import EQCYCLE_DIR, NECIS_DIR

_INNER_RE = re.compile(r"^(\d+)\.([avr])\.zip$")
# miniSEED member basename: NET.STA.CHA.YYYY.DDD.HH.MM.SS — origin-stamped, identical for
# every trace of one event. (SAC names carry per-station segment START times — never use
# those for identification.)
_MSEED_RE = re.compile(r"^[A-Z0-9]+\.[A-Z0-9]+\.[A-Z0-9]+"
                       r"\.(\d{4})\.(\d{3})\.(\d{2})\.(\d{2})\.(\d{2})$")


def _load_cfg(cluster: str):
    if EQCYCLE_DIR not in sys.path:
        sys.path.insert(0, EQCYCLE_DIR)
    import importlib
    return importlib.import_module(f"pipeline.clusters.{cluster}").CONFIG


def _event_id_of_names(names) -> str | None:
    """Derive the UTC event_id from the first origin-stamped miniSEED member name."""
    for name in names:
        m = _MSEED_RE.match(os.path.basename(name))
        if m:
            year, jday, hh, mm, ss = (int(g) for g in m.groups())
            t = datetime(year, 1, 1) + timedelta(days=jday - 1)
            return f"{t.year:04d}{t.month:02d}{t.day:02d}{hh:02d}{mm:02d}{ss:02d}"
    return None


def stage_zip(zip_path: str, cluster: str, data_types=("a", "v"),
              only_missing=True, convert_sac=True, dry_run=False) -> dict:
    """Stage catalog events from a NECIS bulk ZIP. Returns {event_id: [archives staged]}."""
    cfg = _load_cfg(cluster)
    from pipeline.core import waveforms as pwf
    catalog_ids = {r["event_id"] for r in pwf.load_catalog(cfg)}
    wf_root = os.path.join(cfg.src_root, "kma_waveforms")
    if NECIS_DIR not in sys.path:
        sys.path.insert(0, NECIS_DIR)
    from necis.utils import _convert_mseed_to_sac

    outer = zipfile.ZipFile(zip_path)
    inner_names, ignored = {}, []
    for name in outer.namelist():
        m = _INNER_RE.match(os.path.basename(name))
        if m and m.group(2) in data_types:
            inner_names.setdefault(m.group(1), {})[m.group(2)] = name
        elif not (m and m.group(2) == "r"):        # .r (RESP) is silently out of scope
            ignored.append(name)
    if ignored:
        print(f"[necis_zip] ignoring {len(ignored)} non-event members "
              f"(e.g. {os.path.basename(ignored[0])})")
    print(f"[necis_zip] {len(inner_names)} NECIS event archives in {os.path.basename(zip_path)}")

    staged: dict[str, list] = {}
    with tempfile.TemporaryDirectory(prefix="necis_zip_",
                                     dir=os.path.dirname(os.path.abspath(zip_path))) as tmp:
        for necis_id, types in sorted(inner_names.items()):
            # identify the event from whichever data type is present
            probe_member = types.get("a") or types.get("v")
            probe_path = outer.extract(probe_member, tmp)
            with zipfile.ZipFile(probe_path) as probe:
                event_id = _event_id_of_names(probe.namelist())
            if event_id is None:
                print(f"[necis_zip] WARN {necis_id}: no origin-stamped miniSEED member — skipped")
                continue
            if event_id not in catalog_ids:
                print(f"[necis_zip] {necis_id} -> {event_id}: not in the cluster catalog — skipped")
                continue
            ev_dir = os.path.join(wf_root, event_id)
            have = {t for t in types if glob(os.path.join(ev_dir, f"*.{t}"))}
            todo = sorted(set(types) - have) if only_missing else sorted(types)
            if not todo:
                print(f"[necis_zip] {necis_id} -> {event_id}: already staged — skipped")
                continue
            if dry_run:
                print(f"[necis_zip] would stage {necis_id} -> {event_id} ({todo})")
                staged[event_id] = [f"{necis_id}.{t}" for t in todo]
                continue
            for t in todo:
                inner_path = (probe_path if types[t] == probe_member
                              else outer.extract(types[t], tmp))
                mseed_dir = Path(ev_dir) / f"{necis_id}.{t}" / "MSEED"
                mseed_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(inner_path) as z:
                    for member in z.namelist():
                        base = os.path.basename(member)
                        if not base:               # directory entry
                            continue
                        with z.open(member) as src, open(mseed_dir / base, "wb") as dst:
                            dst.write(src.read())
                if convert_sac:
                    _convert_mseed_to_sac(mseed_dir, mseed_dir.parent / "SAC")
                staged.setdefault(event_id, []).append(f"{necis_id}.{t}")
            print(f"[necis_zip] staged {necis_id} -> {ev_dir} ({todo})")
    n_arch = sum(len(v) for v in staged.values())
    print(f"[necis_zip] done: {len(staged)} catalog events staged ({n_arch} archives)"
          + (" [dry run]" if dry_run else ""))
    return staged


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("zip", help="NECIS bulk ZIP (contains <NECIS_ID>.{a,v}.zip members)")
    ap.add_argument("--cluster", required=True, help="cluster slug (module in pipeline/clusters/)")
    ap.add_argument("--data-types", default="a,v", help="comma list of NECIS types (default a,v)")
    ap.add_argument("--all", action="store_true",
                    help="stage catalog events even if already present (default: missing only)")
    ap.add_argument("--no-convert-sac", action="store_true",
                    help="keep miniSEED only (default: convert to band-sorted SAC via mseed2sac)")
    ap.add_argument("--dry-run", action="store_true", help="print the mapping, change nothing")
    args = ap.parse_args(argv)
    stage_zip(args.zip, args.cluster,
              data_types=tuple(t for t in args.data_types.split(",") if t),
              only_missing=not args.all, convert_sac=not args.no_convert_sac,
              dry_run=args.dry_run)


if __name__ == "__main__":
    main()
