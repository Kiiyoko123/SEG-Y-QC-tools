import json
import subprocess
import sys

import pytest

import segyqc.runner as runner
from segyqc.cli import main
from segyqc.models import Finding, Severity


def dummy_file(tmp_path):
    p = tmp_path / "dummy.sgy"
    p.write_bytes(b"x")
    return p


def fake_checks(monkeypatch, *severities):
    checks = []
    for i, sev in enumerate(severities, start=1):
        cid = f"X-0{i}"
        checks.append((cid, lambda path, cid=cid, sev=sev:
                       [Finding(cid, sev, "msg")]))
    monkeypatch.setattr(runner, "CHECKS", checks)


def test_exit_0_and_report_written_when_clean(tmp_path, monkeypatch, capsys):
    fake_checks(monkeypatch, Severity.INFO, Severity.INFO)
    out = tmp_path / "out"
    code = main(["check", str(dummy_file(tmp_path)), "--out", str(out)])
    assert code == 0
    data = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert data["summary"] == {"INFO": 2, "WARN": 0, "FAIL": 0}
    assert "Summary: 2 INFO, 0 WARN, 0 FAIL" in capsys.readouterr().out


def test_exit_1_when_any_fail(tmp_path, monkeypatch):
    fake_checks(monkeypatch, Severity.INFO, Severity.FAIL)
    assert main(["check", str(dummy_file(tmp_path)),
                 "--out", str(tmp_path / "o")]) == 1


def test_exit_0_when_only_warn(tmp_path, monkeypatch):
    fake_checks(monkeypatch, Severity.WARN)
    assert main(["check", str(dummy_file(tmp_path)),
                 "--out", str(tmp_path / "o")]) == 0


def test_exit_2_missing_file(tmp_path, capsys):
    code = main(["check", str(tmp_path / "nope.sgy"), "--out", str(tmp_path / "o")])
    assert code == 2
    assert "file not found" in capsys.readouterr().err


def test_exit_2_missing_config(tmp_path, monkeypatch, capsys):
    fake_checks(monkeypatch, Severity.INFO)
    code = main(["check", str(dummy_file(tmp_path)),
                 "--config", str(tmp_path / "nope.yaml")])
    assert code == 2
    assert "file not found" in capsys.readouterr().err


def test_exit_2_invalid_config(tmp_path, monkeypatch, capsys):
    fake_checks(monkeypatch, Severity.INFO)
    cfg = tmp_path / "qc.yaml"
    cfg.write_text("bogus: 1\n", encoding="utf-8")
    code = main(["check", str(dummy_file(tmp_path)), "--config", str(cfg)])
    assert code == 2
    assert "invalid config" in capsys.readouterr().err


def test_exit_2_malformed_yaml(tmp_path, monkeypatch, capsys):
    fake_checks(monkeypatch, Severity.INFO)
    cfg = tmp_path / "qc.yaml"
    cfg.write_text("thresholds: [unclosed\n", encoding="utf-8")
    code = main(["check", str(dummy_file(tmp_path)), "--config", str(cfg)])
    assert code == 2
    assert "not valid YAML" in capsys.readouterr().err


def test_default_output_folder_is_report(tmp_path, monkeypatch):
    fake_checks(monkeypatch, Severity.INFO)
    monkeypatch.chdir(tmp_path)
    assert main(["check", str(dummy_file(tmp_path))]) == 0
    assert (tmp_path / "report" / "report.json").exists()


def test_no_command_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_module_entry_point_runs(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "segyqc", "check", str(tmp_path / "nope.sgy")],
        capture_output=True, text=True)
    assert result.returncode == 2
    assert "file not found" in result.stderr