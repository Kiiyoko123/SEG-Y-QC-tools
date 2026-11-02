import os
import struct

import numpy as np
import segyio
from segyio import TraceField

from .models import Finding, Severity

TEXT_HEADER_SIZE = 3200


def _printable_fraction(text):
    return sum(c.isprintable() for c in text) / len(text)


def check_h01(path, min_fraction=0.95):
    """H-01: textual header (3200 bytes) harus terbaca sebagai EBCDIC."""
    with open(path, "rb") as f:
        raw = f.read(TEXT_HEADER_SIZE)

    if len(raw) < TEXT_HEADER_SIZE:
        return Finding("H-01", Severity.FAIL,
                       f"File too short for a textual header ({len(raw)} bytes).")

    if _printable_fraction(raw.decode("cp037")) >= min_fraction:
        return Finding("H-01", Severity.INFO, "Textual header is valid EBCDIC.")

    if _printable_fraction(raw.decode("latin-1")) >= min_fraction:
        return Finding("H-01", Severity.WARN,
                       "Textual header is ASCII, not EBCDIC (readable, non-standard).")

    return Finding("H-01", Severity.FAIL,
                   "Textual header is not decodable as EBCDIC or ASCII.")

BINARY_HEADER_START = 3200
BINARY_HEADER_SIZE = 400
VALID_FORMAT_CODES = {1, 2, 3, 5, 8}  # IBM float, int32, int16, IEEE float, int8


def read_binary_header(path):
    """Baca field penting binary header (big-endian). None kalau file terlalu pendek."""
    with open(path, "rb") as f:
        f.seek(BINARY_HEADER_START)
        raw = f.read(BINARY_HEADER_SIZE)
    if len(raw) < BINARY_HEADER_SIZE:
        return None
    return {
        "interval": struct.unpack(">h", raw[16:18])[0],   # byte 3217-3218
        "samples": struct.unpack(">h", raw[20:22])[0],    # byte 3221-3222
        "format": struct.unpack(">h", raw[24:26])[0],     # byte 3225-3226
    }


def check_h02(path):
    """H-02: format code valid, sample interval > 0, samples/trace > 0."""
    hdr = read_binary_header(path)
    if hdr is None:
        return [Finding("H-02", Severity.FAIL, "File too short for a binary header.")]

    findings = []
    if hdr["format"] not in VALID_FORMAT_CODES:
        findings.append(Finding("H-02", Severity.FAIL,
                                f"Invalid format code: {hdr['format']}."))
    if hdr["interval"] <= 0:
        findings.append(Finding("H-02", Severity.FAIL,
                                f"Sample interval must be > 0 (found {hdr['interval']})."))
    if hdr["samples"] <= 0:
        findings.append(Finding("H-02", Severity.FAIL,
                                f"Samples per trace must be > 0 (found {hdr['samples']})."))

    if not findings:
        findings.append(Finding("H-02", Severity.INFO, "Binary header fields are valid."))
    return findings

def read_trace_header_arrays(path):
    """Baca sample count dan interval dari SEMUA trace header (hanya header)."""
    with segyio.open(path, "r", ignore_geometry=True) as f:
        return {
            "samples": np.asarray(f.attributes(TraceField.TRACE_SAMPLE_COUNT)[:]),
            "interval": np.asarray(f.attributes(TraceField.TRACE_SAMPLE_INTERVAL)[:]),
        }


def _load(path):
    """Return (binary_header, trace_arrays, error_message). Salah satunya None."""
    hdr = read_binary_header(path)
    if hdr is None:
        return None, None, "File too short for a binary header."
    try:
        arrays = read_trace_header_arrays(path)
    except Exception as exc:
        return None, None, f"segyio could not read trace headers: {exc}"
    if len(arrays["samples"]) == 0:
        return None, None, "File contains no traces."
    return hdr, arrays, None


def check_h03(path):
    """H-03: binary header sample count/interval sama dengan trace header."""
    hdr, arrays, err = _load(path)
    if err:
        return [Finding("H-03", Severity.FAIL, err)]

    findings = []
    bad_n = np.flatnonzero(arrays["samples"] != hdr["samples"])
    if len(bad_n):
        findings.append(Finding(
            "H-03", Severity.FAIL,
            f"{len(bad_n)} trace(s) have a sample count different from the binary "
            f"header ({hdr['samples']}). First indices: {bad_n[:5].tolist()}."))

    bad_dt = np.flatnonzero(arrays["interval"] != hdr["interval"])
    if len(bad_dt):
        findings.append(Finding(
            "H-03", Severity.WARN,
            f"{len(bad_dt)} trace(s) have a sample interval different from the binary "
            f"header ({hdr['interval']}). First indices: {bad_dt[:5].tolist()}."))

    if not findings:
        findings.append(Finding("H-03", Severity.INFO,
                                "Binary and trace headers agree on samples and interval."))
    return findings

BYTES_PER_SAMPLE = {1: 4, 2: 4, 3: 2, 5: 4, 8: 1}
TRACE_HEADER_SIZE = 240
EXT_HEADER_COUNT_OFFSET = 3504  # jumlah extended textual header (byte 3505-3506)


def _read_ext_header_count(path):
    with open(path, "rb") as f:
        f.seek(EXT_HEADER_COUNT_OFFSET)
        raw = f.read(2)
    if len(raw) < 2:
        return 0
    return struct.unpack(">h", raw)[0]


def _walk_traces(path, data_start, bytes_per_sample, expected_ns):
    """Telusuri trace demi trace: baca sample count di tiap header, lalu lompat.

    Data amplitudo tidak dimuat. Panjang tiap trace dihitung dari header-nya sendiri.
    """
    size = os.path.getsize(path)
    counts = {}
    first_bad = None
    invalid = None
    n = 0
    pos = data_start
    with open(path, "rb") as f:
        while pos + TRACE_HEADER_SIZE <= size:
            f.seek(pos + 114)
            ns = struct.unpack(">h", f.read(2))[0]
            counts[ns] = counts.get(ns, 0) + 1
            if ns != expected_ns and first_bad is None:
                first_bad = n
            if ns <= 0:
                invalid = (n, ns)
                break
            pos += TRACE_HEADER_SIZE + ns * bytes_per_sample
            n += 1
    truncated = invalid is None and pos > size
    trailing = (size - pos) if (invalid is None and pos <= size) else 0
    return {"counts": counts, "first_bad": first_bad, "invalid": invalid,
            "truncated": truncated, "trailing": trailing}


def check_h04(path):
    """H-04: sample count konstan di semua trace (ukuran fisik di disk + header)."""
    hdr = read_binary_header(path)
    if hdr is None:
        return [Finding("H-04", Severity.FAIL, "File too short for a binary header.")]

    bps = BYTES_PER_SAMPLE.get(hdr["format"])
    if bps is None:
        return [Finding("H-04", Severity.FAIL,
                        f"Cannot determine sample size: invalid format code {hdr['format']}.")]
    if hdr["samples"] <= 0:
        return [Finding("H-04", Severity.FAIL,
                        f"Cannot check trace sizes: binary header samples = {hdr['samples']}.")]

    ext = _read_ext_header_count(path)
    if ext < 0:
        return [Finding("H-04", Severity.WARN,
                        "Variable number of extended text headers is not supported; H-04 skipped.")]

    data_start = 3600 + ext * 3200
    remaining = os.path.getsize(path) - data_start
    trace_size = TRACE_HEADER_SIZE + hdr["samples"] * bps
    if remaining < TRACE_HEADER_SIZE:
        return [Finding("H-04", Severity.FAIL, "File contains no complete trace.")]

    # Lapis 1: ukuran file harus habis dibagi ukuran satu trace.
    if remaining % trace_size == 0:
        _, arrays, err = _load(path)
        if err:
            return [Finding("H-04", Severity.FAIL, err)]
        values, counts = np.unique(arrays["samples"], return_counts=True)
        if len(values) > 1:
            detail = ", ".join(f"{int(v)}: {int(c)} traces" for v, c in zip(values, counts))
            return [Finding("H-04", Severity.FAIL,
                            f"Sample count is not constant in trace headers ({detail}).")]
        return [Finding("H-04", Severity.INFO,
                        f"Sample count is constant ({int(values[0])}) across all traces.")]

    # Lapis 2: ukuran tidak cocok, telusuri untuk mencari penyebabnya.
    findings = [Finding(
        "H-04", Severity.FAIL,
        f"File size does not match {hdr['samples']} samples/trace: {remaining} data bytes "
        f"is not a multiple of the trace size ({trace_size} bytes).")]
    walk = _walk_traces(path, data_start, bps, hdr["samples"])

    if walk["first_bad"] is not None:
        detail = ", ".join(f"{k}: {v} traces" for k, v in sorted(walk["counts"].items()))
        findings.append(Finding(
            "H-04", Severity.FAIL,
            f"Traces have different sample counts ({detail}). "
            f"First trace with a different sample count: index {walk['first_bad']}."))
    if walk["invalid"] is not None:
        idx, ns = walk["invalid"]
        findings.append(Finding(
            "H-04", Severity.FAIL,
            f"Trace index {idx} declares {ns} samples; scanning stopped there."))
    if walk["truncated"]:
        findings.append(Finding(
            "H-04", Severity.FAIL, "Last trace is truncated: file ends before the trace is complete."))
    if walk["trailing"]:
        findings.append(Finding(
            "H-04", Severity.FAIL,
            f"{walk['trailing']} trailing byte(s) after the last complete trace."))
    return findings

def read_line_arrays(path):
    """Baca inline (byte 189) dan crossline (byte 193) dari semua trace header."""
    with segyio.open(path, "r", ignore_geometry=True) as f:
        return (
            np.asarray(f.attributes(TraceField.INLINE_3D)[:], dtype=np.int64),
            np.asarray(f.attributes(TraceField.CROSSLINE_3D)[:], dtype=np.int64),
        )


def _line_gaps(values):
    """Return (nilai unik, step, nilai yang hilang, spasi tidak teratur?)."""
    u = np.unique(values)
    if len(u) < 2:
        return u, 1, np.array([], dtype=np.int64), False
    d = np.diff(u)
    vals, cnts = np.unique(d, return_counts=True)
    step = int(vals[np.argmax(cnts)])
    irregular = bool(np.any(d % step != 0))
    expected = np.arange(u[0], u[-1] + 1, step)
    return u, step, np.setdiff1d(expected, u), irregular


def check_g01(path):
    """G-01: kelengkapan grid inline/crossline (gap, line hilang)."""
    try:
        il, xl = read_line_arrays(path)
    except Exception as exc:
        return [Finding("G-01", Severity.FAIL,
                        f"segyio could not read trace headers: {exc}")]
    if len(il) == 0:
        return [Finding("G-01", Severity.FAIL, "File contains no traces.")]

    if np.all(il == 0) or np.all(xl == 0):
        return [Finding("G-01", Severity.FAIL,
                        "Inline or crossline is 0 in every trace; the values are unset "
                        "or stored at different byte locations.")]

    findings = []
    u_il, step_il, miss_il, irr_il = _line_gaps(il)
    u_xl, step_xl, miss_xl, irr_xl = _line_gaps(xl)

    for name, miss, step, u, irr in (
        ("Inline", miss_il, step_il, u_il, irr_il),
        ("Crossline", miss_xl, step_xl, u_xl, irr_xl),
    ):
        if len(miss):
            findings.append(Finding(
                "G-01", Severity.FAIL,
                f"{len(miss)} {name.lower()}(s) missing between {int(u[0])} and "
                f"{int(u[-1])} (step {step}). {name}s missing: {miss[:10].tolist()}."))
        if irr:
            findings.append(Finding(
                "G-01", Severity.WARN,
                f"{name} spacing is irregular (most common step: {step})."))

    pairs = np.unique(np.column_stack((il, xl)), axis=0)
    holes = len(u_il) * len(u_xl) - len(pairs)
    if holes > 0:
        pct = 100 * holes / (len(u_il) * len(u_xl))
        findings.append(Finding(
            "G-01", Severity.WARN,
            f"{holes} grid position(s) ({pct:.2f}%) have no trace within the present "
            f"inline/crossline range. Survey outlines can be non-rectangular, so this "
            f"may be legitimate."))

    if not findings:
        findings.append(Finding(
            "G-01", Severity.INFO,
            f"Complete grid: {len(u_il)} inlines x {len(u_xl)} crosslines "
            f"({len(pairs)} positions)."))
    return findings

def check_g02(path):
    """G-02: posisi (inline, crossline) duplikat."""
    try:
        il, xl = read_line_arrays(path)
    except Exception as exc:
        return [Finding("G-02", Severity.FAIL,
                        f"segyio could not read trace headers: {exc}")]
    if len(il) == 0:
        return [Finding("G-02", Severity.FAIL, "File contains no traces.")]

    if np.all(il == 0) or np.all(xl == 0):
        return [Finding("G-02", Severity.FAIL,
                        "Inline or crossline is 0 in every trace; duplicate check "
                        "is meaningless (unset values or wrong byte location).")]

    pairs, counts = np.unique(np.column_stack((il, xl)), axis=0, return_counts=True)
    dup = counts > 1
    n_pos = int(dup.sum())
    if n_pos == 0:
        return [Finding("G-02", Severity.INFO,
                        f"No duplicate positions across {len(il)} traces.")]

    extra = int((counts[dup] - 1).sum())
    examples = ", ".join(
        f"({int(a)}, {int(b)}) x{int(c)}"
        for (a, b), c in list(zip(pairs[dup], counts[dup]))[:5])
    return [Finding("G-02", Severity.FAIL,
                    f"{n_pos} position(s) have more than one trace ({extra} extra "
                    f"trace(s) in total). Examples: {examples}.")]

VALID_SCALARS = {1, 10, 100, 1000, 10000, -1, -10, -100, -1000, -10000}


def read_scalar_array(path):
    """Baca coordinate scalar (byte 71) dari semua trace header."""
    with segyio.open(path, "r", ignore_geometry=True) as f:
        return np.asarray(f.attributes(TraceField.SourceGroupScalar)[:], dtype=np.int64)


def check_g03(path):
    """G-03: coordinate scalar valid dan konsisten."""
    try:
        scalars = read_scalar_array(path)
    except Exception as exc:
        return [Finding("G-03", Severity.FAIL,
                        f"segyio could not read trace headers: {exc}")]
    if len(scalars) == 0:
        return [Finding("G-03", Severity.FAIL, "File contains no traces.")]

    values, counts = np.unique(scalars, return_counts=True)
    findings = []

    if len(values) > 1:
        detail = ", ".join(f"{int(v)}: {int(c)} traces" for v, c in zip(values, counts))
        findings.append(Finding("G-03", Severity.FAIL,
                                f"Coordinate scalar is not constant ({detail})."))

    invalid = [int(v) for v in values if v != 0 and int(v) not in VALID_SCALARS]
    if invalid:
        findings.append(Finding(
            "G-03", Severity.FAIL,
            f"Invalid coordinate scalar value(s): {invalid}. Valid: 0, +/-1, 10, 100, "
            f"1000, 10000."))

    if 0 in values:
        n0 = int(counts[list(values).index(0)])
        findings.append(Finding(
            "G-03", Severity.WARN,
            f"{n0} trace(s) have scalar 0, which is undefined in the standard "
            f"(often treated as 1)."))

    if not findings:
        findings.append(Finding(
            "G-03", Severity.INFO,
            f"Coordinate scalar is valid and constant ({int(values[0])}) across all traces."))
    return findings

G04_WARN_FRACTION = 0.1   # simpangan > 10% ukuran sel -> WARN
G04_FAIL_FRACTION = 0.5   # simpangan > 50% ukuran sel -> FAIL


def read_coordinate_arrays(path):
    """Baca CDP_X (byte 181), CDP_Y (byte 185), dan scalar (byte 71)."""
    with segyio.open(path, "r", ignore_geometry=True) as f:
        return (
            np.asarray(f.attributes(TraceField.CDP_X)[:], dtype=np.float64),
            np.asarray(f.attributes(TraceField.CDP_Y)[:], dtype=np.float64),
            np.asarray(f.attributes(TraceField.SourceGroupScalar)[:], dtype=np.float64),
        )


def _apply_scalar(values, scalars):
    """Scalar > 0 mengalikan, < 0 membagi, 0 dianggap 1."""
    denom = np.where(scalars < 0, -scalars, 1.0)
    factor = np.where(scalars > 0, scalars, 1.0 / denom)
    return values * factor


def check_g04(path):
    """G-04: X/Y header konsisten dengan inline/crossline (residual affine fit)."""
    try:
        il, xl = read_line_arrays(path)
        x, y, scalars = read_coordinate_arrays(path)
    except Exception as exc:
        return [Finding("G-04", Severity.FAIL,
                        f"segyio could not read trace headers: {exc}")]
    if len(il) == 0:
        return [Finding("G-04", Severity.FAIL, "File contains no traces.")]

    if np.all(il == 0) or np.all(xl == 0):
        return [Finding("G-04", Severity.FAIL,
                        "Inline or crossline is 0 in every trace; the fit is meaningless "
                        "(unset values or wrong byte location).")]
    if np.all(x == 0) and np.all(y == 0):
        return [Finding("G-04", Severity.FAIL,
                        "X and Y are 0 in every trace; coordinates are unset or stored "
                        "at different byte locations.")]

    x = _apply_scalar(x, scalars)
    y = _apply_scalar(y, scalars)

    il_c = il.astype(np.float64) - il.mean()
    xl_c = xl.astype(np.float64) - xl.mean()
    design = np.column_stack((il_c, xl_c, np.ones(len(il))))

    if np.linalg.matrix_rank(design) < 3:
        return [Finding("G-04", Severity.WARN,
                        "Not enough geometry for an affine fit (need at least two "
                        "inlines and two crosslines that are not collinear).")]

    coef_x = np.linalg.lstsq(design, x, rcond=None)[0]
    coef_y = np.linalg.lstsq(design, y, rcond=None)[0]
    resid = np.hypot(x - design @ coef_x, y - design @ coef_y)
    idx = int(np.argmax(resid))
    max_res = float(resid[idx])

    step_il = _line_gaps(il)[1]
    step_xl = _line_gaps(xl)[1]
    spacing_il = float(np.hypot(coef_x[0], coef_y[0])) * step_il
    spacing_xl = float(np.hypot(coef_x[1], coef_y[1])) * step_xl
    cell = min(spacing_il, spacing_xl)
    scale = max(float(np.abs(x).max()), float(np.abs(y).max()), 1.0)
    if cell <= 1e-9 * scale:
        return [Finding("G-04", Severity.FAIL,
                        "X/Y do not change with inline/crossline; coordinates are "
                        "constant or inconsistent with the line numbers.")]

    ratio = max_res / cell
    detail = (f"max residual {max_res:.2f} coordinate units ({ratio:.0%} of the "
              f"{cell:.2f} cell size) at trace index {idx}")
    if ratio >= G04_FAIL_FRACTION:
        return [Finding("G-04", Severity.FAIL,
                        f"Header X/Y inconsistent with inline/crossline: {detail}.")]
    if ratio >= G04_WARN_FRACTION:
        return [Finding("G-04", Severity.WARN,
                        f"Header X/Y deviate from the inline/crossline fit: {detail}.")]
    return [Finding("G-04", Severity.INFO,
                    f"Header X/Y consistent with inline/crossline: {detail}.")]