"""流水线编排：采集 → 筛选 → 归一化 → 探测 → 剔除 → 发布。"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import collect, normalize, publish, validate
from .config import Dot, resolve
from .history import History, iso, now_utc
from .models import RunStats, Stream

NON_HTTP = {"rtmp", "rtsp", "rtp", "udp", "mms", "rtmpi"}


def _data_path(cfg: Dot, name: str) -> Path:
    p = resolve(cfg, "history", "path")
    return p.parent / name


def save_streams(streams: list[Stream], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([s.to_dict() for s in streams], ensure_ascii=False), encoding="utf-8"
    )


def load_streams(path: Path) -> list[Stream]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [Stream.from_dict(d) for d in data]


def build_history(cfg: Dot) -> History:
    h = History(
        path=resolve(cfg, "history", "path"),
        blacklist_after=cfg.history.get("blacklist_after") or 4,
        blacklist_hours=cfg.history.get("blacklist_hours") or 72,
        keep_days=cfg.history.get("keep_days") or 60,
    )
    return h.load()


def _priority_map(cfg: Dot) -> dict[str, int]:
    order = list(cfg.get("output_order") or [])
    return {name: i for i, name in enumerate(order)}


def cap_candidates(
    streams: list[Stream], cfg: Dot, history: History
) -> list[Stream]:
    """按「分组优先级 + 历史稳定度」排序后截断，保证优先探测重要的频道。"""
    max_probe = int(cfg.network.get("max_probe") or 0)
    if max_probe <= 0 or len(streams) <= max_probe:
        return streams

    order = _priority_map(cfg)
    big = len(order) + 1

    def rank(st: Stream) -> tuple:
        ent = history.get(st.url)
        ok = int(ent.get("ok_count", 0))
        last_ok = ent.get("last_ok", "")
        return (order.get(st.category, big), -ok, last_ok == "", st.key)

    ranked = sorted(streams, key=rank)
    return ranked[:max_probe]


async def run_pipeline(
    cfg: Dot, log=print, show_progress: bool = True, force: bool = False
) -> RunStats:
    started = now_utc()
    stats = RunStats(started_at=iso(started))
    t_begin = time.perf_counter()

    # ---------- 1. 采集 ----------
    log("[1/6] 采集公开源 ...")
    raw, source_stats = await collect.collect_all(cfg, on_progress=log)
    stats.sources = source_stats
    stats.total_parsed = len(raw)
    log(f"      共解析 {len(raw)} 条原始流")

    if not raw:
        log("      没有采集到任何数据，请检查网络或 config.yaml 里的 sources。")
        stats.finished_at = iso(now_utc())
        stats.elapsed_sec = time.perf_counter() - t_begin
        return stats

    # ---------- 2. 筛选 ----------
    log("[2/6] 关键词筛选 ...")
    modes = normalize.source_modes(cfg)
    kept = [s for s in raw if normalize.matches_filter(s, cfg, modes)]
    stats.after_filter = len(kept)
    log(f"      命中 {len(kept)} 条（过滤掉 {len(raw) - len(kept)} 条）")

    if not kept:
        log("      筛选后没有剩余频道，可把 filter.mode 改成 all 试试。")
        stats.finished_at = iso(now_utc())
        stats.elapsed_sec = time.perf_counter() - t_begin
        return stats

    # ---------- 3. 归一化 + 去重 ----------
    log("[3/6] 频道名归一化 / 去重 ...")
    normalize.normalize(kept, cfg)
    deduped = normalize.dedupe(kept)
    stats.after_dedup = len(deduped)
    log(f"      去重后 {len(deduped)} 条，覆盖 {len({s.key for s in deduped})} 个频道")

    # ---------- 4. 准备探测 ----------
    history = build_history(cfg)
    candidates: list[Stream] = []
    skipped_scheme = 0
    for st in deduped:
        if validate.scheme_of(st.url) in NON_HTTP:
            skipped_scheme += 1
            continue
        history.apply(st)
        candidates.append(st)

    if skipped_scheme:
        log(f"      跳过 {skipped_scheme} 条非 HTTP 协议流（rtmp/rtsp/udp 等）")

    candidates = cap_candidates(candidates, cfg, history)
    log(f"[4/6] 探测 {len(candidates)} 条流（并发 {cfg.network.get('concurrency')}）...")

    last = {"done": 0}

    def progress(done: int, total: int, alive: int, phase: str = "") -> None:
        last["done"] = done
        if show_progress:
            pct = done / total * 100 if total else 100
            bar_len = 24
            filled = int(bar_len * done / total) if total else bar_len
            bar = "#" * filled + "-" * (bar_len - filled)
            tag = f" {phase}" if phase else ""
            log(f"      [{bar}] {pct:5.1f}%  {done}/{total}  可用 {alive}{tag}")

    await validate.probe_all(candidates, cfg, history, on_progress=progress)
    stats.probed = len(candidates)
    stats.skipped_blacklist = sum(1 for s in candidates if s.skipped)
    stats.alive = sum(1 for s in candidates if s.ok)
    stats.dead = stats.probed - stats.alive - stats.skipped_blacklist
    if stats.dead < 0:
        stats.dead = 0

    breakdown: dict[str, int] = {}
    for st in candidates:
        if st.ok:
            breakdown[st.kind] = breakdown.get(st.kind, 0) + 1
    stats.kind_breakdown = breakdown
    stats.channels = len({s.key for s in candidates if s.ok})

    log(f"      可用 {stats.alive} 条 / 失效 {stats.dead} 条 / 拉黑跳过 {stats.skipped_blacklist} 条")

    # ---------- 5. 保存历史（这就是「自动剔除」的依据）----------
    pruned = history.prune()
    history.save()
    hstats = history.stats()
    log(
        f"[5/6] 历史库已更新：跟踪 {hstats['tracked']} 条，"
        f"当前拉黑 {hstats['blacklisted']} 条，清理过期 {pruned} 条"
    )

    # 中间产物，便于排查
    try:
        save_streams(deduped, _data_path(cfg, "raw.json"))
        save_streams(candidates, _data_path(cfg, "probed.json"))
    except OSError as exc:
        log(f"      中间文件写入失败（忽略）：{exc}")

    # ---------- 6. 发布 ----------
    alive = [s for s in candidates if s.ok]
    stats.finished_at = iso(now_utc())
    stats.elapsed_sec = time.perf_counter() - t_begin

    log("[6/6] 生成输出文件 ...")
    if alive:
        try:
            written = publish.write_outputs(alive, cfg, stats, force=force)
        except publish.OutputRegression as exc:
            log(f"      [保留旧文件] {exc}")
            log("             为免把电视上的好列表冲掉，本次不覆盖输出。")
            log("             确认要写入请加 --force 重跑。")
        else:
            for key, path in written.items():
                log(f"      {key:<7} -> {path}")
    else:
        log("      没有任何可用流，未生成播放列表（保留上一版文件）。")

    last_run = _data_path(cfg, "last_run.json")
    last_run.parent.mkdir(parents=True, exist_ok=True)
    last_run.write_text(
        json.dumps(stats.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
    )

    log("")
    log(f"完成：{stats.published_channels} 个频道 / {stats.published_streams} 条线路，"
        f"耗时 {stats.elapsed_sec:.1f} 秒")
    return stats


def run_sync(
    cfg: Dot, log=print, show_progress: bool = True, force: bool = False
) -> RunStats:
    return asyncio.run(run_pipeline(cfg, log=log, show_progress=show_progress, force=force))
