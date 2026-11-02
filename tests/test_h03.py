import struct

import numpy as np

from segyqc.header_checks import check_h03
from segyqc.models import Severity


def make_sgy(path, n=10, bin_ns=20, bin_dt=4000, trace_ns=None, trace_dt=None):
    """SEG-Y sintetis (IEEE float). trace_ns/trace_dt: list per trace, atau None."""
    out = bytearray(3600)
    out[3216:3218] = struct.pack(">h", bin_dt)
    out[3220:3222] = struct.pack(">h", bin_ns)
    out[3224:3226] = struct.pack(">h", 5)
    data = np.zeros(bin_ns, dtype=">f4").tobytes()
    for i in range(n):
        th = bytearray(240)
        th[114:116] = struct.pack(">h", trace_ns[i] if trace_ns else bin_ns)
        th[116:118] = struct.pack(">h", trace_dt[i] if trace_dt else bin_dt)
        out += th + data
    path.write_bytes(bytes(out))


def test_h03_ok(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p)
    r = check_h03(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_h03_samples_mismatch(tmp_path):
    p = tmp_path / "b.sgy"
    make_sgy(p, trace_ns=[20] * 9 + [30])
    r = check_h03(p)
    assert any(f.severity == Severity.FAIL and "1 trace" in f.message for f in r)


def test_h03_interval_mismatch(tmp_path):
    p = tmp_path / "c.sgy"
    make_sgy(p, trace_dt=[2000] * 10)
    r = check_h03(p)
    assert any(f.severity == Severity.WARN for f in r)


def test_h03_too_short(tmp_path):
    p = tmp_path / "d.sgy"
    p.write_bytes(b"abc")
    assert check_h03(p)[0].severity == Severity.FAIL