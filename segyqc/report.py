import json
import os
from collections import Counter

from .models import Severity


class Report:
    """Hasil satu kali QC: daftar temuan + ringkasan + ekspor JSON."""

    def __init__(self, path, findings):
        self.path = str(path)
        self.findings = list(findings)

    def summary(self):
        counts = Counter(f.severity.value for f in self.findings)
        return {s.value: counts.get(s.value, 0) for s in Severity}

    @property
    def has_fail(self):
        return any(f.severity == Severity.FAIL for f in self.findings)

    def to_dict(self):
        return {
            "file": self.path,
            "summary": self.summary(),
            "findings": [
                {"check_id": f.check_id, "severity": f.severity.value,
                 "message": f.message}
                for f in self.findings
            ],
        }

    def to_json(self, out_path):
        folder = os.path.dirname(os.fspath(out_path))
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
        return out_path