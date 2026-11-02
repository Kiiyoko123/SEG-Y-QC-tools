import struct

import numpy as np

from segyqc.header_checks import check_g02
from segyqc.models import Severity


def make_sgy(path, positions, ns=4):
    out = bytearray(3600)
    out[3216:3218] = struct.pack(">h", 4000)
    out[3220:3222] = struct.pack(">h", ns)
    out[3224:3226] = struct.pack(">h", 5)
    for il, xl in positions:
        th = bytearray(240)
        th[114:116] = struct.pack(">h", ns)
        th[116:118] = struct.pack(">h", 4000)
        th[188:192] = struct.pack(">i", il)
        th[192:196] = struct.pack(">i", xl)
        out += th + np.zeros(ns, dtype=">f4").tobytes()
    path.write_bytes(bytes(out))


def grid(ils, xls):
    return [(i, x) for i in ils for x in xls]


def test_g02_no_duplicates(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p, grid(range(100, 103), range(1, 4)))
    r = check_g02(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_g02_one_duplicate(tmp_path):
    p = tmp_path / "b.sgy"
    pos = grid(range(100, 103), range(1, 4))
    pos.append((101, 2))
    make_sgy(p, pos)
    r = check_g02(p)
    assert r[0].severity == Severity.FAIL
    assert "1 position" in r[0].message and "(101, 2) x2" in r[0].message


def test_g02_multiple_duplicates(tmp_path):
    p = tmp_path / "c.sgy"
    pos = grid(range(100, 102), range(1, 3)) + [(100, 1), (100, 1), (101, 2)]
    make_sgy(p, pos)
    r = check_g02(p)
    assert r[0].severity == Severity.FAIL
    assert "2 position" in r[0].message and "3 extra" in r[0].message


def test_g02_unset_lines(tmp_path):
    p = tmp_path / "d.sgy"
    make_sgy(p, [(0, 0)] * 5)
    assert check_g02(p)[0].severity == Severity.FAIL


def test_g02_too_short(tmp_path):
    p = tmp_path / "e.sgy"
    p.write_bytes(b"abc")
    assert check_g02(p)[0].severity == Severity.FAIL