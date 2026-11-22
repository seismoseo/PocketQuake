"""Public option forwarding and reproducible cluster configuration, all offline."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "external" / "korea-cluster-relocation"))

from pocketquake import orchestrate, scaffold


@pytest.fixture
def spec(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold, "EQCYCLE_DIR", str(tmp_path))
    (tmp_path / "pipeline" / "clusters").mkdir(parents=True)
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("Year,Month,Day,Hour,Minute,Second,Latitude,Longitude,Magnitude,Depth\n"
                       "2020,5,3,22,7,14,34.66,126.4,3.1,10\n")
    return dict(name="demo", region="Demo", catalog_csv=str(catalog),
                epicenter=(34.66, 126.4), region_bounds=(34, 35, 126, 127))


def test_snapshot_table_and_import_generated_config(spec, tmp_path):
    table = tmp_path / "epoch measurements.csv"
    contents = ("network,station,sensor,start,end,theta_deg\n"
                "XX,TEST,HH,2020-01-01,2020-12-31,20\n")
    table.write_text(contents)
    cs = scaffold.ClusterSpec(**spec, orientation_csv=str(table),
                              rotation_reference=(34.6611, 126.4049))
    assert cs.s_on_t
    scaffold.scaffold(cs)
    module = scaffold.write_cluster_module(cs)
    assert (Path(cs.src_root) / "station_table" / "orientation.csv").read_text() == contents
    table.unlink()  # The generated config depends on the bundled snapshot.
    namespace = {}
    exec(compile(Path(module).read_text(), module, "exec"), namespace)
    cfg = namespace["CONFIG"]
    assert cfg.xcorr["s_comps"] == ("T",)
    assert cfg.xcorr["p_comp"] == "Z"
    assert cfg.rotate_for_xcorr is True
    assert cfg.rotation_reference == (34.6611, 126.4049)
    assert cfg.orientation_missing == "error"
    assert cfg.orientation_csv.endswith("/station_table/orientation.csv")


def test_default_scaffold_keeps_existing_horizontal_mode(spec):
    cs = scaffold.ClusterSpec(**spec)
    scaffold.scaffold(cs)
    module = scaffold.write_cluster_module(cs)
    source = Path(module).read_text()
    ast.parse(source)
    assert "orientation_csv=" not in source
    ns = {}
    exec(compile(source, module, "exec"), ns)
    assert ns["CONFIG"].xcorr["s_comps"] == ("N", "E")


def test_nominal_t_explicitly_requests_rotation(spec):
    cs = scaffold.ClusterSpec(**spec, s_on_t=True)
    scaffold.scaffold(cs)
    module = scaffold.write_cluster_module(cs)
    ns = {}
    exec(compile(Path(module).read_text(), module, "exec"), ns)
    assert ns["CONFIG"].rotate_for_xcorr is True
    assert ns["CONFIG"].orientation_csv is None
    assert ns["CONFIG"].xcorr["s_comps"] == ("T",)


@pytest.mark.parametrize("kwargs", [
    {"rotation_reference": (91, 0), "s_on_t": True},
    {"rotation_reference": (float("nan"), 0), "s_on_t": True},
    {"orientation_missing": "ignore", "s_on_t": True},
    {"orientation_missing": "skip"},
    {"orientation_csv": "/missing/orientation.csv"},
])
def test_bad_settings_fail_before_scaffold(spec, kwargs):
    with pytest.raises(ValueError):
        scaffold.ClusterSpec(**spec, **kwargs)


def test_python_cli_forwards_orientation_options(monkeypatch):
    calls = []
    monkeypatch.setattr(orchestrate, "orchestrate", lambda **kw: calls.append(kw))
    orchestrate.main(["catalog.csv", "--cluster", "demo", "--epicenter", "34.6,126.4",
                      "--region-bounds", "34,35,126,127", "--orientation-csv", "epochs.csv",
                      "--orientation-missing", "skip", "--rotation-reference", "34.66,126.4"])
    assert calls[0]["orientation_csv"] == "epochs.csv"
    assert calls[0]["orientation_missing"] == "skip"
    assert calls[0]["rotation_reference"] == (34.66, 126.4)


@pytest.mark.parametrize("flag", ["--s-on-t", "--orientation-csv", "--orientation-missing",
                                  "--rotation-reference"])
def test_augment_rejects_orientation_changes(flag):
    args = {"--s-on-t": [], "--orientation-csv": ["epochs.csv"],
            "--orientation-missing": ["zero"], "--rotation-reference": ["0,0"]}
    with pytest.raises(SystemExit) as error:
        orchestrate.main(["catalog.csv", "--cluster", "demo", "--augment", flag, *args[flag]])
    assert error.value.code == 2


def test_shell_rejects_augment_change_before_credentials():
    result = subprocess.run(["bash", str(ROOT / "pocketquake.sh"), "unused.csv", "demo",
                             "--augment", "--s-on-t"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "stored orientation settings" in result.stderr
