"""局域网 HTTP 服务：让电视 / PotPlayer 用 http://电脑IP:8899/live.m3u 订阅。"""

from __future__ import annotations

import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def lan_ips() -> list[str]:
    ips: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    return sorted(ips)


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        # 播放器会缓存 m3u，必须禁掉，否则更新了 TV 也看不到
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - 基类签名如此
        if self.path in ("/", "/index.html"):
            return
        super().log_message(fmt, *args)


def make_server(cfg) -> ThreadingHTTPServer:
    out = Path(cfg.output.get("dir") or "output")
    if not out.is_absolute():
        out = Path(cfg._root) / out
    out.mkdir(parents=True, exist_ok=True)

    host = cfg.server.get("host") or "0.0.0.0"
    port = int(cfg.server.get("port") or 8899)

    handler = partial(Handler, directory=str(out))
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    return httpd


def serve(cfg, refresh=None, log=print) -> None:
    """启动局域网服务。refresh 为可选的回调（用于 /refresh 触发重新检测）。"""
    out = Path(cfg.output.get("dir") or "output")
    if not out.is_absolute():
        out = Path(cfg._root) / out

    httpd = make_server(cfg)
    port = httpd.server_address[1]

    log("")
    log("=" * 62)
    log("  局域网服务已启动（Ctrl+C 停止）")
    log("=" * 62)
    log(f"  输出目录 : {out}")
    log("")
    log("  PotPlayer / 本机测试：")
    log(f"    订阅地址 : http://127.0.0.1:{port}/live.m3u")
    log(f"    纯链接列表: http://127.0.0.1:{port}/live.txt")
    log(f"    网页面板 : http://127.0.0.1:{port}/")
    log("")
    for ip in lan_ips():
        log("  安卓 TV / 手机（同一局域网）：")
        log(f"    订阅地址 : http://{ip}:{port}/live.m3u")
    log("")
    log("  TiviMate / OTT Navigator：添加播放列表 → 输入上面的订阅地址")
    log("=" * 62)
    log("")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("\n已停止服务。")
    finally:
        httpd.server_close()


def serve_background(cfg) -> threading.Thread:
    """后台线程方式启动，便于和其他任务共存。"""
    httpd = make_server(cfg)

    def _run() -> None:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

    t = threading.Thread(target=_run, daemon=True, name="iptv-http")
    t.start()
    return t
