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