"""发布层：把验证通过的流渲染成 M3U / TXT / 报告 / 索引页。"""

from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .models import RunStats, Stream


def _order_map(cfg) -> dict[str, int]:
    order = list(cfg.get("output_order") or [])
    return {name: i for i, name in enumerate(order)}


def sort_key_factory(cfg):
    order = _order_map(cfg)
    big = len(order) + 1
    return lambda st: (order.get(st.category, big), st.key, -st.score)


def group_by_channel(streams: list[Stream]) -> dict[str, list[Stream]]:
    groups: dict[str, list[Stream]] = defaultdict(list)
    for st in streams:
        groups[st.key].append(st)
    for items in groups.values():
        items.sort(key=lambda s: -s.score)
    return groups


def select_published(streams: list[Stream], cfg) -> list[Stream]:
    """每个频道保留 score 最高的前 N 条，作为备用线路。"""
    max_per = int(cfg.output.get("max_per_channel") or 3)
    groups = group_by_channel(streams)
    out: list[Stream] = []
    for items in groups.values():
        out.extend(items[:max_per] if max_per > 0 else items)
    out.sort(key=sort_key_factory(cfg))
    return out


def _esc(value: str) -> str:
    return (value or "").replace('"', "'").replace("\n", " ").replace("\r", " ").strip()


def render_m3u(streams: list[Stream], cfg, epg_url: str = "") -> str:
    lines = ["#EXTM3U"]
    if epg_url:
        lines[0] = f'#EXTM3U x-tvg-url="{_esc(epg_url)}"'
    for st in streams:
        attrs = [f'tvg-name="{_esc(st.display or st.name)}"']
        if st.tvg_id:
            attrs.append(f'tvg-id="{_esc(st.tvg_id)}"')
        if st.tvg_logo:
            attrs.append(f'tvg-logo="{_esc(st.tvg_logo)}"')
        if st.category:
            attrs.insert(0, f'group-title="{_esc(st.category)}"')
        lines.append(f"#EXTINF:-1 {' '.join(attrs)},{_esc(st.display or st.name)}")
        if st.referrer:
            lines.append(f"#EXTVLCOPT:http-referrer={st.referrer}")
        if st.user_agent:
            lines.append(f"#EXTVLCOPT:http-user-agent={st.user_agent}")
        lines.append(st.url)
    return "\n".join(lines) + "\n"


def _report_md(stats: RunStats, streams: list[Stream], cfg) -> str:
    groups = group_by_channel(streams)
    order = _order_map(cfg)
    by_cat: dict[str, int] = defaultdict(int)
    for st in streams:
        by_cat[st.category] += 1

    lines = [
        "# IPTV 直播源检测报告",
        "",
        f"- 运行时间：{stats.started_at} → {stats.finished_at}（{stats.elapsed_sec:.1f} 秒）",
        f"- 解析到流：**{stats.total_parsed}** 条",
        f"- 筛选后：{stats.after_filter} 条，去重后：{stats.after_dedup} 条",
        f"- 实际探测：{stats.probed} 条（拉黑跳过 {stats.skipped_blacklist} 条）",
        f"- 可用：**{stats.alive}** 条（{stats.alive_rate:.1f}%），失效：{stats.dead} 条",
        f"- 频道数：{stats.channels}，发布：{stats.published_channels} 个频道 / "
        f"{stats.published_streams} 条线路",
        "",
        "## 流类型分布",
        "",
    ]
    for kind, cnt in sorted(stats.kind_breakdown.items(), key=lambda kv: -kv[1]):
        lines.append(f"- `{kind}`：{cnt}")

    lines += ["", "## 分组统计", "", "| 分组 | 可用线路 | 频道数 |", "|---|---|---|"]
    cat_channels: dict[str, int] = defaultdict(int)
    for key, items in groups.items():
        cat_channels[items[0].category] += 1
    for cat in sorted(cat_channels, key=lambda c: order.get(c, 999)):
        lines.append(f"| {cat} | {by_cat.get(cat, 0)} | {cat_channels[cat]} |")

    lines += ["", "## 采集源", "", "| 源 | 条数 | 状态 |", "|---|---|---|"]
    for s in stats.sources:
        status = f"失败：{s.error}" if s.error else "正常"
        lines.append(f"| {s.name} | {s.parsed} | {status} |")

    top = sorted(streams, key=lambda s: -s.score)[:30]
    lines += ["", "## 质量最高的 30 条线路", "",
              "| 频道 | 分组 | 类型 | 分辨率 | 延迟 | 评分 |", "|---|---|---|---|---|---|"]
    for st in top:
        lines.append(
            f"| {st.display} | {st.category} | {st.kind} | {st.resolution or '-'} | "
            f"{st.latency_ms:.0f}ms | {st.score:.0f} |"
        )

    lines += ["", f"> 由 iptv-pipeline 自动生成 {stats.finished_at}", ""]
    return "\n".join(lines)


def _index_html(stats: RunStats, streams: list[Stream], files: dict[str, str], cfg) -> str:
    groups = group_by_channel(streams)
    order = _order_map(cfg)
    rows = []
    for key in sorted(groups, key=lambda k: (order.get(groups[k][0].category, 99), k)):
        items = groups[key]
        best = items[0]
        rows.append(
            "<tr>"
            f"<td>{html.escape(best.category)}</td>"
            f"<td><b>{html.escape(best.display)}</b></td>"
            f"<td>{len(items)}</td>"
            f"<td>{html.escape(best.kind)}</td>"
            f"<td>{html.escape(best.resolution or '-')}</td>"
            f"<td>{best.latency_ms:.0f} ms</td>"
            f"<td class='u'><a href='{html.escape(best.url)}' target='_blank'>测试</a></td>"
            "</tr>"
        )

    links = " · ".join(
        f"<a href='{html.escape(f)}'>{html.escape(f)}</a>" for f in files.values()
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IPTV 直播源</title>
<style>
 body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;margin:0;padding:24px;
      background:#0f1115;color:#e6e6e6}}
 h1{{font-size:20px;margin:0 0 12px}}
 .card{{background:#171a21;border:1px solid #262b36;border-radius:10px;
        padding:16px;margin-bottom:16px}}
 .kpi{{display:flex;gap:28px;flex-wrap:wrap}}
 .kpi div{{font-size:13px;color:#9aa4b2}}
 .kpi b{{display:block;font-size:22px;color:#4ea1ff;margin-top:4px}}
 table{{width:100%;border-collapse:collapse;font-size:13px}}
 th,td{{padding:7px 10px;border-bottom:1px solid #232833;text-align:left}}
 th{{color:#8b94a3;font-weight:500;position:sticky;top:0;background:#171a21}}
 a{{color:#4ea1ff;text-decoration:none}} a:hover{{text-decoration:underline}}
 .u{{white-space:nowrap}}
 .wrap{{max-height:70vh;overflow:auto;border-radius:8px}}
 code{{background:#0b0d11;padding:2px 6px;border-radius:4px;color:#7ee787}}
</style></head><body>
<h1>📺 IPTV 直播源</h1>
<div class="card">
  <div class="kpi">
    <div>可用频道<b>{stats.channels}</b></div>
    <div>可用线路<b>{stats.alive}</b></div>
    <div>存活率<b>{stats.alive_rate:.1f}%</b></div>
    <div>探测总数<b>{stats.probed}</b></div>
    <div>耗时<b>{stats.elapsed_sec:.0f}s</b></div>
  </div>
  <p style="color:#9aa4b2;font-size:13px">更新时间：{stats.finished_at}</p>
  <p style="font-size:13px">订阅地址：<code>live.m3u</code>　其他文件：{links}</p>
</div>
<div class="card"><div class="wrap"><table>
<thead><tr><th>分组</th><th>频道</th><th>线路</th><th>类型</th><th>分辨率</th>
<th>延迟</th><th>直连测试</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div></div>
</body></html>
"""


def write_outputs(streams: list[Stream], cfg, stats: RunStats) -> dict[str, Path]:
    out_dir = Path(cfg.output.get("dir") or "output")
    if not out_dir.is_absolute():
        out_dir = Path(cfg._root) / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    epg_url = cfg.output.get("epg_url") or ""
    main_streams = select_published(streams, cfg)

    max_channels = int(cfg.output.get("max_channels") or 0)
    if max_channels > 0:
        seen_keys: list[str] = []
        for st in main_streams:
            if st.key not in seen_keys:
                seen_keys.append(st.key)
        keep = set(seen_keys[:max_channels])
        main_streams = [s for s in main_streams if s.key in keep]

    written: dict[str, Path] = {}

    main_path = out_dir / (cfg.output.get("main") or "live.m3u")
    main_path.write_text(render_m3u(main_streams, cfg, epg_url), encoding="utf-8")
    written["main"] = main_path

    full_path = out_dir / (cfg.output.get("full") or "live_full.m3u")
    full_path.write_text(render_m3u(streams, cfg, epg_url), encoding="utf-8")
    written["full"] = full_path

    txt_path = out_dir / (cfg.output.get("text") or "live.txt")
    txt_path.write_text("\n".join(s.url for s in streams) + "\n", encoding="utf-8")
    written["text"] = txt_path

    stats.published_channels = len({s.key for s in main_streams})
    stats.published_streams = len(main_streams)

    report_path = out_dir / (cfg.output.get("report") or "report.md")
    report_path.write_text(_report_md(stats, streams, cfg), encoding="utf-8")
    written["report"] = report_path

    index_path = out_dir / (cfg.output.get("index") or "index.html")
    index_path.write_text(
        _index_html(stats, streams, {k: v.name for k, v in written.items()}, cfg),
        encoding="utf-8",
    )
    written["index"] = index_path

    # 运行快照，便于排查
    snapshot = out_dir / "stats.json"
    snapshot.write_text(
        json.dumps(stats.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    written["stats"] = snapshot

    return written
