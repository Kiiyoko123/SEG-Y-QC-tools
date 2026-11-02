import struct

import numpy as np

from segyqc.header_checks import check_t01
from segyqc.models import Severity


def make_sgy(path, traces):
    """SEG-Y sintetis (IEEE float). traces = array 2D (n_trace, n_sampel)."""
    traces = np.asarray(traces, dtype=">f4")
    ns = traces.shape[1]
    out = bytearray(3600)
    out[3216:3218] = struct.pack(">h", 4000)
    out[3220:3222] = struct.pack(">h", ns)
    out[3224:3226] = struct.pack(">h", 5)
    for row in traces:
        th = bytearray(240)
        th[114:116] = struct.pack(">h", ns)
        th[116:118] = struct.pack(">h", 4000)
        out += th + row.tobytes()
    path.write_bytes(bytes(out))


def good_traces(n=20, ns=16):
    return np.random.default_rng(0).standard_normal((n, ns))


def test_t01_clean(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p, good_traces())
    r = check_t01(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_t01_one_dead_warns(tmp_path):
    p = tmp_path / "b.sgy"
    t = good_traces()
    t[3] = 0
    make_sgy(p, t)
    r = check_t01(p)
    assert r[0].severity == Severity.WARN
    assert "1 trace(s) are dead" in r[0].message and "[3]" in r[0].message


def test_t01_constant_nonzero(tmp_path):
    p = tmp_path / "c.sgy"
    t = good_traces()
    t[7] = 5.0
    make_sgy(p, t)
    r = check_t01(p)
    assert r[0].severity == Severity.WARN and "constant" in r[0].message


def test_t01_many_dead_fails(tmp_path):
    p = tmp_path / "d.sgy"
    t = good_traces()
    t[0] = 0
    t[1] = 0
    make_sgy(p, t)
    assert check_t01(p)[0].severity == Severity.FAIL


def test_t01_all_dead_fails(tmp_path):
    p = tmp_path / "e.sgy"
    make_sgy(p, np.zeros((10, 16)))
    assert check_t01(p)[0].severity == Severity.FAIL


def test_t01_low_amplitude_is_not_dead(tmp_path):
    p = tmp_path / "f.sgy"
    make_sgy(p, good_traces() * 1e-3)
    r = check_t01(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_t01_too_short(tmp_path):
    p = tmp_path / "g.sgy"
    p.write_bytes(b"abc")
    assert check_t01(p)[0].severity == Severity.FAIL