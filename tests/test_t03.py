import struct

import numpy as np

from segyqc.header_checks import check_t03
from segyqc.models import Severity


def make_sgy(path, traces):
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


def good_traces(n=20, ns=200):
    return np.random.default_rng(0).standard_normal((n, ns))


def clip(trace, level):
    return np.clip(trace, -level, level)


def test_t03_clean(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p, good_traces())
    r = check_t03(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_t03_one_clipped_warns(tmp_path):
    p = tmp_path / "b.sgy"
    t = good_traces()
    t[5] = clip(t[5], 0.5)
    make_sgy(p, t)
    r = check_t03(p)
    assert r[0].severity == Severity.WARN
    assert "1 of 20" in r[0].message and "[5]" in r[0].message


def test_t03_many_clipped_fails(tmp_path):
    p = tmp_path / "c.sgy"
    t = good_traces()
    for i in (0, 1, 2):
        t[i] = clip(t[i], 0.5)
    make_sgy(p, t)
    assert check_t03(p)[0].severity == Severity.FAIL


def test_t03_constant_trace_not_counted(tmp_path):
    p = tmp_path / "d.sgy"
    t = good_traces()
    t[3] = 5.0
    make_sgy(p, t)
    r = check_t03(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_t03_single_extreme_not_clipped(tmp_path):
    p = tmp_path / "e.sgy"
    t = np.ones((10, 50)) * 0.1
    t[:, 0] = 1.0
    t[:, 1:] += np.random.default_rng(1).standard_normal((10, 49)) * 0.01
    make_sgy(p, t)
    r = check_t03(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_t03_too_short(tmp_path):
    p = tmp_path / "f.sgy"
    p.write_bytes(b"abc")
    assert check_t03(p)[0].severity == Severity.FAIL