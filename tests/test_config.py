import pytest

import segyqc.runner as runner
from segyqc import run_qc
from segyqc.config import (DEFAULT_BYTE_LOCATIONS, DEFAULT_THRESHOLDS,
                           ConfigError, load_config)
from segyqc.models import Finding, Severity

README_STYLE = """\
byte_locations:
  inline: 189      # default
  crossline: 193   # default
  cdp_x: 181
  cdp_y: 185
thresholds:
  dead_trace_rms: 1.0e-8
  rms_outlier_mad: 6.0
  clip_fraction: 0.001
"""


def write(tmp_path, text):
    p = tmp_path / "qc.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def dummy_file(tmp_path):
    p = tmp_path / "dummy.sgy"
    p.write_bytes(b"x")
    return p


def test_defaults_when_no_config():
    cfg = load_config(None)
    assert cfg["byte_locations"] == DEFAULT_BYTE_LOCATIONS
    assert cfg["thresholds"] == DEFAULT_THRESHOLDS


def test_readme_style_file_equals_defaults(tmp_path):
    cfg = load_config(write(tmp_path, README_STYLE))
    assert cfg["byte_locations"] == DEFAULT_BYTE_LOCATIONS
    assert cfg["thresholds"] == DEFAULT_THRESHOLDS


def test_override_and_partial_file(tmp_path):
    cfg = load_config(write(tmp_path, "thresholds:\n  rms_outlier_mad: 4.5\n"))
    assert cfg["thresholds"]["rms_outlier_mad"] == 4.5
    assert cfg["thresholds"]["clip_fraction"] == 0.001


def test_scientific_notation_without_dot_is_accepted(tmp_path):
    cfg = load_config(write(tmp_path, "thresholds:\n  dead_trace_rms: 1e-6\n"))
    assert cfg["thresholds"]["dead_trace_rms"] == 1e-6


def test_empty_file_gives_defaults(tmp_path):
    assert load_config(write(tmp_path, ""))["thresholds"] == DEFAULT_THRESHOLDS


def test_unknown_section_rejected(tmp_path):
    with pytest.raises(ConfigError, match="Unknown config section"):
        load_config(write(tmp_path, "threshold:\n  clip_fraction: 0.01\n"))


def test_unknown_threshold_key_rejected(tmp_path):
    with pytest.raises(ConfigError, match="Unknown thresholds key"):
        load_config(write(tmp_path, "thresholds:\n  clip_fracton: 0.01\n"))


def test_invalid_values_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, "thresholds:\n  rms_outlier_mad: -2\n"))
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, "thresholds:\n  clip_fraction: 1.5\n"))
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, "byte_locations:\n  inline: 999\n"))


def test_run_qc_passes_thresholds_to_checks(tmp_path, monkeypatch):
    seen = {}

    def fake(name):
        def check(path, **kwargs):
            seen[name] = kwargs
            return [Finding(name, Severity.INFO, "ok")]
        return check

    monkeypatch.setattr(runner, "CHECKS", [
        ("T-01", fake("T-01")), ("T-03", fake("T-03")), ("T-04", fake("T-04")),
        ("H-02", fake("H-02"))])
    cfg = write(tmp_path, "thresholds:\n  dead_trace_rms: 0.5\n"
                          "  rms_outlier_mad: 3.0\n  clip_fraction: 0.02\n")
    run_qc(dummy_file(tmp_path), config=cfg)
    assert seen["T-01"] == {"dead_rms": 0.5}
    assert seen["T-03"] == {"clip_fraction": 0.02}
    assert seen["T-04"] == {"mad_threshold": 3.0, "dead_rms": 0.5}
    assert seen["H-02"] == {}


def test_custom_byte_locations_not_supported_yet(tmp_path):
    cfg = write(tmp_path, "byte_locations:\n  inline: 9\n")
    with pytest.raises(NotImplementedError):
        run_qc(dummy_file(tmp_path), config=cfg)


def test_explicit_default_byte_locations_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "CHECKS", [
        ("Z-01", lambda p: [Finding("Z-01", Severity.INFO, "ok")])])
    report = run_qc(dummy_file(tmp_path), config=write(tmp_path, README_STYLE))
    assert report.summary()["INFO"] == 1