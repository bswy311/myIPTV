# IPTV 直播源检测报告

- 运行时间：2026-10-08T06:13:18+00:00 → 2026-10-08T06:17:08+00:00（230.4 秒）
- 解析到流：**9971** 条
- 筛选后：3138 条，去重后：2105 条
- 实际探测：2076 条（拉黑跳过 1086 条）
- 可用：**654** 条（31.5%），失效：336 条
- 频道数：188，发布：188 个频道 / 352 条线路

## 流类型分布

- `hls`：624
- `mp4`：23
- `flv`：3
- `ts`：2
- `dash`：2

## 带宽实测概览

- 平均下载速度：**39.1 Mbps**（最低 0.8，最高 447.1）
- 平均视频码率：**3.3 Mbps**
- 带宽余量 ≥2x（基本不会卡）：**145/169** 条（占 86%）

> 余量 = 实测速度 ÷ 视频码率。余量 <1 必定卡；1~2 勉强；>2 流畅。

## 分组统计

| 分组 | 可用线路 | 频道数 |
|---|---|---|
| 央视 | 221 | 39 |
| 卫视 | 285 | 42 |
| 吉林 | 5 | 4 |
| 长春 | 1 | 1 |
| 港澳台 | 68 | 44 |
| 国际新闻 | 33 | 20 |
| 其他 | 41 | 38 |

## 采集源

| 源 | 条数 | 状态 |
|---|---|---|
| local-extra | 1 | 正常 |
| bestfan-cctv | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_cctv.m3u8'
For more information check: https://develo |
| bestfan-province | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_province.m3u8'
For more information check: https://de |
| bestfan-all | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_all.m3u8'
For more information check: https://develop |
| bestfan-all-direct | 187 | 正常 |
| vbskycn-ipv4 | 544 | 正常 |
| vbskycn-ipv4-gh | 544 | 正常 |
| chinaiptv-cntv | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV1_ALL.m3u8'
For more information check: https://deve |
| iptv-org-sports | 447 | 正常 |
| iptv-org-cn | 147 | 正常 |
| iptv-org-hk | 18 | 正常 |
| iptv-org-tw | 26 | 正常 |
| iptv-org-zho | 216 | 正常 |
| iptv-org-news | 1034 | 正常 |
| suxuang-iptv | 1225 | 正常 |
| suxuang-iptv-gh | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u'
For more information check: https://developer.mozilla |
| gh:myIPTV | 698 | 正常 |
| gh:myIPTV | 356 | 正常 |
| gh:iptv | 401 | 正常 |
| gh:iptv | 401 | 正常 |
| gh:iptv | 0 | 失败：HTTPStatusError: Client error '404 Not Found' for url 'https://raw.githubusercontent.com/app-bot-server/iptv/main/lista.m3u8'
For more information check: https://developer.mozilla.org/en-US/docs/Web/H |
| gh:iptv-bridge | 636 | 正常 |
| gh:m3u-autoupdate | 2748 | 正常 |
| gh:m3u-autoupdate | 5 | 正常 |

## 带宽实测（决定会不会卡）

| 频道 | 分辨率 | 音轨 | 码率 | 实测速度 | 余量 | 稳定性 | 评分 |
|---|---|---|---|---|---|---|---|
| Bloomberg tv+ 🇺🇸 | 3840x2160 | aac 344k | 10.0M | 142.5M | 14.2x | 100% | 2416 |
| 翡翠台 | 1920x1080 | mp2 | 8.0M | 208.3M | 26.0x | 100% | 2379 |
| 翡翠台 | 1920x1080 | mp2 | 8.0M | 69.6M | 8.7x | 100% | 2379 |
| CNN International | 1920x1080 | aac | 8.9M | 125.6M | 14.1x | 100% | 2376 |
| NHK World-Japan | 1920x1080 | - | 7.0M | 311.0M | 44.4x | 100% | 2355 |
| NBC News Now | 1920x1080 | aac | 5.3M | 380.8M | 72.5x | 100% | 2322 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 210.9M | 42.2x | 100% | 2320 |
| 华丽翡翠台 | 1920x1080 | aac | 5.0M | 236.9M | 47.4x | 100% | 2320 |
| 无线新闻 | 1920x1080 | aac 161k | 5.0M | 160.3M | 32.0x | 100% | 2319 |
| 翡翠台北美版 | 1920x1080 | aac | 5.0M | 209.8M | 42.0x | 100% | 2319 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 196.3M | 39.3x | 100% | 2319 |
| 翡翠 | 1920x1080 | - | 5.0M | 90.2M | 18.0x | 100% | 2319 |
| TVB翡翠台 | 1920x1080 | - | 5.0M | 308.3M | 61.6x | 100% | 2319 |
| 明珠台 | 1920x1080 | - | 5.0M | 38.1M | 7.6x | 100% | 2319 |
| 无线新闻台 | 1920x1080 | aac 161k | 5.0M | 251.8M | 50.4x | 100% | 2319 |
| 凤凰卫视台 | 1920x1080 | aac | 5.0M | 286.2M | 57.2x | 100% | 2319 |
| 翡翠台 | 1920x1080 | - | 5.0M | 86.6M | 17.3x | 100% | 2319 |
| 凤凰资讯台 | 1920x1080 | aac | 5.0M | 180.8M | 36.1x | 100% | 2319 |
| 凤凰香港台 | 1920x1080 | aac 54k | 5.0M | 226.6M | 45.3x | 100% | 2318 |
| 凤凰中文 | 1920x1080 | aac | 5.0M | 267.2M | 53.4x | 100% | 2318 |
| 明珠台 | 1920x1080 | - | 5.0M | 283.0M | 56.6x | 100% | 2318 |
| Sky News | 1920x1080 | aac | 5.3M | 447.1M | 85.1x | 100% | 2318 |
| 凤凰资讯 | 1920x1080 | aac | 5.0M | 247.2M | 49.5x | 100% | 2312 |
| ViuTV | 1920x1080 | - | 4.6M | 52.7M | 11.5x | 100% | 2311 |
| ViuTV | 1920x1080 | - | 4.6M | 91.8M | 20.0x | 100% | 2311 |
| ViuTV | 1920x1080 | - | 4.6M | 120.6M | 26.2x | 100% | 2311 |
| ViuTV | 1920x1080 | - | 4.6M | 258.0M | 56.1x | 100% | 2311 |
| CNN 🇺🇸 | 1920x1080 | aac | 4.7M | 66.2M | 14.0x | 100% | 2309 |
| Reuters TV | 1920x1080 | aac 54k | 4.7M | 61.5M | 13.0x | 100% | 2306 |
| CGTN 财经 | 1920x1080 | aac | 4.7M | 43.6M | 9.3x | 100% | 2305 |

> 音轨码率低于音轨阈值会标 ⚠ 并被降权：这种源视频很好但声音是噪音。

> 由 iptv-pipeline 自动生成 2026-10-08T06:17:08+00:00
