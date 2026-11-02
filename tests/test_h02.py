import struct

from segyqc.header_checks import check_h02
from segyqc.models import Severity


def make_file(path, interval=4000, samples=100, fmt=5):
    data = bytearray(3600)
    data[3216:3218] = struct.pack(">h", interval)
    data[3220:3222] = struct.pack(">h", samples)
    data[3224:3226] = struct.pack(">h", fmt)
    path.write_bytes(bytes(data))


def test_h02_valid(tmp_path):
    p = tmp_path / "a.sgy"
    make_file(p)
    result = check_h02(p)
    assert len(result) == 1 and result[0].severity == Severity.INFO


def test_h02_bad_format(tmp_path):
    p = tmp_path / "b.sgy"
    make_file(p, fmt=99)
    assert any("format code" in f.message for f in check_h02(p))


def test_h02_zero_interval(tmp_path):
    p = tmp_path / "c.sgy"
    make_file(p, interval=0)
    assert any("interval" in f.message for f in check_h02(p))


def test_h02_zero_samples(tmp_path):
    p = tmp_path / "d.sgy"
    make_file(p, samples=0)
    assert any("Samples" in f.message for f in check_h02(p))


def test_h02_multiple_defects(tmp_path):
    p = tmp_path / "e.sgy"
    make_file(p, interval=0, samples=0, fmt=99)
    assert len(check_h02(p)) == 3


def test_h02_too_short(tmp_path):
    p = tmp_path / "f.sgy"
    p.write_bytes(b"abc")
    assert check_h02(p)[0].severity == Severity.FAIL