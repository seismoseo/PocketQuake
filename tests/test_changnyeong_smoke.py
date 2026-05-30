"""Smoke tests — keep them fast and non-destructive.

The slow/heavy parts (NECIS auth ping, full end-to-end run) are gated by env vars so the default
`pytest` run is offline and quick. Set `POCKETQUAKE_TEST_NECIS=1` to include the auth ping.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make PocketQuake importable when running pytest from any cwd.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest


def test_imports_clean():
    """The four PocketQuake modules import without side effects."""
    from pocketquake import orchestrate, scaffold, necis_bridge, build_results_nb  # noqa: F401
    from pocketquake import ROOT, NECIS_DIR, EQCYCLE_DIR, STATIONS_KP
    for p, label in [(NECIS_DIR, "NECIS_DIR"),
                     (EQCYCLE_DIR, "EQCYCLE_DIR"),
                     (STATIONS_KP, "STATIONS_KP")]:
        assert os.path.exists(p), f"{label} not found: {p}"


def test_submodules_initialised():
    """The submodules are checked out (not empty placeholder dirs)."""
    from pocketquake import NECIS_DIR, EQCYCLE_DIR
    assert (Path(NECIS_DIR) / "necis" / "events.py").is_file()
    assert (Path(EQCYCLE_DIR) / "pipeline" / "clusters" / "_base.py").is_file()


def test_kp_to_eqcycle_conversion():
    """The bundled KP_station_list.csv yields the expected 404 KS stations in the eq-cycle format."""
    from pocketquake.scaffold import kp_to_eqcycle_format
    from pocketquake import STATIONS_KP
    df = kp_to_eqcycle_format(STATIONS_KP, "KS")
    assert len(df) == 404, f"expected 404 KS stations, got {len(df)}"
    assert list(df.columns) == ["Network", "Code", "Latitude", "Longitude", "Elevation"]
    assert (df.Network == "KS").all()
    assert df.Latitude.between(33, 39).all()
    assert df.Longitude.between(124, 132).all()


def test_changnyeong_catalog_present():
    """The bundled changnyeong fixture matches the expected schema."""
    import pandas as pd
    cat_path = ROOT / "examples" / "changnyeong" / "changnyeong_catalog.csv"
    assert cat_path.is_file(), f"missing test fixture: {cat_path}"
    d = pd.read_csv(cat_path)
    assert {"Year", "Month", "Day", "Hour", "Minute", "Second",
            "Latitude", "Longitude", "Magnitude", "Depth"}.issubset(d.columns)
    assert len(d) >= 1


@pytest.mark.skipif(os.environ.get("POCKETQUAKE_TEST_NECIS") != "1",
                    reason="POCKETQUAKE_TEST_NECIS=1 to run; needs NECIS_USER/NECIS_PASS in env")
def test_necis_auth_ping():
    """Log into NECIS and immediately close — verifies credentials + Playwright setup."""
    from pocketquake.necis_bridge import auth_ping
    assert auth_ping() is True
