"""按频道名查一个频道的所有线路（排错用）。

用法：
    python tools/findchannel.py 黑龙江卫视 河北4K [data/probed.json]

会把每条线路的 URL、分辨率、音轨、评分都列出来，方便判断
「这个频道还有没有能用的源」以及「哪条源是标错了频道」。
"""
from __future__ import annotations

import json
import pathlib
import sys

args = sys.argv[1:]
paths = [a for a in args if a.endswith(".json")]
names = [a for a in args if not a.endswith(".json")]
src = pathlib.Path(paths[0] if paths else "data/probed.json")
if not src.exists():
    src = pathlib.Path("data/raw.json")

data = json.loads(src.read_text(encoding="utf-8"))
print(f"数据源：{src}（{len(data)} 条）\n")

for name in names:
    hits = [s for s in data if name in (s.get("name") or "") or name in (s.get("display") or "")]
    alive = [s for s in hits if s.get("ok")]
    print(f"=== {name}：共 {len(hits)} 条，可用 {len(alive)} 条")
    for s in sorted(hits, key=lambda x: -float(x.get("score") or 0)):
        flag = "OK " if s.get("ok") else "死 "
        bad = " ⚠音轨" if s.get("audio_bad") else ""
        print(f"  {flag} {float(s.get('score') or 0):7.0f}  "
              f"{(s.get('resolution') or '-'):11s} "
              f"{float(s.get('audio_kbps') or 0):6.1f}k{bad:6s} "
              f"[{s.get('source') or '?'}]")
        print(f"        {s.get('url')}")
    print()
