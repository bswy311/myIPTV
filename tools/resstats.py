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

# ---- 分辨率 ----
named = [s for s in alive if s.get("height")]
print(f"\n分辨率解出来的：{len(named)}/{len(alive)}"
      f"（{len(named) / max(len(alive), 1) * 100:.1f}%）")
buckets = collections.Counter()
for s in named:
    h = s["height"]
    if h >= 1800:
        buckets["2160p+   340分"] += 1
    elif h >= 1000:
        buckets["1080p    300分"] += 1
    elif h >= 700:
        buckets["720p     200分"] += 1
    elif h >= 500:
        buckets["标清576   30分"] += 1
    else:
        buckets["更低       0分"] += 1
buckets["未解出   150分"] = len(alive) - len(named)
for k in sorted(buckets, key=lambda x: -int(x.split()[-1].rstrip("分"))):
    print(f"  {k}  {buckets[k]:4d}")

# ---- 音轨 ----
bad = [s for s in alive if s.get("audio_bad")]
with_audio = [s for s in alive if s.get("audio_kbps")]
print(f"\n音轨测出来的：{len(with_audio)}/{len(alive)}"
      f"（{len(with_audio) / max(len(alive), 1) * 100:.1f}%）")
print(f"判定音轨残缺（audio_bad）的：{len(bad)} 条")
for s in sorted(bad, key=lambda s: (s["audio_kbps"], s.get("display") or "")):
    print(f"  {s['audio_kbps']:6.1f} kbps  {s.get('audio_codec') or '-':5s} "
          f"{s.get('resolution') or '-':12s} {s.get('display')}")
    print(f"        {s.get('url')}")

kinds = collections.Counter(s.get("kind") for s in alive)
print("\n流类型：", dict(kinds))
