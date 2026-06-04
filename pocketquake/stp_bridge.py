"""STP waveform fetcher — PocketQuake side of the wf_source="stp_sac" path.

The eq-cycle framework already knows how to gather STP-fetched SACs (see
`pipeline.core.stations.parse_sac_name` / `pipeline.core.waveforms.gather_event`,
plus the pre-existing Gyeongju 2017 cluster module that uses this backend). What was
missing was the PocketQuake-side automation: a way to actually drive `stp` (the SNU
client at mara.snu.ac.kr:46804) from a catalog row, producing the SAC tree the
framework expects.

Two public entrypoints:
- `fetch_stp_station_table(...)` — runs STP's `sta` command, writes the eq-cycle
  station-table CSV under `<src_root>/station_table/`. Crucial for older clusters:
  the modern bundled `stations/KP_station_list.csv` doesn't contain stations that
  were operational pre-2020 but have since been retired; STP's `sta` returns the
  full historical roster.
- `download_events_via_stp(...)` — generates a batch of `dir` + `win` commands per
  the Gyeongju 2017 pattern, pipes it (with credentials prepended) to `stp`, walks
  the output tree to confirm SAC counts.

Credentials come from `STP_USER` / `STP_PASS` (read from `.env` like the NECIS ones),
or explicit kwargs.

Mirrors `pocketquake.necis_bridge` in shape so the orchestrator can dispatch on
`wf_backend` ("necis" | "stp") without per-backend special-casing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Iterable, Optional

import pandas as pd
from obspy import UTCDateTime
from obspy.geodetics.base import gps2dist_azimuth


def _stp_cmd() -> list[str]:
    """The command vector for invoking STP.
    Resolution order: $STP_CMD (whole command line) > $STP_PERL_SCRIPT (perl script
    path) > `stp-client.pl` discovered on PATH. Raises RuntimeError with an actionable
    message if none of the above resolves. STP is normally invoked as a shell alias;
    aliases don't survive non-interactive bash, so subprocess needs the explicit path."""
    cmd = os.environ.get("STP_CMD")
    if cmd:
        return cmd.split()
    script = os.environ.get("STP_PERL_SCRIPT") or shutil.which("stp-client.pl")
    if not script:
        raise RuntimeError(
            "STP client not found. Set STP_PERL_SCRIPT=/path/to/stp-client.pl in .env "
            "(or $STP_CMD for a custom command line). See docs/EXTERNAL_TOOLS.md for "
            "where to obtain the STP client.")
    return ["/usr/bin/perl", script]


def _creds(user: Optional[str], pw: Optional[str]) -> tuple[str, str]:
    user = user or os.environ.get("STP_USER")
    pw = pw or os.environ.get("STP_PASS")
    if not user or not pw:
        raise RuntimeError(
            "STP credentials missing — set STP_USER and STP_PASS in .env "
            "(or pass user=/pw= to fetch_stp_station_table / download_events_via_stp)")
    return user, pw


def _run_stp(commands: str, *, user: Optional[str] = None, pw: Optional[str] = None,
             timeout: int = 1800) -> str:
    """Pipe commands (plus quit) to `stp` over stdin, return combined stderr+stdout.

    The Perl client (`stp-client.pl`) writes banner + prompts + result tables to **stderr**
    rather than stdout, so we redirect stderr into stdout to get everything in one stream.
    Prepends `id` and `pw` (the client prompts for them interactively) and appends a
    trailing `quit` so STP doesn't sit on EOF."""
    user, pw = _creds(user, pw)
    stdin = f"{user}\n{pw}\n{commands}\nquit\n"
    res = subprocess.run(_stp_cmd(), input=stdin,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(f"stp exited {res.returncode}\n--- output ---\n{res.stdout}")
    return res.stdout


# ----------------------------------------------------------------- station table
def _parse_sta_output(stdout: str, networks: tuple[str, ...]) -> dict:
    """Parse STP's `sta` table. Format (tab-separated):
        Net  Code  Lat.  Long.  Ele.  Borehole
        KS   GAHB  36.x  127.x  0     X
    Returns {network: pandas.DataFrame[Network,Code,Latitude,Longitude,Elevation]}."""
    rows = []
    for line in stdout.splitlines():
        if not line or line.startswith("STP") or line.startswith("Type") or line.startswith("---"):
            continue
        if line.lower().startswith(("net", "id:", "pw:", "+", "|", "[connected", "networks you")):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        net = parts[0]
        if net not in networks:
            continue
        code = parts[1]
        try:
            lat = float(parts[2])
            lon = float(parts[3])
            elev = float(parts[4])
        except (ValueError, IndexError):
            continue
        rows.append((net, code, lat, lon, elev))
    # STP lists each station twice -- once with elevation in metres (e.g. ADO2 = 320) and once
    # in kilometres (ADO2 = 0.324, a unit bug in STP's own output, not two separate sensors).
    # Dedup by (Network, Code) keeping the larger Elevation -- the metres-valued row, which is
    # the correct unit for the eq-cycle station-table format. Without this dedup
    # used_stations_100km.csv has duplicate codes and per-station Sensor lookups in
    # viz.plot_3c return a Series instead of a scalar, breaking the SAC-file glob.
    out = {}
    for net in networks:
        sub = [r for r in rows if r[0] == net]
        df = pd.DataFrame(sub, columns=["Network", "Code", "Latitude", "Longitude", "Elevation"])
        # Keep the surface installation per code (highest elevation)
        df = (df.sort_values("Elevation", ascending=False)
                .drop_duplicates(subset=("Network", "Code"), keep="first")
                .reset_index(drop=True))
        out[net] = df
    return out


def fetch_stp_station_table(cfg, *, networks: tuple[str, ...] = ("KS", "KG"),
                            user: Optional[str] = None, pw: Optional[str] = None) -> dict:
    """Query STP's `sta` command, write per-network station CSVs under
    `<cfg.src_root>/station_table/<NET>_station.csv` in the eq-cycle format.

    Returns {network: n_stations}. Used by PocketQuake's scaffold for STP-mode clusters
    to populate the station table from STP's historical-inclusive roster (instead of the
    modern bundled KP_station_list.csv that may miss stations retired in the catalog epoch).
    """
    out = _run_stp("sta", user=user, pw=pw)
    parsed = _parse_sta_output(out, networks)
    sta_dir = os.path.join(cfg.src_root, "station_table")
    os.makedirs(sta_dir, exist_ok=True)
    counts = {}
    for net, df in parsed.items():
        path = os.path.join(sta_dir, f"{net}_station.csv")
        df.to_csv(path, index=False)
        counts[net] = len(df)
        print(f"[stp_bridge] wrote {len(df)} {net} stations -> {path}")
    return counts


# ------------------------------------------------------------- event waveform fetch
def _stations_within_radius(cfg, networks: tuple[str, ...]) -> pd.DataFrame:
    """Concatenate the per-network station CSVs at <src_root>/station_table/, filter to
    those within `cfg.radius_km` of `cfg.epicenter`. Returns
    DataFrame[Network,Code,Latitude,Longitude,Elevation]."""
    parts = []
    for net in networks:
        p = os.path.join(cfg.src_root, "station_table", f"{net}_station.csv")
        if os.path.exists(p):
            parts.append(pd.read_csv(p))
    if not parts:
        raise RuntimeError(f"no station CSVs under {cfg.src_root}/station_table/ — "
                           f"run fetch_stp_station_table(cfg) first")
    sta = pd.concat(parts, ignore_index=True)
    elat, elon = cfg.epicenter
    sta["dist_km"] = sta.apply(
        lambda r: gps2dist_azimuth(elat, elon, r.Latitude, r.Longitude)[0] / 1000.0,
        axis=1)
    return sta[sta.dist_km <= cfg.radius_km].reset_index(drop=True)


def _build_batch(cfg, stations: pd.DataFrame, *,
                 window_pre_s: float, window_total_s: float,
                 sensor_bands: tuple[str, ...],
                 skip_existing_station: bool = False) -> str:
    """Build the STP batch: for each event * sensor band, emit one `dir <out>` then one
    `win NET CODE BAND_ YYYY/MM/DD,HH:MM:SS.FFFFFF <total>s` per in-radius station.

    Mirrors the file 10.Earthquake_cycle_project/201704_Gyeongju_swarm/stp_waveform_download.txt
    that the user's 2017 Gyeongju notebook produced."""
    df = pd.read_csv(cfg.event_catalog_csv, encoding="utf-8-sig")
    df.columns = [c.strip().lower() for c in df.columns]
    sac_root = os.path.join(cfg.src_root, "stp_download", "SAC")
    lines = []
    for _, ev in df.iterrows():
        kst = UTCDateTime(int(ev["year"]), int(ev["month"]), int(ev["day"]),
                          int(ev["hour"]), int(ev["minute"]), int(ev["second"]))
        origin_utc = kst - cfg.kst_offset_hours * 3600
        eid = origin_utc.strftime("%Y%m%d%H%M%S")
        win_start = origin_utc - window_pre_s
        # STP wants `YYYY/MM/DD,HH:MM:SS.ffffff`
        stp_time = win_start.strftime("%Y/%m/%d,%H:%M:%S.") + f"{win_start.microsecond:06d}"
        for band in sensor_bands:
            outdir = os.path.join(sac_root, eid, band)
            lines.append(f"dir {outdir}")
            for _, s in stations.iterrows():
                if skip_existing_station and os.path.isdir(outdir):
                    # Skip stations whose SAC files for this (event, band) already exist.
                    # Used to fetch DELTA station-network rosters (e.g. add KG to an existing
                    # KS-only download) without re-paying for KS waveforms we already have.
                    # The STP `dir` line above is still emitted — harmless if no `win` follows.
                    import glob as _glob
                    if _glob.glob(os.path.join(outdir, f"*.{s.Network}.{s.Code}.*.sac")):
                        continue
                lines.append(f"win {s.Network} {s.Code} {band}_ {stp_time} {int(window_total_s)}s")
    return "\n".join(lines)


def download_events_via_stp(cfg, *, user: Optional[str] = None, pw: Optional[str] = None,
                            window_pre_s: float = 30.0, window_total_s: float = 500.0,
                            sensor_bands: tuple[str, ...] = ("HH", "HG", "EL"),
                            networks: Iterable[str] = ("KS", "KG"),
                            skip_existing_station: bool = False) -> dict:
    """Fetch per-event SAC trees via STP, return {event_id: n_sacs}.

    Writes:
      <src_root>/stp_download/stp_batch.txt   (the batch for auditability)
      <src_root>/stp_download/SAC/<event_id>/{HH,HG,EL}/<ts>.<NET>.<CODE>.<CHAN>.sac

    Skips any event_id whose output dir already contains SACs (idempotent reruns) -- if you
    need a clean fetch, `rm -r <src_root>/stp_download/SAC/<event_id>/` first.
    """
    networks = tuple(networks)
    stations = _stations_within_radius(cfg, networks)
    if stations.empty:
        raise RuntimeError(f"no stations within {cfg.radius_km} km of {cfg.epicenter} — "
                           f"check station_table/{networks[0]}_station.csv")
    print(f"[stp_bridge] {len(stations)} stations within {cfg.radius_km} km of "
          f"({cfg.epicenter[0]:.3f}, {cfg.epicenter[1]:.3f})")

    batch_dir = os.path.join(cfg.src_root, "stp_download")
    os.makedirs(batch_dir, exist_ok=True)
    batch_path = os.path.join(batch_dir, "stp_batch.txt")
    batch = _build_batch(cfg, stations,
                         window_pre_s=window_pre_s, window_total_s=window_total_s,
                         sensor_bands=tuple(sensor_bands),
                         skip_existing_station=skip_existing_station)
    with open(batch_path, "w") as f:
        f.write(batch + "\n")
    print(f"[stp_bridge] wrote batch -> {batch_path} ({len(batch.splitlines())} lines)")

    # Drive STP. The Perl client takes id+pw interactively, then reads commands from stdin;
    # the batch ends with `quit` (appended by _run_stp). Long timeout because the SNU server
    # serves ~1 station/sec on a 500 s 3-channel pull.
    print(f"[stp_bridge] running stp (this can take several minutes for a multi-event batch)")
    _run_stp(batch, user=user, pw=pw, timeout=3600)

    # Count SACs per event to confirm success
    sac_root = os.path.join(batch_dir, "SAC")
    counts = {}
    if os.path.isdir(sac_root):
        for eid in sorted(os.listdir(sac_root)):
            n = 0
            for band in sensor_bands:
                d = os.path.join(sac_root, eid, band)
                if os.path.isdir(d):
                    n += len([f for f in os.listdir(d) if f.endswith(".sac")])
            counts[eid] = n
    for eid, n in counts.items():
        print(f"[stp_bridge] {eid}: {n} SACs")
    return counts
