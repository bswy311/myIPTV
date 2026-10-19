# IPTV 直播源检测报告

- 运行时间：2026-10-19T22:25:37+00:00 → 2026-10-19T22:33:16+00:00（459.4 秒）
- 解析到流：**12169** 条
- 筛选后：4709 条，去重后：3246 条
- 实际探测：3217 条（拉黑跳过 1498 条）
- 可用：**901** 条（28.0%），失效：818 条
- 频道数：177，发布：177 个频道 / 340 条线路

## 流类型分布

- `hls`：861
- `mp4`：27
- `ts`：7
- `flv`：4
- `dash`：2

## 带宽实测概览

- 平均下载速度：**21.1 Mbps**（最低 0.8，最高 585.4）
- 平均视频码率：**2.0 Mbps**
- 带宽余量 ≥2x（基本不会卡）：**289/319** 条（占 91%）

> 余量 = 实测速度 ÷ 视频码率。余量 <1 必定卡；1~2 勉强；>2 流畅。

## 分组统计

| 分组 | 可用线路 | 频道数 |
|---|---|---|
| 央视 | 597 | 65 |
| 卫视 | 142 | 16 |
| 吉林 | 7 | 6 |
| 长春 | 1 | 1 |
| 港澳台 | 94 | 51 |
| 国际新闻 | 41 | 20 |
| 其他 | 19 | 18 |

## 采集源

| 源 | 条数 | 状态 |
|---|---|---|
| local-extra | 1 | 正常 |
| bestfan-cctv | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_cctv.m3u8'
For more information check: https://developer.mo |
| bestfan-province | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_province.m3u8'
For more information check: https://develope |
| bestfan-all | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_all.m3u8'
For more information check: https://developer.moz |
| bestfan-all-direct | 91 | 正常 |
| vbskycn-ipv4 | 523 | 正常 |
| vbskycn-ipv4-gh | 523 | 正常 |
| chinaiptv-cntv | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV1_ALL.m3u8'
For more information check: https://developer. |
| iptv-org-sports | 481 | 正常 |
| iptv-org-cn | 147 | 正常 |
| iptv-org-hk | 17 | 正常 |
| iptv-org-tw | 28 | 正常 |
| iptv-org-zho | 215 | 正常 |
| iptv-org-news | 1018 | 正常 |
| suxuang-iptv | 1225 | 正常 |
| suxuang-iptv-gh | 0 | 失败：HTTPStatusError: Server error '502 Bad Gateway' for url 'https://ghproxy.net/https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u'
For more information check: https://developer.mozilla.org/e |
| gh:iptv-m3u-bot | 198 | 正常 |
| gh:Xixi-iptv | 51 | 正常 |
| gh:Xixi-iptv | 21 | 正常 |
| gh:m3u-autoupdate | 2748 | 正常 |
| gh:m3u-autoupdate | 5 | 正常 |
| gh:iptv | 221 | 正常 |
| gh:iptv-bridge | 636 | 正常 |
| gh:Xixi-iptv | 20 | 正常 |
| gh:iptv-curated | 45 | 正常 |
| gh:iptv | 1284 | 正常 |
| gh:iptv | 449 | 正常 |
| gh:iptv | 449 | 正常 |
| gh:IPTV-M3U-TOOL | 73 | 正常 |
| gh:iptv | 109 | 正常 |
| gh:myIPTV | 999 | 正常 |
| gh:myIPTV | 341 | 正常 |
| gh:iptv | 0 | 失败：HTTPStatusError: Client error '404 Not Found' for url 'https://raw.githubusercontent.com/app-bot-server/iptv/main/lista.m3u8'
For more information check: https://developer.mozilla.org/en-US/docs/Web/H |

## 带宽实测（决定会不会卡）

| 频道 | 分辨率 | 音轨 | 码率 | 实测速度 | 余量 | 稳定性 | 评分 |
|---|---|---|---|---|---|---|---|
| 翡翠台 | 3840x2160 | aac 44k | 15.3M | 99.4M | 6.5x | 100% | 2417 |
| Bloomberg TV + | 3840x2160 | aac 287k | 10.0M | 58.1M | 5.8x | 100% | 2392 |
| 翡翠台 | 1920x1080 | mp2 144k | 8.0M | 82.4M | 10.3x | 100% | 2379 |
| 翡翠台 | 1920x1080 | mp2 144k | 8.0M | 123.6M | 15.4x | 100% | 2378 |
| 翡翠台 | 1920x1080 | mp2 144k | 8.0M | 133.0M | 16.6x | 100% | 2377 |
| 翡翠台 | 1920x1080 | mp2 144k | 8.0M | 156.6M | 19.6x | 100% | 2375 |
| CNN International | 1920x1080 | aac | 8.9M | 161.7M | 18.1x | 100% | 2358 |
| NHK World-Japan | 1920x1080 | - | 7.0M | 439.1M | 62.7x | 100% | 2357 |
| Al Jazeera English | 1920x1080 | aac | 6.1M | 44.8M | 7.3x | 100% | 2332 |
| NBC News Now 🇺🇸 | 1920x1080 | aac | 5.3M | 75.5M | 14.4x | 100% | 2323 |
| NBC News Now | 1920x1080 | aac | 5.3M | 585.4M | 111.4x | 100% | 2322 |
| NBC News Now | 1920x1080 | aac | 5.3M | 126.7M | 24.1x | 100% | 2320 |
| 无线新闻台 | 1920x1080 | aac 54k | 5.0M | 111.6M | 22.3x | 100% | 2319 |
| 无线新闻 | 1920x1080 | aac 301k | 5.0M | 240.3M | 48.1x | 100% | 2319 |
| 凤凰资讯 | 1920x1080 | aac | 5.0M | 215.2M | 43.0x | 100% | 2319 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 224.3M | 44.9x | 100% | 2318 |
| 翡翠台北美版 | 1920x1080 | aac 54k | 5.0M | 35.2M | 7.0x | 100% | 2318 |
| 无线新闻台 | 1920x1080 | aac 624k | 5.0M | 152.0M | 30.4x | 100% | 2318 |
| 凤凰卫视台 | 1920x1080 | aac | 5.0M | 245.5M | 49.1x | 100% | 2318 |
| 明珠台 | 1920x1080 | - | 5.0M | 41.9M | 8.4x | 100% | 2318 |
| 凤凰资讯台 | 1920x1080 | aac | 5.0M | 145.5M | 29.1x | 100% | 2318 |
| 凤凰香港台 | 1920x1080 | aac 54k | 5.0M | 106.1M | 21.2x | 100% | 2318 |
| 翡翠台 | 1920x1080 | - | 5.0M | 39.4M | 7.9x | 100% | 2318 |
| TVB Plus | 1920x1080 | - | 5.0M | 52.1M | 10.4x | 100% | 2318 |
| NBC News Now | 1920x1080 | aac | 5.3M | 159.8M | 30.4x | 100% | 2316 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 143.0M | 28.6x | 100% | 2315 |
| 华丽翡翠台 | 1920x1080 | aac | 5.0M | 104.7M | 20.9x | 100% | 2315 |
| 凤凰中文 | 1920x1080 | aac | 5.0M | 145.9M | 29.2x | 100% | 2313 |
| 翡翠 | 1920x1080 | - | 5.0M | 50.8M | 10.2x | 100% | 2313 |
| CNN | 1920x1080 | aac 74k | 4.7M | 100.2M | 21.2x | 100% | 2312 |

> 音轨码率低于音轨阈值会标 ⚠ 并被降权：这种源视频很好但声音是噪音。

> 由 iptv-pipeline 自动生成 2026-10-19T22:33:16+00:00
