import os

import yaml

DEFAULT_BYTE_LOCATIONS = {"inline": 189, "crossline": 193, "cdp_x": 181, "cdp_y": 185}
DEFAULT_THRESHOLDS = {
    "dead_trace_rms": 1e-8,
    "rms_outlier_mad": 6.0,
    "clip_fraction": 0.001,
}


class ConfigError(ValueError):
    """qc.yaml tidak valid."""


def _number(name, value):
    if isinstance(value, bool):
        raise ConfigError(f"thresholds.{name} must be a number, got {value!r}.")
    if isinstance(value, str):  # PyYAML membaca "1e-8" (tanpa titik) sebagai teks
        try:
            value = float(value)
        except ValueError:
            raise ConfigError(f"thresholds.{name} must be a number, got {value!r}.")
    if not isinstance(value, (int, float)):
        raise ConfigError(f"thresholds.{name} must be a number, got {value!r}.")
    if value <= 0:
        raise ConfigError(f"thresholds.{name} must be > 0, got {value}.")
    if name == "clip_fraction" and value >= 1:
        raise ConfigError(f"thresholds.clip_fraction must be < 1, got {value}.")
    return float(value)


def load_config(path=None):
    """Baca qc.yaml. path=None -> nilai bawaan. Mengembalikan dict
    {"byte_locations": {...}, "thresholds": {...}} yang sudah lengkap dan valid."""
    cfg = {"byte_locations": dict(DEFAULT_BYTE_LOCATIONS),
           "thresholds": dict(DEFAULT_THRESHOLDS)}
    if path is None:
        return cfg

    with open(os.fspath(path), "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError("Config must be a YAML mapping (key: value pairs).")

    unknown = set(data) - set(cfg)
    if unknown:
        raise ConfigError(f"Unknown config section(s): {sorted(unknown)}. "
                          f"Allowed: {sorted(cfg)}.")

    for key, value in (data.get("byte_locations") or {}).items():
        if key not in DEFAULT_BYTE_LOCATIONS:
            raise ConfigError(f"Unknown byte_locations key {key!r}. "
                              f"Allowed: {sorted(DEFAULT_BYTE_LOCATIONS)}.")
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 237:
            raise ConfigError(f"byte_locations.{key} must be an integer 1-237, "
                              f"got {value!r}.")
        cfg["byte_locations"][key] = value

    for key, value in (data.get("thresholds") or {}).items():
        if key not in DEFAULT_THRESHOLDS:
            raise ConfigError(f"Unknown thresholds key {key!r}. "
                              f"Allowed: {sorted(DEFAULT_THRESHOLDS)}.")
        cfg["thresholds"][key] = _number(key, value)
    return cfg