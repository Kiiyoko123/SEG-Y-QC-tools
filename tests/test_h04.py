import struct

import numpy as np

from segyqc.header_checks import check_h04
from segyqc.models import Severity


def make_sgy(path, n=10, bin_ns=20, bin_dt=4000, trace_ns=None):
    out = bytearray(3600)
    out[3216:3218] = struct.pack(">h", bin_dt)
    out[3220:3222] = struct.pack(">h", bin_ns)
    out[3224:3226] = struct.pack(">h", 5)
    data = np.zeros(bin_ns, dtype=">f4").tobytes()
    for i in range(n):
        th = bytearray(240)
        th[114:116] = struct.pack(">h", trace_ns[i] if trace_ns else bin_ns)
        th[116:118] = struct.pack(">h", bin_dt)
        out += th + data
    path.write_bytes(bytes(out))


def test_h04_constant(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p)
    assert check_h04(p)[0].severity == Severity.INFO


def test_h04_varies(tmp_path):
    p = tmp_path / "b.sgy"
    make_sgy(p, trace_ns=[20] * 7 + [25] * 3)
    r = check_h04(p)
    assert r[0].severity == Severity.FAIL and "not constant" in r[0].message


def test_h04_too_short(tmp_path):
    p = tmp_path / "c.sgy"
    p.write_bytes(b"abc")
    assert check_h04(p)[0].severity == Severity.FAIL