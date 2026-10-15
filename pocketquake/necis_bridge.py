"""Thin async wrapper around `necis.events.run_events` for the orchestrator, plus the KIGAM
Quake (KG network) event fetch used by `--kigam`.

The NECIS event ZIP packages all 404 KS stations server-side with fixed time windows, so the
`stations` and `pre`/`post` parameters are accepted-but-ignored by the downloader — we pass `[]`.
NECIS carries no KG; `download_kigam_events` adds it from KIGAM's FDSN service."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from pocketquake import NECIS_DIR


def _ensure_path():
    if NECIS_DIR not in sys.path:
        sys.path.insert(0, NECIS_DIR)


async def _adownload(catalog_csv: str, out_root: str,
                     data_types=("a", "v"), convert_sac: bool = True,
                     min_magnitude: float = 0.0,
                     start_date: str | None = None, end_date: str | None = None) -> None:
    _ensure_path()
    from necis.config import NECISConfig
    from necis.events import run_events

    config = NECISConfig.from_env()
    # Point staging at the cluster's kma_waveforms (the eq-cycle reads from here directly —
    # NECIS's per-event SAC layout matches the framework's KMA_GLOB).
    config.download_dir = Path(out_root).parent
    await run_events(
        config=config,
        catalog_path=Path(catalog_csv),
        stations=[],                        # ignored by NECIS event ZIPs (all KS included)
        data_types=tuple(data_types),
        convert_sac=convert_sac,
        min_magnitude=min_magnitude,
        start_date=start_date,
        end_date=end_date,
        out_root=Path(out_root),
    )


def download_events(catalog_csv: str, out_root: str, **kwargs) -> None:
    """Synchronous entry point — `asyncio.run(_adownload(...))`."""
    asyncio.run(_adownload(catalog_csv, out_root, **kwargs))


# The KG sensors the eq-cycle pipeline reads (cfg.sensor_priority HH > EL > HG). KIGAM also serves a
# second accelerometer (HA) that KMA_GLOB does not read, so it is not fetched.
KIGAM_GROUPS = ("HH?", "EL?", "HG?")
SOURCES_JSON = "waveform_sources.json"


def download_kigam_events(catalog_csv: str, out_root: str, data_types=("a", "v"),
                          convert_sac: bool = True) -> dict:
    """KG event waveforms from KIGAM Quake into the same per-event folders as NECIS.

    Writes `<out_root>/<UTC id>/KIGAM.{v,a}/{MSEED,SAC/<band>}/` next to NECIS's `<id>.{v,a}/`,
    cut from origin - 240 s to + 360 s (what NECIS event files cover), so the eq-cycle's
    KMA_GLOB (`*.v/SAC/HH/...`) reads KS and KG alike. Needs the KIGAM open-API key
    (KIGAM_TOKEN or ~/.config/kigam/openapi_token) and, where this machine's IP is not
    registered with KIGAM, KIGAM_SSH_TUNNEL=user@host or KIGAM_PROXY (see necis/kigam.py)."""
    _ensure_path()
    from necis import kigam
    from necis.events import load_catalog

    return kigam.run_kigam_events(kigam.KigamConfig.from_env(), load_catalog(Path(catalog_csv)),
                                  Path(out_root), data_types=tuple(data_types),
                                  convert_sac=convert_sac, groups=KIGAM_GROUPS)


def record_sources(src_root: str, *, kigam: bool, networks) -> None:
    """Record how the cluster's waveforms were fetched, so `--augment` fetches new events the
    same way (a cluster must not mix events with and without KG stations)."""
    import json
    with open(os.path.join(src_root, SOURCES_JSON), "w") as fh:
        json.dump({"kigam": bool(kigam), "networks": list(networks)}, fh, indent=1)


def kigam_enabled(src_root: str) -> bool:
    """True if the cluster was built with --kigam (clusters from before the flag: False)."""
    import json
    p = os.path.join(src_root, SOURCES_JSON)
    if not os.path.exists(p):
        return False
    with open(p) as fh:
        return bool(json.load(fh).get("kigam", False))


def auth_ping() -> bool:
    """Smoke test: log into NECIS and immediately close. Returns True on success.

    Used by `tests/test_changnyeong_smoke.py` to confirm credentials work without touching data."""
    _ensure_path()
    from necis.config import NECISConfig
    from necis.browser import NECISBrowser

    async def _ping() -> bool:
        config = NECISConfig.from_env()
        async with NECISBrowser(config) as browser:
            await browser.login()
            return True
    return asyncio.run(_ping())
