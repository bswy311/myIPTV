#!/usr/bin/env python3
"""项目入口。

用法：
    python main.py run          # 完整流程（推荐）
    python main.py serve        # 只起局域网服务
    python main.py stats        # 查看历史库
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from iptv.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
