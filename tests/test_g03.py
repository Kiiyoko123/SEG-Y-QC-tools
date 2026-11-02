import struct

import numpy as np

from segyqc.header_checks import check_g03
from segyqc.models import Severity


def make_sgy(path, scalars, ns=4):
    """SEG-Y sintetis (IEEE float). scalars = coordinate scalar per trace."""
    out = bytearray(3600)
    out[3216:3218] = struct.pack(">h", 4000)
    out[3220:3222] = struct.pack(">h", ns)
    out[3224:3226] = struct.pack(">h", 5)
    for s in scalars:
        th = bytearray(240)
        th[70:72] = struct.pack(">h", s)
        th[114:116] = struct.pack(">h", ns)
        th[116:118] = struct.pack(">h", 4000)
        out += th + np.zeros(ns, dtype=">f4").tobytes()
    path.write_bytes(bytes(out))


def test_g03_constant_ok(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p, [100] * 10)
    r = check_g03(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_g03_negative_ok(tmp_path):
    p = tmp_path / "b.sgy"
    make_sgy(p, [-100] * 10)
    r = check_g03(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_g03_zero_warns(tmp_path):
    p = tmp_path / "c.sgy"
    make_sgy(p, [0] * 10)
    r = check_g03(p)
    assert len(r) == 1 and r[0].severity == Severity.WARN


def test_g03_inconsistent(tmp_path):
    p = tmp_path / "d.sgy"
    make_sgy(p, [-100] * 9 + [10])
    r = check_g03(p)
    assert any(f.severity == Severity.FAIL and "not constant" in f.message for f in r)


def test_g03_invalid_value(tmp_path):
    p = tmp_path / "e.sgy"
    make_sgy(p, [7] * 10)
    r = check_g03(p)
    assert any(f.severity == Severity.FAIL and "Invalid" in f.message for f in r)


def test_g03_too_short(tmp_path):
    p = tmp_path / "f.sgy"
    p.write_bytes(b"abc")
    assert check_g03(p)[0].severity == Severity.FAIL