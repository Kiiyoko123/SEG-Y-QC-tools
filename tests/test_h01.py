from segyqc.header_checks import check_h01
from segyqc.models import Severity

CARDS = "".join(f"C{i:2d} SYNTHETIC TEST HEADER".ljust(80) for i in range(1, 41))


def test_h01_ebcdic_ok(tmp_path):
    p = tmp_path / "a.sgy"
    p.write_bytes(CARDS.encode("cp037"))
    assert check_h01(p).severity == Severity.INFO


def test_h01_ascii_warns(tmp_path):
    p = tmp_path / "b.sgy"
    p.write_bytes(CARDS.encode("ascii"))
    assert check_h01(p).severity == Severity.WARN


def test_h01_garbage_fails(tmp_path):
    p = tmp_path / "c.sgy"
    p.write_bytes(bytes(range(256)) * 13)
    assert check_h01(p).severity == Severity.FAIL


def test_h01_too_short_fails(tmp_path):
    p = tmp_path / "d.sgy"
    p.write_bytes(b"abc")
    assert check_h01(p).severity == Severity.FAIL