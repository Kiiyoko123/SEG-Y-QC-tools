import os

from . import header_checks as hc
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


def _as_list(result):
    """check_h01 mengembalikan satu Finding, check lain mengembalikan daftar."""
    if isinstance(result, Finding):
        return [result]
    return list(result)


def run_qc(path, config=None):
    """Jalankan semua check pada satu file SEG-Y dan kembalikan Report."""
    if config is not None:
        raise NotImplementedError("Config files (qc.yaml) are not supported yet.")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    findings = []
    for check_id, fn in CHECKS:
        try:
            findings.extend(_as_list(fn(path)))
        except Exception as exc:  # satu check rusak tidak boleh mematikan semuanya
            findings.append(Finding(
                check_id, Severity.FAIL,
                f"Check crashed unexpectedly: {type(exc).__name__}: {exc}"))
    return Report(path, findings)