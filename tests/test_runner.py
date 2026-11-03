import json
import struct

import numpy as np
import pytest

import segyqc.runner as runner
from segyqc import run_qc
from segyqc.models import Finding, Severity

CARDS = "".join(f"C{i:2d} SYNTHETIC TEST HEADER".ljust(80) for i in range(1, 41))


def make_clean_sgy(path, n_il=4, n_xl=5, ns=100):
    rng = np.random.default_rng(0)
    out = bytearray(3600)
    out[0:3200] = CARDS.encode("cp037")
    out[3216:3218] = struct.pack(">h", 4000)
    out[3220:3222] = struct.pack(">h", ns)
    out[3224:3226] = struct.pack(">h", 5)
    for il in range(100, 100 + n_il):
        for xl in range(1, 1 + n_xl):
            th = bytearray(240)
            th[70:72] = struct.pack(">h", -100)
            th[114:116] = struct.pack(">h", ns)
            th[116:118] = struct.pack(">h", 4000)
            x = 500000 + 20 * il + 5 * xl
            y = 4000000 + 3 * il + 25 * xl
            th[180:184] = struct.pack(">i", x * 100)
            th[184:188] = struct.pack(">i", y * 100)
            th[188:192] = struct.pack(">i", il)
            th[192:196] = struct.pack(">i", xl)
            out += th + rng.standard_normal(ns).astype(">f4").tobytes()
    path.write_bytes(bytes(out))


def dummy_file(tmp_path):
    p = tmp_path / "dummy.sgy"
    p.write_bytes(b"x")
    return p


def test_summary_counts_and_normalizes_single_finding(tmp_path, monkeypatch):
    def single(path):
        return Finding("A-01", Severity.INFO, "ok")

    def several(path):
        return [Finding("A-02", Severity.WARN, "w"),
                Finding("A-02", Severity.FAIL, "f")]

    monkeypatch.setattr(runner, "CHECKS", [("A-01", single), ("A-02", several)])
    report = run_qc(dummy_file(tmp_path))
    assert report.summary() == {"INFO": 1, "WARN": 1, "FAIL": 1}
    assert report.has_fail


def test_crashing_check_does_not_stop_others(tmp_path, monkeypatch):
    def boom(path):
        raise ValueError("kaboom")

    def fine(path):
        return [Finding("B-02", Severity.INFO, "ok")]

    monkeypatch.setattr(runner, "CHECKS", [("B-01", boom), ("B-02", fine)])
    report = run_qc(dummy_file(tmp_path))
    assert report.summary() == {"INFO": 1, "WARN": 0, "FAIL": 1}
    assert "kaboom" in report.findings[0].message


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_qc(tmp_path / "nope.sgy")


def test_config_not_supported_yet(tmp_path):
    with pytest.raises(NotImplementedError):
        run_qc(dummy_file(tmp_path), config="qc.yaml")


def test_to_json_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "CHECKS", [
        ("C-01", lambda p: [Finding("C-01", Severity.WARN, "perhatian")])])
    report = run_qc(dummy_file(tmp_path))
    out = report.to_json(tmp_path / "report" / "report.json")
    data = json.loads(open(out, encoding="utf-8").read())
    assert data["summary"] == {"INFO": 0, "WARN": 1, "FAIL": 0}
    assert data["findings"][0] == {
        "check_id": "C-01", "severity": "WARN", "message": "perhatian"}


def test_has_fail_false_without_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "CHECKS", [
        ("D-01", lambda p: [Finding("D-01", Severity.WARN, "w")])])
    assert not run_qc(dummy_file(tmp_path)).has_fail


def test_end_to_end_clean_file(tmp_path):
    p = tmp_path / "clean.sgy"
    make_clean_sgy(p)
    report = run_qc(p)
    assert report.summary() == {"INFO": 12, "WARN": 0, "FAIL": 0}