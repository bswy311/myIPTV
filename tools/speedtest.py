"""量一下本机真实下行带宽，用来决定 validate.bw_concurrency 该设多少。

为什么要这个工具：
    带宽测速阶段是并发下载的。如果并发数 × 单条流码率超过了本机带宽上限，
    等于自己把自己挤死，测出来每个源都「带宽不足」——结论全是错的。
    所以调 bw_concurrency 之前，先知道自己这条线有多宽。

用法：
    python tools/speedtest.py            # 默认测 3 次取最快
    python tools/speedtest.py -n 5
    python tools/speedtest.py -p 6       # 6 路并发，看聚合速度（判断链路真实上限）
"""

from __future__ import annotations

import argparse
import asyncio
import time

import httpx

# 挑几个不同线路的大文件，谁通就用谁（本机网络对域名很挑，多备几个）
TARGETS = [
    ("Cloudflare", "https://speed.cloudflare.com/__down?bytes=26214400"),
    ("CacheFly", "https://cachefly.cachefly.net/25mb.test"),
    ("阿里云镜像", "https://mirrors.aliyun.com/ubuntu/ls-lR.gz"),
    ("腾讯云镜像", "https://mirrors.cloud.tencent.com/ubuntu/ls-lR.gz"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}

MAX_BYTES = 25 * 1024 * 1024
MIN_BYTES = 2 * 1024 * 1024
HARD_LIMIT = 15.0  # 单次最多测 15 秒，免得在慢节点上干等


async def one(client: httpx.AsyncClient, name: str, url: str) -> float:
    """返回 Mbps，失败返回 0。"""
    n = 0
    t0 = time.perf_counter()
    try:
        async with client.stream("GET", url, headers=HEADERS) as resp:
            if resp.status_code >= 400:
                print(f"  [x] {name:<12} HTTP {resp.status_code}")
                return 0.0
            async for chunk in resp.aiter_bytes(65536):
                n += len(chunk)
                el = time.perf_counter() - t0
                if n >= MAX_BYTES or el > HARD_LIMIT:
                    break
    except Exception as exc:  # noqa: BLE001 - 测速失败不是错误，换下一个
        print(f"  [x] {name:<12} {type(exc).__name__}")
        return 0.0

    el = max(time.perf_counter() - t0, 1e-6)
    if n < MIN_BYTES:
        print(f"  [x] {name:<12} 只拿到 {n / 1024:.0f} KB，样本太小")
        return 0.0

    mbps = n * 8.0 / el / 1e6
    print(f"  [v] {name:<12} {n / 1048576:6.1f} MB / {el:5.2f}s = {mbps:8.1f} Mbps")
    return mbps


async def parallel(client: httpx.AsyncClient, name: str, url: str, n_streams: int) -> float:
    """同一条 URL 开 n 路并发，返回聚合 Mbps。

    单流跑 87 Mbps 不代表链路只有 87 Mbps——很可能是对面服务器限速。
    多流聚合才能看出本机链路的真实天花板，而这个数字才决定 bw_concurrency。
    """
    got = [0] * n_streams
    t0 = time.perf_counter()

    async def worker(idx: int) -> None:
        try:
            async with client.stream("GET", url, headers=HEADERS) as resp:
                if resp.status_code >= 400:
                    return
                async for chunk in resp.aiter_bytes(65536):
                    got[idx] += len(chunk)
                    if time.perf_counter() - t0 > HARD_LIMIT:
                        break
        except Exception:  # noqa: BLE001
            return

    await asyncio.gather(*(worker(i) for i in range(n_streams)))
    el = max(time.perf_counter() - t0, 1e-6)
    total = sum(got)
    if total < MIN_BYTES:
        print(f"  [x] {name:<12} {n_streams} 路聚合只拿到 {total / 1024:.0f} KB")
        return 0.0
    mbps = total * 8.0 / el / 1e6
    print(f"  [v] {name:<12} {n_streams} 路聚合 {total / 1048576:6.1f} MB / {el:5.2f}s"
          f" = {mbps:8.1f} Mbps")
    return mbps


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--rounds", type=int, default=3, help="每个源测几轮")
    ap.add_argument("-p", "--parallel", type=int, default=0,
                    help="并发路数；>0 时改为测聚合速度，判断链路真实上限")
    args = ap.parse_args()

    if args.parallel > 0:
        print(f"本机下行带宽实测（同一源 {args.parallel} 路并发，看聚合上限）\n")
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=6.0),
            follow_redirects=True,
            verify=False,
        ) as client:
            results = await asyncio.gather(
                *(parallel(client, n, u, args.parallel) for n, u in TARGETS)
            )
        best_agg = max(results, default=0.0)
        print()
        if best_agg <= 0:
            print("全部失败，跳过。")
            return
        print(f"链路聚合上限大约：{best_agg:.0f} Mbps")
        print(f"建议 bw_concurrency: {max(4, min(32, int(best_agg / 12)))}"
              f"  （按「留 4 倍余量、单流平均 3 Mbps」估）")
        return

    print("本机下行带宽实测（多源取最快值）\n")
    best = 0.0
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=6.0),
            follow_redirects=True,
            verify=False,
        ) as client:
            for rnd in range(args.rounds):
                print(f"第 {rnd + 1} 轮：")
                results = await asyncio.gather(
                    *(one(client, n, u) for n, u in TARGETS)
                )
                best = max(best, *results)
                if round(best, 1) <= 0:
                    continue
    except KeyboardInterrupt:
        pass

    print()
    if best <= 0:
        print("全部目标都连不上。本机网络对境外/公共测速站拦截严重，")
        print("可以直接跳过这步：把 config.yaml 里的 bw_concurrency 调到 8 就够安全了。")
        return

    print(f"本机下行大约：{best:.0f} Mbps")
    print()
    print("建议的 bw_concurrency（按「单条流平均 3 Mbps」留 3 倍余量）：")
    for label, mbps in [
        ("20M 宽带", 20),
        ("50M 宽带", 50),
        ("100M 宽带", 100),
        ("200M 宽带", 200),
        ("500M 宽带", 500),
        ("1000M 宽带", 1000),
    ]:
        if best >= mbps * 0.75:
            print(f"  {label:<12} -> bw_concurrency: {max(4, int(mbps / 9))}")
    print()
    print(f"  （按实测 {best:.0f} Mbps 算）-> bw_concurrency: "
          f"{max(4, int(best / 9))}，上限建议不超过 32")


if __name__ == "__main__":
    asyncio.run(main())
