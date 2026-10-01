from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "config.yaml"


class Dot(dict):
    """支持 cfg.network.concurrency 这种点号访问的字典。"""

    def __getattr__(self, key: str) -> Any:
        if key.startswith("__"):
            raise AttributeError(key)
        return self.get(key)

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def get_path(self, path: str, default: Any = None) -> Any:
        cur: Any = self
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


def _wrap(value: Any) -> Any:
    if isinstance(value, dict):
        return Dot({k: _wrap(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_wrap(v) for v in value]
    return value


def load_config(path: str | os.PathLike[str] | None = None) -> Dot:
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    if not cfg_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    cfg = _wrap(raw)
    cfg["_path"] = str(cfg_path)
    cfg["_root"] = str(ROOT)
    return cfg


def resolve(cfg: Dot, *parts: str) -> Path:
    """把配置里的相对路径解析成基于项目根目录的绝对路径。"""
    value = cfg.get_path(".".join(parts)) or ""
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / p
    return p


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
