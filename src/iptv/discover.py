"""源发现：每次运行自动搜一遍全网，找出新的可用高质量源。

为什么要这一层：
    公开源的寿命很短，手工维护的列表过几个月就会大面积失效，
    而新的好源又会不断冒出来。与其等人去更新配置，不如让程序每次运行都自己找。

工作方式（关键点：**测完立刻就用**，不用等下一轮）：
    1. 候选来源分两路
       - 手工注册表 `config/source_registry.yaml`（稳定、可控）
       - GitHub 搜索最近还在更新的 IPTV 仓库，再列出它们仓库里的 .m3u 文件
    2. 逐个拉取解析，统计两个指标
       - hits        通过关键词筛选的条数
       - new_channels 相对本次基础源**新覆盖**的频道数（这才是真正的价值）
    3. 达到 `min_new_channels` 的候选，流**当场并入本轮**，不用等下次
    4. 连续 `promote_after` 次达标 → 写进 `data/source_stats.json` 标记常驻，
       以后每轮直接采集；连续 `demote_after` 次没价值/拉不动 → 自动停用

这样「6 小时自动更新」就同时具备了自动换血的能力：坏的源会被淘汰，
新出现的好源会被自动吸收。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from . import collect, normalize
from .models import Stream

STATS_NAME = "source_stats.json"
REGISTRY_DEFAULT = "config/source_registry.yaml"

GITHUB_API = "https://api.github.com"
M3U_SUFFIXES = (".m3u", ".m3u8")
# 明显不是直播列表的文件（播放器配置、示例等）
SKIP_HINTS = ("sample", "example", "demo", "backup", "old", "test")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> datetime:
    return datetime.now(timezone.utc)


def stats_path(cfg) -> Path:
    h = Path(cfg._root) / (cfg.history.get("path") or "data/history.json")
    return h.parent / STATS_NAME


def load_stats(cfg) -> dict:
    p = stats_path(cfg)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_stats(cfg, stats: dict) -> None:
    p = stats_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    # 只留最近 200 条，避免文件无限膨胀
    if len(stats) > 200:
        ordered = sorted(stats.items(),
                         key=lambda kv: kv[1].get("last_seen", ""), reverse=True)
        stats = dict(ordered[:200])
    p.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------
# 候选收集
# ---------------------------------------------------------------
def registry_candidates(cfg) -> list[dict]:
    """读手工注册表。"""
    rel = cfg.discover.get("registry") or REGISTRY_DEFAULT
    p = Path(rel)
    if not p.is_absolute():
        p = Path(cfg._root) / p
    if not p.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 - 注册表坏了不该影响主流程
        return []

    out: list[dict] = []
    for item in data.get("candidates") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        out.append({
            "name": str(item.get("name") or url)[:40],
            "url": url,
            "filter": str(item.get("filter") or "include"),
            "origin": "registry",
        })
    return out


def _auth_headers(cfg) -> dict[str, str]:
    token = (cfg.discover.get("github_token")
             or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "")
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


async def github_candidates(cfg, on_progress=None) -> list[dict]:
    """搜 GitHub 上最近还在更新的 IPTV 仓库，列出仓库里的 .m3u 文件。

    用「仓库 → 文件树」而不是猜路径：先 git/trees?recursive=1 拿到全部文件，
    再挑体积最大的几个 .m3u，比盲猜 `tv/xxx.m3u` 靠谱得多。
    没有 token 也能跑，只是速率限制低（60 次/小时），失败就静默跳过。
    """
    if not cfg.discover.get("github_search", True):
        return []

    days = int(cfg.discover.get("github_pushed_within_days") or 30)
    since = (_today() - timedelta(days=days)).strftime("%Y-%m-%d")
    queries = cfg.discover.get("github_queries") or ["iptv in:name,description"]
    max_repos = int(cfg.discover.get("github_repos") or 10)
    per_repo = int(cfg.discover.get("files_per_repo") or 2)

    headers = _auth_headers(cfg)
    found: list[dict] = []
    seen_repos: set[str] = set()

    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(headers=headers, timeout=timeout,
                                 follow_redirects=True) as client:
        for q in queries:
            if len(seen_repos) >= max_repos:
                break
            try:
                r = await client.get(f"{GITHUB_API}/search/repositories", params={
                    "q": f"{q} pushed:>{since}",
                    "sort": "updated",
                    "order": "desc",
                    "per_page": max_repos,
                })
                if r.status_code != 200:
                    if on_progress:
                        on_progress(f"      GitHub 搜索返回 {r.status_code}，跳过")
                    continue
                repos = r.json().get("items") or []
            except Exception as exc:  # noqa: BLE001
                if on_progress:
                    on_progress(f"      GitHub 搜索失败：{type(exc).__name__}")
                continue

            for repo in repos:
                full = str(repo.get("full_name") or "")
                if not full or full in seen_repos:
                    continue
                seen_repos.add(full)
                # 一天更新的仓库更容易包含可用的新源
                branch = str(repo.get("default_branch") or "HEAD")
                try:
                    tr = await client.get(
                        f"{GITHUB_API}/repos/{full}/git/trees/{branch}",
                        params={"recursive": "1"},
                    )
                    if tr.status_code != 200:
                        continue
                    tree = tr.json().get("tree") or []
                except Exception:  # noqa: BLE001
                    continue

                files = []
                for node in tree:
                    path = str(node.get("path") or "")
                    low = path.lower()
                    if node.get("type") != "blob" or not low.endswith(M3U_SUFFIXES):
                        continue
                    if any(h in low for h in SKIP_HINTS):
                        continue
                    files.append((int(node.get("size") or 0), path))
                files.sort(reverse=True)
                for size, path in files[:per_repo]:
                    # 太小的多半是单个频道或占位文件
                    if size < 2000:
                        continue
                    found.append({
                        "name": f"gh:{full.split('/')[-1]}"[:40],
                        "url": f"https://raw.githubusercontent.com/{full}/{branch}/{path}",
                        "filter": "include",
                        "origin": "github",
                    })
                if len(seen_repos) >= max_repos:
                    break

    return found


# ---------------------------------------------------------------
# 评估
# ---------------------------------------------------------------
async def _evaluate_one(client, cand: dict, cfg, timeout: float) -> dict:
    """拉一个候选源，统计条数与频道键。"""
    res = {"url": cand["url"], "name": cand["name"], "origin": cand.get("origin", ""),
           "parsed": 0, "hits": 0, "keys": set(), "error": ""}
    try:
        text, stat, base_dir = await collect.fetch_text(client, cand, timeout)
        if not text:
            res["error"] = stat.error[:120] or "空响应"
            return res
        streams = collect.parse_content(text, cand["name"], base_dir)
        res["parsed"] = len(streams)
    except Exception as exc:  # noqa: BLE001
        res["error"] = f"{type(exc).__name__}: {str(exc)[:90]}"
        return res

    modes = {cand["name"]: cand.get("filter") or "include"}
    kept = [s for s in streams if normalize.matches_filter(s, cfg, modes)]
    res["hits"] = len(kept)
    res["keys"] = {normalize.canonical_key(s.name or s.tvg_name) for s in kept}
    res["keys"].discard("")
    res["streams"] = kept
    return res


async def discover(cfg, base_streams: list[Stream], log=print) -> tuple[list[Stream], list[dict]]:
    """跑一轮源发现。返回 (要并入本轮的流, 每候选的评估结果)。"""
    if not cfg.discover.get("enabled", True):
        return [], []

    max_cands = int(cfg.discover.get("max_candidates") or 40)
    conc = max(1, int(cfg.discover.get("concurrency") or 8))
    timeout = float(cfg.discover.get("timeout") or 12)
    min_new = int(cfg.discover.get("min_new_channels") or 3)
    max_new = int(cfg.discover.get("max_new_channels") or 0)
    max_merge = int(cfg.discover.get("max_merge_per_source") or 0)
    min_rate = float(cfg.discover.get("min_hit_rate") or 0.0)
    promote_after = int(cfg.discover.get("promote_after") or 2)
    demote_after = int(cfg.discover.get("demote_after") or 3)
    auto_enable = bool(cfg.discover.get("auto_enable", True))

    stats = load_stats(cfg)

    # 已经在手工 sources 里的不必再测
    configured = {str(s.get("url") or "") for s in (cfg.sources or [])}
    cands: list[dict] = []
    seen: set[str] = set()
    for c in registry_candidates(cfg) + await github_candidates(cfg, log):
        u = c["url"]
        if u in configured or u in seen:
            continue
        seen.add(u)
        cands.append(c)
        if len(cands) >= max_cands:
            break

    if not cands:
        log("      没有待测候选源")
        return [], []

    log(f"      候选源 {len(cands)} 个，开始测试 ...")

    base_urls = {s.url for s in base_streams}
    base_keys = {s.key for s in base_streams if s.key}

    headers = {"User-Agent": cfg.network.get("user_agent") or "Mozilla/5.0"}
    sem = asyncio.Semaphore(conc)
    results: list[dict] = []

    async with httpx.AsyncClient(headers=headers,
                                 timeout=httpx.Timeout(timeout, connect=8.0),
                                 follow_redirects=True, verify=False) as client:
        async def worker(cand: dict) -> None:
            async with sem:
                results.append(await _evaluate_one(client, cand, cfg, timeout))

        await asyncio.gather(*(worker(c) for c in cands))

    merged: list[Stream] = []
    report: list[dict] = []
    cand_map = {c["url"]: c for c in cands}
    for res in sorted(results, key=lambda r: -r.get("hits", 0)):
        novel = res.get("keys", set()) - base_keys
        entry = stats.setdefault(res["url"], {})
        entry.setdefault("first_seen", _now())
        entry["name"] = res["name"]
        entry["origin"] = res.get("origin", "")
        entry["last_seen"] = _now()
        entry["runs"] = int(entry.get("runs", 0)) + 1
        entry["last_parsed"] = res["parsed"]
        entry["last_hits"] = res["hits"]
        entry["last_new_channels"] = len(novel)
        entry["error"] = res.get("error", "")

        # 命中率 = 通过筛选的条数 / 解析到的总条数。
        # 这是区分「对味的源」与「全量泛列表」的关键指标：
        # 一个 12525 条的全国家列表能凑出几百个“新频道”，但命中率只有 3%，
        # 收进来只会白白增加探测量和噪声。而专做中文频道的列表命中率能到 40%+。
        hit_rate = res["hits"] / max(res["parsed"], 1)
        entry["last_hit_rate"] = round(hit_rate, 3)

        # 两个门槛分开看：
        #   useful_now  值得**当轮并入**：新频道够多 + 命中率够高
        #   good        值得**长期常驻**：再加一条「不是巨型列表」
        # 为什么分开：像 19000 条、凑出 967 个新频道的巨型聚合列表，
        # 当轮取一部分（max_merge_per_source）是有用的，
        # 但如果设成常驻，每轮都要采它、列表会被冲垮。
        flood = bool(max_new) and len(novel) > max_new
        useful_now = (len(novel) >= min_new and res["hits"] > 0
                      and hit_rate >= min_rate)
        good = useful_now and not flood
        if good:
            entry["good_runs"] = int(entry.get("good_runs", 0)) + 1
            entry["fail_streak"] = 0
            entry["best_hits"] = max(int(entry.get("best_hits", 0)), res["hits"])
        else:
            entry["good_runs"] = 0
            entry["fail_streak"] = int(entry.get("fail_streak", 0)) + 1

        # 自动常驻 / 自动停用
        was = bool(entry.get("enabled", False))
        now_on = was
        if auto_enable:
            if int(entry["good_runs"]) >= promote_after:
                now_on = True
            elif int(entry["fail_streak"]) >= demote_after:
                now_on = False
        changed = now_on != was
        entry["enabled"] = now_on
        if auto_enable:
            # 记下完整定义，常驻后才能每轮直接采集
            entry["filter"] = cand_map.get(res["url"], {}).get("filter", "include")

        report.append({
            "name": res["name"], "url": res["url"], "origin": res.get("origin", ""),
            "parsed": res["parsed"], "hits": res["hits"], "new": len(novel),
            "rate": hit_rate, "flood": flood, "useful": useful_now,
            "error": res.get("error", ""), "enabled": now_on,
            "promoted": changed and now_on, "demoted": changed and not now_on,
        })

        # 有价值的当场就用上，不必等下一轮。单个源最多并入 max_merge 条，
        # 免得一个巨型列表直接把本轮探测量推高好几倍。
        if useful_now and res.get("streams"):
            fresh = [s for s in res["streams"] if s.url not in base_urls]
            if max_merge:
                fresh = sorted(fresh, key=lambda s: -len(s.name or ""))[:max_merge]
            for s in fresh:
                base_urls.add(s.url)
            merged.extend(fresh)

    save_stats(cfg, stats)

    promoted = [r for r in report if r["promoted"]]
    demoted = [r for r in report if r["demoted"]]
    useful = [r for r in report if r["new"] > 0]
    for r in useful[:8]:
        if r.get("flood"):
            flag = "  ← 巨型列表，只当轮取一部分，不设常驻"
        elif not r.get("useful"):
            flag = "  ← 命中率偏低，仅供参考"
        else:
            flag = ""
        log(f"        + {r['name']:<22} 解析 {r['parsed']:>5} 命中 {r['hits']:>4} "
            f"({r['rate']*100:>3.0f}%) 新频道 {r['new']:>4}{flag}")
    if promoted:
        for r in promoted:
            log(f"        [常驻] {r['name']} 已达标，以后每轮自动采集")
    if demoted:
        for r in demoted:
            log(f"        [停用] {r['name']} 连续无价值，已自动停用")
    log(f"      本轮新增 {len(merged)} 条流（来自 {len(useful)} 个候选源）")
    return merged, report


def extra_sources(cfg) -> list[dict]:
    """把已自动常驻的源转成采集源定义，供 collect_all 每轮直接使用。"""
    out: list[dict] = []
    for url, ent in load_stats(cfg).items():
        if not ent.get("enabled"):
            continue
        if str(url) in {str(s.get("url") or "") for s in (cfg.sources or [])}:
            continue
        out.append({
            "name": ent.get("name") or url,
            "url": url,
            "enabled": True,
            "filter": ent.get("filter") or "include",
        })
    return out
