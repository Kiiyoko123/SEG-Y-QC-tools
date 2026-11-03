import os

from . import header_checks as hc
from .config import DEFAULT_BYTE_LOCATIONS, load_config
from .models import Finding, Severity
from .report import Report

CHECKS = [
    ("H-01", hc.check_h01),
    ("H-02", hc.check_h02),
    ("H-03", hc.check_h03),
    ("H-04", hc.check_h04),
    ("G-01", hc.check_g01),
    ("G-02", hc.check_g02),
    ("G-03", hc.check_g03),
    ("G-04", hc.check_g04),
    ("T-01", hc.check_t01),
    ("T-02", hc.check_t02),
    ("T-03", hc.check_t03),
    ("T-04", hc.check_t04),
]

# check -> {nama threshold di qc.yaml: nama parameter di fungsi check}
THRESHOLD_ARGS = {
    "T-01": {"dead_trace_rms": "dead_rms"},
    "T-03": {"clip_fraction": "clip_fraction"},
    "T-04": {"rms_outlier_mad": "mad_threshold", "dead_trace_rms": "dead_rms"},
}


def _as_list(result):
    """check_h01 mengembalikan satu Finding, check lain mengembalikan daftar."""
    if isinstance(result, Finding):
        return [result]
    return list(result)


def run_qc(path, config=None):
    """Jalankan semua check pada satu file SEG-Y dan kembalikan Report.
    config: path ke qc.yaml (opsional)."""
    cfg = load_config(config)
    if cfg["byte_locations"] != DEFAULT_BYTE_LOCATIONS:
        raise NotImplementedError(
            "Custom byte_locations are not supported yet; only the defaults "
            f"{DEFAULT_BYTE_LOCATIONS} work.")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    thresholds = cfg["thresholds"]
    findings = []
    for check_id, fn in CHECKS:
        kwargs = {param: thresholds[key]
                  for key, param in THRESHOLD_ARGS.get(check_id, {}).items()}
        try:
            findings.extend(_as_list(fn(path, **kwargs)))
        except Exception as exc:  # satu check rusak tidak boleh mematikan semuanya
            findings.append(Finding(
                check_id, Severity.FAIL,
                f"Check crashed unexpectedly: {type(exc).__name__}: {exc}"))
    return Report(path, findings)