"""Thin async wrapper around `necis.events.run_events` for the orchestrator.

The NECIS event ZIP packages all 404 KS stations server-side with fixed time windows, so the
`stations` and `pre`/`post` parameters are accepted-but-ignored by the downloader — we pass `[]`."""
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
