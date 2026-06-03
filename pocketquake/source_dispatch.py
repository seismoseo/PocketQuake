"""Per-event STP/NECIS source dispatch for `--source mixed` cluster runs.

Two routing modes (the orchestrator picks one based on whether `--stp-cutoff` was set):

1. **Strict date cutoff** (`split_by_cutoff`): events with UTC origin time strictly before
   the cutoff go to STP, the rest go to NECIS. No STP attempt is wasted on late events.

2. **Try-STP-first with NECIS fallback** (default, no cutoff): the orchestrator calls STP
   over the full catalog (STP silently returns nothing for events past its coverage); then
   `find_failed_events` lists the per-event subset that came back empty, and the orchestrator
   re-fetches those via NECIS. No prior knowledge of the STP coverage date is needed.

Both helpers operate on the KMA catalog CSV format: columns
`Year,Month,Day,Hour,Minute,Second,Latitude,Longitude,Depth,Magnitude` in KST.
"""
from __future__ import annotations

import os
from glob import glob

import pandas as pd
from obspy import UTCDateTime


def _utc_origin(row, kst_offset_hours: float = 9.0) -> UTCDateTime:
    """KST catalog row → UTC origin. Accepts a pandas Series or namedtuple-ish."""
    return (UTCDateTime(int(row.Year), int(row.Month), int(row.Day),
                        int(row.Hour), int(row.Minute), float(row.Second))
            - kst_offset_hours * 3600.0)


def _event_id_from_row(row, kst_offset_hours: float = 9.0) -> str:
    """The same UTC event_id (YYYYMMDDHHMMSS) the STP bridge uses for its per-event dirs."""
    return _utc_origin(row, kst_offset_hours).strftime("%Y%m%d%H%M%S")


def split_by_cutoff(catalog_csv: str, cutoff_iso: str,
                    *, kst_offset_hours: float = 9.0
                    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a catalog into (stp_eligible, necis_only) by UTC origin time.

    `cutoff_iso` is an ISO date / datetime string (e.g. "2024-10-01"). Events with
    UTC origin < cutoff land in the STP subset; everything else (origin ≥ cutoff) is
    NECIS-only. Both halves preserve the input columns and KST formatting."""
    df = pd.read_csv(catalog_csv)
    cutoff = UTCDateTime(cutoff_iso)
    is_pre = df.apply(lambda r: _utc_origin(r, kst_offset_hours) < cutoff, axis=1)
    return df[is_pre].reset_index(drop=True), df[~is_pre].reset_index(drop=True)


def find_failed_events(stp_download_sac_root: str, catalog_csv: str,
                       *, kst_offset_hours: float = 9.0) -> pd.DataFrame:
    """After STP has run, return the rows whose `<stp_download_sac_root>/<event_id>/`
    contains zero SAC files (either the dir is missing or every sensor subdir is empty).

    These are the events the orchestrator must fall back to NECIS for. Returned frame
    has the same columns as the input catalog so it can be fed straight into the NECIS
    bridge."""
    df = pd.read_csv(catalog_csv)
    failed_mask = []
    for _, r in df.iterrows():
        eid = _event_id_from_row(r, kst_offset_hours)
        sacs = glob(os.path.join(stp_download_sac_root, eid, "*", "*.sac"))
        failed_mask.append(not sacs)
    return df[pd.Series(failed_mask)].reset_index(drop=True)


def write_subset(df: pd.DataFrame, out_csv: str) -> str:
    """Write a sub-catalog to CSV, return the path. Used to materialise a temp CSV
    for the downstream fetcher (`download_events_via_stp` / `download_events`)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)) or ".", exist_ok=True)
    df.to_csv(out_csv, index=False)
    return out_csv
