import struct

import numpy as np

from segyqc.header_checks import check_g01
from segyqc.models import Severity


def make_sgy(path, positions, ns=4):
    """SEG-Y sintetis (IEEE float). positions = list (inline, crossline) per trace."""
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


def test_g01_complete(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p, grid(range(100, 104), range(1, 6)))
    r = check_g01(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_g01_missing_inline(tmp_path):
    p = tmp_path / "b.sgy"
    make_sgy(p, grid([100, 101, 103, 104], range(1, 4)))
    r = check_g01(p)
    assert any(f.severity == Severity.FAIL and "inline" in f.message and "102" in f.message
               for f in r)


def test_g01_missing_crossline(tmp_path):
    p = tmp_path / "c.sgy"
    make_sgy(p, grid(range(100, 103), [1, 2, 4, 5]))
    r = check_g01(p)
    assert any(f.severity == Severity.FAIL and "crossline" in f.message and "[3]" in f.message
               for f in r)


def test_g01_hole_in_grid(tmp_path):
    p = tmp_path / "d.sgy"
    pos = grid(range(100, 103), range(1, 4))
    pos.remove((101, 2))
    make_sgy(p, pos)
    r = check_g01(p)
    assert len(r) == 1 and r[0].severity == Severity.WARN
    assert "1 grid position" in r[0].message


def test_g01_regular_step_is_not_a_gap(tmp_path):
    p = tmp_path / "e.sgy"
    make_sgy(p, grid([100, 102, 104], [10, 20, 30]))
    r = check_g01(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_g01_unset_lines(tmp_path):
    p = tmp_path / "f.sgy"
    make_sgy(p, [(0, 0)] * 5)
    assert check_g01(p)[0].severity == Severity.FAIL


def test_g01_too_short(tmp_path):
    p = tmp_path / "g.sgy"
    p.write_bytes(b"abc")
    assert check_g01(p)[0].severity == Severity.FAIL