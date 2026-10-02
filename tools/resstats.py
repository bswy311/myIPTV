"""统计已探测结果里的分辨率覆盖率，用来判断「按分辨率排序」是否真的有效。

用法：python tools/resstats.py [data/probed.json]
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/probed.json")
data = json.loads(src.read_text(encoding="utf-8"))
alive = [s for s in data if s.get("ok")]

print(f"{src}：共 {len(data)} 条，可用 {len(alive)} 条")
cnt = collections.Counter((s.get("resolution") or "(未声明)") for s in alive)
for name, n in cnt.most_common(15):
    print(f"  {name:14s} {n:5d}  {n / max(len(alive), 1) * 100:5.1f}%")

named = sum(n for k, n in cnt.items() if k != "(未声明)")
print(f"\n有分辨率声明的 {named}/{len(alive)}（{named / max(len(alive), 1) * 100:.1f}%）")

kinds = collections.Counter(s.get("kind") for s in alive)
print("流类型：", dict(kinds))

print("\n非 1080p 声明的源（拿来验证标清判定）：")
for s in alive:
    res = s.get("resolution") or ""
    if res and res != "1920x1080":
        print(f"  {res:12s} {s.get('display')} | {s.get('url')}")
