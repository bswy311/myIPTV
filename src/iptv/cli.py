"""命令行入口：run / collect / publish / serve / stats / reset。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import pipeline, server
from .config import load_config, resolve
from .history import History


def _setup_stdout() -> None:
    """Windows 控制台默认 GBK，中文/进度条容易炸，强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="iptv",
        description="IPTV 直播源自动采集 / 有效性检测 / 自动剔除 / 发布",
    )
    p.add_argument("-c", "--config", default=None, help="配置文件路径，默认 config/config.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="跑完整流程：采集 → 检测 → 剔除 → 发布")
    r.add_argument("--no-progress", action="store_true", help="不打印进度条（适合 CI 日志）")
    r.add_argument("--concurrency", type=int, default=None, help="覆盖并发数")
    r.add_argument("--timeout", type=float, default=None, help="覆盖单请求超时（秒）")
    r.add_argument("--max-probe", type=int, default=None, help="覆盖单次最大探测条数，0 为不限")
    r.add_argument("--mode", choices=["include", "all"], default=None, help="覆盖筛选模式")
    r.add_argument("--serve", action="store_true", help="跑完后顺手起局域网服务")

    c = sub.add_parser("collect", help="只采集并保存原始清单，不做探测")
    c.add_argument("--out", default="data/raw.json", help="输出文件")

    pub = sub.add_parser("publish", help="用上次的探测结果重新生成输出文件（不联网）")
    pub.add_argument("--from", dest="src", default="data/probed.json", help="探测结果文件")

    s = sub.add_parser("serve", help="启动局域网 HTTP 服务，供电视订阅")
    s.add_argument("--port", type=int, default=None, help="覆盖端口")

    sub.add_parser("stats", help="查看历史库统计")

    rs = sub.add_parser("reset", help="清空历史库（会重新检测所有源）")
    rs.add_argument("-y", "--yes", action="store_true", help="跳过确认")

    return p


def _apply_overrides(cfg, args) -> None:
    if getattr(args, "concurrency", None):
        cfg.network["concurrency"] = args.concurrency
    if getattr(args, "timeout", None):
        cfg.network["timeout"] = args.timeout
    if getattr(args, "max_probe", None) is not None:
        cfg.network["max_probe"] = args.max_probe
    if getattr(args, "mode", None):
        cfg.filter["mode"] = args.mode
    if getattr(args, "port", None):
        cfg.server["port"] = args.port


def cmd_collect(cfg, args, log) -> int:
    from . import collect, normalize

    log("采集原始清单 ...")
    raw, stats = asyncio.run(collect.collect_all(cfg))
    for st in stats:
        state = f"失败: {st.error}" if st.error else f"{st.parsed} 条"
        log(f"  {st.name:<22} {state}")
    modes = normalize.source_modes(cfg)
    kept = [s for s in raw if normalize.matches_filter(s, cfg, modes)]
    normalize.normalize(kept, cfg)
    deduped = normalize.dedupe(kept)

    out = Path(args.out)
    if not out.is_absolute():
        out = Path(cfg._root) / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([s.to_dict() for s in deduped], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    log(f"共 {len(raw)} 条 → 筛选 {len(kept)} 条 → 去重 {len(deduped)} 条")
    log(f"已写入 {out}")
    return 0


def cmd_publish(cfg, args, log) -> int:
    from .models import RunStats
    from .history import iso, now_utc
    from . import publish

    src = Path(args.src)
    if not src.is_absolute():
        src = Path(cfg._root) / src
    streams = pipeline.load_streams(src)
    if not streams:
        log(f"没有找到探测结果：{src}，请先执行 `python main.py run`")
        return 1

    alive = [s for s in streams if s.ok]
    if not alive:
        log("结果里没有可用流，无法发布。")
        return 1

    stats = RunStats(
        started_at=iso(now_utc()),
        finished_at=iso(now_utc()),
        probed=len(streams),
        alive=len(alive),
        dead=len(streams) - len(alive),
        channels=len({s.key for s in alive}),
    )
    written = publish.write_outputs(alive, cfg, stats)
    log(f"已发布 {stats.published_channels} 个频道 / {stats.published_streams} 条线路")
    for key, path in written.items():
        log(f"  {key:<7} -> {path}")
    return 0


def cmd_stats(cfg, log) -> int:
    h = pipeline.build_history(cfg)
    s = h.stats()
    log("历史库统计：")
    log(f"  跟踪 URL : {s['tracked']}")
    log(f"  健康     : {s['healthy']}")
    log(f"  已拉黑   : {s['blacklisted']}")
    log(f"  文件     : {resolve(cfg, 'history', 'path')}")
    return 0


def cmd_reset(cfg, args, log) -> int:
    path = resolve(cfg, "history", "path")
    if not path.exists():
        log("历史库本来就不存在，无需清理。")
        return 0
    if not args.yes:
        log(f"将删除 {path}（内含 {len(History(path).load().entries)} 条记录）")
        log("加 -y 参数确认执行，例如：python main.py reset -y")
        return 1
    path.unlink()
    log(f"已删除 {path}，下次运行会重新检测所有源。")
    return 0


def main(argv: list[str] | None = None) -> int:
    _setup_stdout()
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    _apply_overrides(cfg, args)

    def log(msg: str = "") -> None:
        print(msg, flush=True)

    try:
        if args.cmd == "run":
            stats = pipeline.run_sync(cfg, log=log, show_progress=not args.no_progress)
            if args.serve:
                server.serve(cfg, log=log)
            return 0 if stats.alive else 2
        if args.cmd == "collect":
            return cmd_collect(cfg, args, log)
        if args.cmd == "publish":
            return cmd_publish(cfg, args, log)
        if args.cmd == "serve":
            server.serve(cfg, log=log)
            return 0
        if args.cmd == "stats":
            return cmd_stats(cfg, log)
        if args.cmd == "reset":
            return cmd_reset(cfg, args, log)
    except KeyboardInterrupt:
        log("\n已中断。")
        return 130
    except FileNotFoundError as exc:
        log(f"错误：{exc}")
        return 1
    return 1
