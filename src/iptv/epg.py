"""EPG（节目单）获取。

为什么要自己下回来再发布：
    原来直接让播放器去拉 `https://live.fanmingming.cn/e.xml`，但这个域名
    实测已经连不上（ConnectTimeout，可能改了域名或遭 DNS 污染）。
    播放器那边表现就是「节目单加载失败」。

    既然我们本来就把 live.m3u 发到 GitHub Pages，那就顺手把 EPG 也下回来一起发布，
    播放器直接从**自己的域名**取：
        https://<用户名>.github.io/<仓库名>/e.xml
    好处是：域名是我们已知可达的（*.github.io），不依赖第三方站点的存活，
    而且每轮自动更新，节目单不会变旧。

    原始 EPG 来自 fanmingming/live，它的 channel id 与我们生成的 tvg-id 对齐
    （见 normalize.epg_id），所以央视和卫视能匹配上，不需要额外做 id 映射。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

EPG_FILE = "e.xml"
# XMLTV 至少要像这么回事，否则说明下到的是错误页
_MIN_BYTES = 100_000
_HINTS = (b"<tv", b"<?xml")


def _looks_like_epg(data: bytes) -> bool:
    head = data[:4096]
    return len(data) >= _MIN_BYTES and any(h in head for h in _HINTS)


async def fetch_epg(cfg, out_dir: Path, log=print) -> Path | None:
    """把 EPG 下到 out_dir/e.xml。成功返回路径，失败返回 None（保留旧文件）。"""
    if not cfg.output.get("epg_self_host", True):
        return None

    mirrors = [str(u) for u in (cfg.output.get("epg_mirrors") or []) if str(u).strip()]
    if not mirrors:
        return None

    target = out_dir / EPG_FILE
    old = b""
    if target.exists():
        try:
            old = target.read_bytes()
        except OSError:
            old = b""

    headers = {"User-Agent": cfg.network.get("user_agent") or "Mozilla/5.0"}
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0), follow_redirects=True, verify=False
    ) as client:
        for url in mirrors:
            try:
                r = await client.get(url, headers=headers)
                if r.status_code >= 400:
                    log(f"      EPG 镜像 HTTP {r.status_code}：{url[:70]}")
                    continue
                data = r.content
            except Exception as exc:  # noqa: BLE001 - 单个镜像失败换下一个
                log(f"      EPG 镜像失败 {type(exc).__name__}：{url[:70]}")
                continue

            if not _looks_like_epg(data):
                log(f"      EPG 内容不对（{len(data)}B）：{url[:70]}")
                continue

            if old and hashlib.md5(data).digest() == hashlib.md5(old).digest():
                log(f"      EPG 未变化（{len(data) / 1048576:.1f}MB）")
                return target

            try:
                target.write_bytes(data)
            except OSError as exc:
                log(f"      EPG 写入失败：{exc}")
                return None
            log(f"      EPG 已更新：{len(data) / 1048576:.1f}MB -> {target.name}")
            return target

    if target.exists():
        log("      EPG 所有镜像都失败，沿用上一次的副本")
        return target
    log("      EPG 获取失败，播放器将没有节目单（可改 output.epg_url）")
    return None
