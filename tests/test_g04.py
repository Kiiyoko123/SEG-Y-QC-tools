import struct

import numpy as np

from segyqc.header_checks import check_g04
from segyqc.models import Severity


def make_sgy(path, rows, scalar=-100, ns=4):
    """rows = list (inline, crossline, x, y) dengan x/y dalam satuan nyata.
    Koordinat disimpan sebagai integer sesuai scalar (-100 -> dikali 100)."""
    factor = 100 if scalar == -100 else 1
    out = bytearray(3600)
    out[3216:3218] = struct.pack(">h", 4000)
    out[3220:3222] = struct.pack(">h", ns)
    out[3224:3226] = struct.pack(">h", 5)
    for il, xl, x, y in rows:
        th = bytearray(240)
        th[70:72] = struct.pack(">h", scalar)
        th[114:116] = struct.pack(">h", ns)
        th[116:118] = struct.pack(">h", 4000)
        th[180:184] = struct.pack(">i", int(round(x * factor)))
        th[184:188] = struct.pack(">i", int(round(y * factor)))
        th[188:192] = struct.pack(">i", il)
        th[192:196] = struct.pack(">i", xl)
        out += th + np.zeros(ns, dtype=">f4").tobytes()
    path.write_bytes(bytes(out))


def rows(ils, xls):
    """Grid dengan koordinat affine (agak miring), bin sekitar 20 x 25 unit."""
    return [(i, x, 500000 + 20 * i + 5 * x, 4000000 + 3 * i + 25 * x)
            for i in ils for x in xls]


def shifted(rs, idx, dx):
    il, xl, x, y = rs[idx]
    rs = list(rs)
    rs[idx] = (il, xl, x + dx, y)
    return rs


def test_g04_consistent(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p, rows(range(100, 104), range(1, 6)))
    r = check_g04(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_g04_scalar_zero_treated_as_one(tmp_path):
    p = tmp_path / "b.sgy"
    make_sgy(p, rows(range(100, 104), range(1, 6)), scalar=0)
    r = check_g04(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_g04_small_deviation_warns(tmp_path):
    p = tmp_path / "c.sgy"
    make_sgy(p, shifted(rows(range(100, 104), range(1, 6)), 0, 6))
    assert check_g04(p)[0].severity == Severity.WARN


def test_g04_large_deviation_fails(tmp_path):
    p = tmp_path / "d.sgy"
    make_sgy(p, shifted(rows(range(100, 104), range(1, 6)), 0, 100))
    r = check_g04(p)
    assert r[0].severity == Severity.FAIL and "inconsistent" in r[0].message


def test_g04_all_coordinates_zero(tmp_path):
    p = tmp_path / "e.sgy"
    make_sgy(p, [(i, x, 0, 0) for i in range(100, 103) for x in range(1, 4)])
    r = check_g04(p)
    assert r[0].severity == Severity.FAIL and "0 in every trace" in r[0].message


def test_g04_constant_coordinates(tmp_path):
    p = tmp_path / "f.sgy"
    make_sgy(p, [(i, x, 1000, 2000) for i in range(100, 103) for x in range(1, 4)])
    r = check_g04(p)
    assert r[0].severity == Severity.FAIL and "do not change" in r[0].message


def test_g04_unset_lines(tmp_path):
    p = tmp_path / "g.sgy"
    make_sgy(p, [(0, 0, 500000 + k, 4000000 + k) for k in range(5)])
    assert check_g04(p)[0].severity == Severity.FAIL


def test_g04_single_inline_warns(tmp_path):
    p = tmp_path / "h.sgy"
    make_sgy(p, rows([100], range(1, 6)))
    assert check_g04(p)[0].severity == Severity.WARN


def test_g04_too_short(tmp_path):
    p = tmp_path / "i.sgy"
    p.write_bytes(b"abc")
    assert check_g04(p)[0].severity == Severity.FAIL