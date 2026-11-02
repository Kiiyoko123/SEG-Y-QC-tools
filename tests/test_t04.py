import struct

import numpy as np

from segyqc.header_checks import check_t04
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


def good_traces(n=40, ns=100):
    return np.random.default_rng(0).standard_normal((n, ns))


def test_t04_clean(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p, good_traces())
    r = check_t04(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_t04_high_outlier(tmp_path):
    p = tmp_path / "b.sgy"
    t = good_traces()
    t[7] *= 10
    make_sgy(p, t)
    r = check_t04(p)
    assert r[0].severity == Severity.WARN
    assert "1 high, 0 low" in r[0].message and "[7]" in r[0].message


def test_t04_low_outlier(tmp_path):
    p = tmp_path / "c.sgy"
    t = good_traces()
    t[2] *= 0.05
    make_sgy(p, t)
    r = check_t04(p)
    assert r[0].severity == Severity.WARN and "0 high, 1 low" in r[0].message


def test_t04_dead_trace_excluded(tmp_path):
    p = tmp_path / "d.sgy"
    t = good_traces()
    t[0] = 0
    make_sgy(p, t)
    r = check_t04(p)
    assert r[0].severity == Severity.INFO and "excluded" in r[0].message


def test_t04_nan_trace_excluded(tmp_path):
    p = tmp_path / "e.sgy"
    t = good_traces()
    t[1, 3] = np.nan
    make_sgy(p, t)
    r = check_t04(p)
    assert r[0].severity == Severity.INFO and "excluded" in r[0].message


def test_t04_too_few_traces(tmp_path):
    p = tmp_path / "f.sgy"
    make_sgy(p, good_traces(n=5))
    r = check_t04(p)
    assert r[0].severity == Severity.WARN and "Skipped" in r[0].message


def test_t04_identical_rms(tmp_path):
    p = tmp_path / "g.sgy"
    one = np.random.default_rng(3).standard_normal(100)
    make_sgy(p, np.tile(one, (20, 1)))
    r = check_t04(p)
    assert r[0].severity == Severity.INFO and "identical" in r[0].message


def test_t04_mad_zero_warns(tmp_path):
    p = tmp_path / "h.sgy"
    one = np.random.default_rng(3).standard_normal(100)
    t = np.tile(one, (20, 1))
    t[4] *= 3
    make_sgy(p, t)
    r = check_t04(p)
    assert r[0].severity == Severity.WARN and "MAD = 0" in r[0].message


def test_t04_too_short(tmp_path):
    p = tmp_path / "i.sgy"
    p.write_bytes(b"abc")
    assert check_t04(p)[0].severity == Severity.FAIL