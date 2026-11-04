import struct

import numpy as np

from segyqc.header_checks import check_g01, check_g02, check_g04
from segyqc.models import Severity

TEAPOT_LIKE = dict(inline=181, crossline=185, cdp_x=189, cdp_y=193)


def make_teapot_like(path, n_il=4, n_xl=5, ns=4):
    """Layout non-standar: inline di byte 181, crossline di 185, X di 189, Y di 193."""
    out = bytearray(3600)
    out[3216:3218] = struct.pack(">h", 4000)
    out[3220:3222] = struct.pack(">h", ns)
    out[3224:3226] = struct.pack(">h", 5)
    for il in range(100, 100 + n_il):
        for xl in range(1, 1 + n_xl):
            th = bytearray(240)
            th[70:72] = struct.pack(">h", -100)
            th[114:116] = struct.pack(">h", ns)
            x = 500000 + 20 * il + 5 * xl
            y = 4000000 + 3 * il + 25 * xl
            th[180:184] = struct.pack(">i", il)
            th[184:188] = struct.pack(">i", xl)
            th[188:192] = struct.pack(">i", x * 100)
            th[192:196] = struct.pack(">i", y * 100)
            out += th + np.zeros(ns, dtype=">f4").tobytes()
    path.write_bytes(bytes(out))


def test_custom_byte_locations_read_correctly(tmp_path):
    p = tmp_path / "t.sgy"
    make_teapot_like(p)
    assert check_g01(p, inline=181, crossline=185)[0].severity == Severity.INFO
    assert check_g02(p, inline=181, crossline=185)[0].severity == Severity.INFO
    r = check_g04(p, **TEAPOT_LIKE)
    assert len(r) == 1 and r[0].severity == Severity.INFO


def test_default_bytes_misread_nonstandard_file(tmp_path):
    p = tmp_path / "t.sgy"
    make_teapot_like(p)
    r = check_g01(p)  # byte 189/193 berisi koordinat, bukan nomor line
    assert r[0].severity != Severity.INFO