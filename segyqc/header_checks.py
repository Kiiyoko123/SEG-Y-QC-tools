import struct

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