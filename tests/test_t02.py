import struct

import numpy as np

from segyqc.header_checks import check_t02
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


def test_t02_clean(tmp_path):
    p = tmp_path / "a.sgy"
    make_sgy(p, good_traces())
    r = check_t02(p)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_t02_nan(tmp_path):
    p = tmp_path / "b.sgy"
    t = good_traces()
    t[4, 2] = np.nan
    make_sgy(p, t)
    r = check_t02(p)
    assert r[0].severity == Severity.FAIL
    assert "1 NaN and 0 Inf" in r[0].message and "[4]" in r[0].message


def test_t02_inf(tmp_path):
    p = tmp_path / "c.sgy"
    t = good_traces()
    t[1, 0] = np.inf
    t[1, 5] = -np.inf
    make_sgy(p, t)
    r = check_t02(p)
    assert r[0].severity == Severity.FAIL
    assert "0 NaN and 2 Inf" in r[0].message and "1 of 20" in r[0].message


def test_t02_nan_and_inf_in_different_traces(tmp_path):
    p = tmp_path / "d.sgy"
    t = good_traces()
    t[2, 3] = np.nan
    t[9, 3] = np.inf
    make_sgy(p, t)
    r = check_t02(p)
    assert "1 NaN and 1 Inf" in r[0].message and "2 of 20" in r[0].message


def test_t02_too_short(tmp_path):
    p = tmp_path / "e.sgy"
    p.write_bytes(b"abc")
    assert check_t02(p)[0].severity == Severity.FAIL

def make_raw(path, raw_samples, fmt):
    """File dengan byte sampel mentah (4 byte per sampel), untuk uji format."""
    ns = len(raw_samples) // 4
    out = bytearray(3600)
    out[3216:3218] = struct.pack(">h", 4000)
    out[3220:3222] = struct.pack(">h", ns)
    out[3224:3226] = struct.pack(">h", fmt)
    th = bytearray(240)
    th[114:116] = struct.pack(">h", ns)
    th[116:118] = struct.pack(">h", 4000)
    out += th + raw_samples
    path.write_bytes(bytes(out))


def test_t02_ibm_out_of_range_detected(tmp_path):
    p = tmp_path / "ibm.sgy"
    make_raw(p, bytes.fromhex("7FFFFFFF") + bytes.fromhex("41100000") * 3, fmt=1)
    r = check_t02(p)
    assert r[0].severity == Severity.FAIL and "1 NaN" in r[0].message


def test_t02_integer_format_not_applicable(tmp_path):
    p = tmp_path / "int.sgy"
    make_raw(p, bytes(16), fmt=2)
    r = check_t02(p)
    assert r[0].severity == Severity.INFO and "Not applicable" in r[0].message


def test_t02_invalid_format_skipped(tmp_path):
    p = tmp_path / "bad.sgy"
    make_raw(p, bytes(16), fmt=99)
    r = check_t02(p)
    assert r[0].severity == Severity.WARN and "Skipped" in r[0].message