import struct

import numpy as np

from segyqc.header_checks import check_h04
from segyqc.models import Severity


def make_sgy(path, ns_list, bin_ns=20, header_ns=None):
    """SEG-Y sintetis (IEEE float). ns_list = panjang FISIK tiap trace (jumlah sampel).
    header_ns = sample count yang DITULIS di tiap trace header (default sama dengan fisik)."""
    out = bytearray(3600)
    out[3216:3218] = struct.pack(">h", 4000)
    out[3220:3222] = struct.pack(">h", bin_ns)
    out[3224:3226] = struct.pack(">h", 5)
    for i, ns in enumerate(ns_list):
        th = bytearray(240)
        th[114:116] = struct.pack(">h", header_ns[i] if header_ns else ns)
        th[116:118] = struct.pack(">h", 4000)
        out += th + np.zeros(ns, dtype=">f4").tobytes()
    path.write_bytes(bytes(out))


def _messages(findings):
    return " | ".join(f.message for f in findings)


def test_h04_constant(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p, [20] * 10)
    r = check_h04(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_h04_header_declares_different(tmp_path):
    p = tmp_path / "b.sgy"
    make_sgy(p, [20] * 10, header_ns=[20] * 7 + [25] * 3)
    r = check_h04(p)
    assert r[0].severity == Severity.FAIL and "not constant" in r[0].message


def test_h04_physically_variable(tmp_path):
    p = tmp_path / "c.sgy"
    make_sgy(p, [20] * 5 + [30] + [20] * 4)
    r = check_h04(p)
    assert all(f.severity == Severity.FAIL for f in r)
    assert "index 5" in _messages(r)


def test_h04_truncated(tmp_path):
    p = tmp_path / "d.sgy"
    make_sgy(p, [20] * 10)
    p.write_bytes(p.read_bytes()[:-50])
    assert "truncated" in _messages(check_h04(p))


def test_h04_trailing_bytes(tmp_path):
    p = tmp_path / "e.sgy"
    make_sgy(p, [20] * 10)
    p.write_bytes(p.read_bytes() + b"xyz")
    assert "3 trailing" in _messages(check_h04(p))


def test_h04_too_short(tmp_path):
    p = tmp_path / "f.sgy"
    p.write_bytes(b"abc")
    assert check_h04(p)[0].severity == Severity.FAIL