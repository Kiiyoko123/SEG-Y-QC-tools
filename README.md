# segyqc

Automated quality control for **post-stack 3D SEG-Y** files: header validation, geometry checks, and trace-level amplitude diagnostics, with a pass/warn/fail report.

> **Status: early development (v0.1 in progress).** Items marked ✅ are implemented and tested; items marked 🔲 are planned. Do not rely on a check until it is ✅.

---

## Why this exists

SEG-Y files from the field, vendors, or public archives are frequently non-compliant: trace headers at non-standard byte locations, wrong coordinate scalars, missing inlines, dead traces, inconsistent sample counts. Most tools either crash on such files or silently load garbage. `segyqc` answers one question before you start interpretation or processing: **is this file safe to use, and if not, what exactly is wrong?**

This tool does not repair data and does not replace commercial QC suites. It reports problems; it does not hide them.

## Scope

| In scope (v0.1) | Out of scope (for now) |
|---|---|
| Post-stack 3D volumes | Pre-stack / gathers |
| SEG-Y Rev 0 / Rev 1, IBM and IEEE float | SEG-Y Rev 2 |
| Files larger than RAM (chunked reading) | Writing / repairing SEG-Y |
| CLI + Python API + Colab demo | GUI |

## Checks

Every check has an ID, a severity (`INFO` / `WARN` / `FAIL`), and configurable thresholds.

| ID | Check | Status |
|---|---|---|
| H-01 | Textual (EBCDIC) header decodable | ✅ |
| H-02 | Binary header: valid format code, sample interval > 0, samples/trace > 0 | ✅ |
| H-03 | Binary header sample interval/count agrees with trace headers | ✅ |
| H-04 | Constant sample count across all traces (header and physical size) | ✅ |
| G-01 | Inline/crossline grid completeness (gaps, missing lines) | 🔲 |
| G-02 | Duplicate (inline, crossline) positions | 🔲 |
| G-03 | Coordinate scalar valid and consistent | 🔲 |
| G-04 | Header X/Y consistent with inline/crossline (affine fit residual) | 🔲 |
| T-01 | Dead / constant traces | 🔲 |
| T-02 | NaN / Inf samples | 🔲 |
| T-03 | Amplitude clipping | 🔲 |
| T-04 | Trace RMS outliers (robust z-score, MAD-based) | 🔲 |
| T-05 | Average amplitude spectrum, dominant frequency vs. Nyquist | 🔲 |

## Installation

```bash
git clone https://github.com/Kiiyoko123/SEG-Y-QC-tools.git
cd SEG-Y-QC-tools
pip install -e .
```

Requires Python ≥ 3.9. Core dependencies: `numpy`, `segyio`, `matplotlib`, `pyyaml`.

## Usage (target API)

### Command line

```bash
segyqc check survey.sgy --config qc.yaml --out report/
```

Produces `report/report.json` (machine-readable) and `report/report.html` (human-readable, with maps and plots). Exit code is non-zero if any `FAIL` is raised, so it can be used in pipelines.

### Python

```python
from segyqc import run_qc

report = run_qc("survey.sgy", config="qc.yaml")
print(report.summary())      # counts of INFO / WARN / FAIL
report.to_html("report.html")
```

### Non-standard header byte locations

```yaml
# qc.yaml
byte_locations:
  inline: 189      # default
  crossline: 193   # default
  cdp_x: 181
  cdp_y: 185
thresholds:
  dead_trace_rms: 1.0e-8
  rms_outlier_mad: 6.0
  clip_fraction: 0.001
```

### Google Colab

A demo notebook is planned at `notebooks/demo.ipynb`. Note that Colab disk and RAM are limited; large volumes must be processed in chunks, which is how `segyqc` reads data by default.

## Example output

*(Screenshot of the HTML report on a public dataset will be added here once checks G-01 to T-04 are implemented.)*

## Design decisions

- **Reading is delegated to [`segyio`](https://github.com/equinor/segyio)** with `ignore_geometry=True`. Geometry is inferred and validated by `segyqc` itself, because `segyio` raises on exactly the malformed files this tool is meant to diagnose.
- **No data is loaded entirely into memory.** Headers are read as arrays; traces are processed in chunks.
- **Statistics use robust estimators** (median/MAD), because amplitude distributions in seismic data are heavy-tailed and mean/std produce false positives.
- **Thresholds are configurable and documented**, not hard-coded magic numbers.

## Testing

Unit tests use **synthetic SEG-Y files** generated with known defects (missing inline, duplicated traces, wrong scalar, dead traces, clipped amplitudes), so every check is verified against ground truth.

```bash
pip install -e ".[dev]"
pytest
```

## Test data

This project is developed and validated **only on openly licensed public datasets**. No proprietary or confidential data is used anywhere in this repository.

- Netherlands Offshore F3 Block
- Teapot Dome

For each dataset, the source URL, license, and attribution requirements will be recorded in `docs/datasets.md` before it is used in any result shown here.

Datasets are **not** committed or redistributed. They are fetched with a download script (`scripts/download_data.py`, planned), and `*.sgy` / `*.segy` are listed in `.gitignore`.

## Limitations

- Heuristic checks (T-04, T-05) flag anomalies; they cannot determine whether an anomaly is geological or an acquisition/processing artifact.
- No polarity or phase determination.
- Results on files with severely corrupted binary headers may be unreliable.
- H-04 first checks total file size against the binary header; a file whose trace-length deviations exactly cancel out can pass this first test.
- G-01 reads inline/crossline from fixed byte locations (189/193); configurable locations are planned. Missing grid positions are reported as WARN because survey outlines can be non-rectangular.

## Roadmap

- [ ] v0.1: H-01 to H-04, G-01 to G-04, T-01 to T-04, JSON report, CLI
- [ ] v0.2: HTML report with inline/crossline maps, T-05, CI via GitHub Actions
- [ ] v0.3: Benchmarks on multi-GB files (memory and runtime reported)
- [ ] Later: Rev 2 support, pre-stack gather checks

## Contributing

Issues and pull requests are welcome. Please include a minimal SEG-Y file (or a generator script) that reproduces any bug.

## License

MIT (see `LICENSE`).

## References

- SEG Technical Standards Committee, *SEG-Y rev 1 Data Exchange Format* (2002).
- Equinor, `segyio`: https://github.com/equinor/segyio
