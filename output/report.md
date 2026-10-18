# IPTV 直播源检测报告

- 运行时间：2026-10-18T04:41:36+00:00 → 2026-10-18T04:48:57+00:00（441.6 秒）
- 解析到流：**15215** 条
- 筛选后：6023 条，去重后：3853 条
- 实际探测：3824 条（拉黑跳过 1791 条）
- 可用：**1046** 条（27.4%），失效：987 条
- 频道数：196，发布：196 个频道 / 369 条线路

## 流类型分布

- `hls`：996
- `mp4`：25
- `ts`：18
- `flv`：5
- `dash`：2

## 带宽实测概览

- 平均下载速度：**17.7 Mbps**（最低 0.8，最高 473.4）
- 平均视频码率：**2.8 Mbps**
- 带宽余量 ≥2x（基本不会卡）：**207/257** 条（占 81%）

> 余量 = 实测速度 ÷ 视频码率。余量 <1 必定卡；1~2 勉强；>2 流畅。

## 分组统计

| 分组 | 可用线路 | 频道数 |
|---|---|---|
| 央视 | 670 | 65 |
| 卫视 | 189 | 15 |
| 吉林 | 7 | 6 |
| 长春 | 1 | 1 |
| 港澳台 | 101 | 51 |
| 国际新闻 | 39 | 20 |
| 其他 | 39 | 38 |

## 采集源

| 源 | 条数 | 状态 |
|---|---|---|
| local-extra | 1 | 正常 |
| bestfan-cctv | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_cctv.m3u8'
For more information check: https://develo |
| bestfan-province | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_province.m3u8'
For more information check: https://de |
| bestfan-all | 124 | 正常 |
| bestfan-all-direct | 124 | 正常 |
| vbskycn-ipv4 | 497 | 正常 |
| vbskycn-ipv4-gh | 497 | 正常 |
| chinaiptv-cntv | 0 | 失败：HTTPStatusError: Client error '429 TOO MANY REQUESTS' for url 'https://ghproxy.net/https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV1_ALL.m3u8'
For more information check: https://deve |
| iptv-org-sports | 481 | 正常 |
| iptv-org-cn | 147 | 正常 |
| iptv-org-hk | 17 | 正常 |
| iptv-org-tw | 28 | 正常 |
| iptv-org-zho | 215 | 正常 |
| iptv-org-news | 1019 | 正常 |
| suxuang-iptv | 1225 | 正常 |
| suxuang-iptv-gh | 1225 | 正常 |
| gh:Xixi-iptv | 53 | 正常 |
| gh:Xixi-iptv | 23 | 正常 |
| gh:iptv-bridge | 636 | 正常 |
| gh:Xixi-iptv | 20 | 正常 |
| gh:m3u-autoupdate | 2748 | 正常 |
| gh:m3u-autoupdate | 5 | 正常 |
| gh:iptv-curated | 45 | 正常 |
| gh:iptv | 1929 | 正常 |
| gh:iptv | 1035 | 正常 |
| gh:iptv | 1035 | 正常 |
| gh:IPTV-M3U-TOOL | 76 | 正常 |
| gh:iptv | 221 | 正常 |
| gh:iptv | 109 | 正常 |
| gh:myIPTV | 1171 | 正常 |
| gh:myIPTV | 367 | 正常 |
| gh:iptv | 0 | 失败：HTTPStatusError: Client error '404 Not Found' for url 'https://raw.githubusercontent.com/app-bot-server/iptv/main/lista.m3u8'
For more information check: https://developer.mozilla.org/en-US/docs/Web/H |

## 带宽实测（决定会不会卡）

| 频道 | 分辨率 | 音轨 | 码率 | 实测速度 | 余量 | 稳定性 | 评分 |
|---|---|---|---|---|---|---|---|
| 翡翠台 | 3840x2160 | aac 241k | 15.3M | 116.2M | 7.6x | 100% | 2419 |
| 翡翠台 | 1920x1080 | mp2 287k | 8.0M | 181.3M | 22.7x | 100% | 2379 |
| 翡翠台 | 1920x1080 | mp2 293k | 8.0M | 187.8M | 23.5x | 100% | 2379 |
| 翡翠台 | 1920x1080 | mp2 293k | 8.0M | 50.4M | 6.3x | 100% | 2379 |
| 翡翠台 | 1920x1080 | mp2 287k | 8.0M | 118.6M | 14.8x | 100% | 2378 |
| NHK World-Japan | 1920x1080 | - | 7.0M | 403.9M | 57.7x | 100% | 2355 |
| Al Jazeera English | 1920x1080 | aac | 6.1M | 206.1M | 33.6x | 100% | 2330 |
| NBC News Now | 1920x1080 | aac | 5.3M | 473.4M | 90.1x | 100% | 2323 |
| 凤凰卫视台 | 1920x1080 | aac | 5.0M | 75.1M | 15.0x | 100% | 2319 |
| 凤凰香港台 | 1920x1080 | aac 54k | 5.0M | 74.1M | 14.8x | 100% | 2319 |
| 无线新闻台 | 1920x1080 | aac 208k | 5.0M | 225.1M | 45.0x | 100% | 2319 |
| 无线新闻 | 1920x1080 | aac | 5.0M | 145.9M | 29.2x | 100% | 2319 |
| 华丽翡翠台 | 1920x1080 | aac | 5.0M | 196.9M | 39.4x | 100% | 2319 |
| 凤凰资讯台 | 1920x1080 | aac | 5.0M | 177.7M | 35.5x | 100% | 2319 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 207.5M | 41.5x | 100% | 2319 |
| 无线新闻台 | 1920x1080 | aac | 5.0M | 147.1M | 29.4x | 100% | 2319 |
| 翡翠台北美版 | 1920x1080 | aac 54k | 5.0M | 49.9M | 10.0x | 100% | 2319 |
| 凤凰香港 | 1920x1080 | aac 54k | 5.0M | 122.3M | 24.5x | 100% | 2319 |
| 凤凰资讯 | 1920x1080 | aac | 5.0M | 172.7M | 34.5x | 100% | 2318 |
| 明珠台 | 1920x1080 | - | 5.0M | 155.1M | 31.0x | 100% | 2318 |
| TVB Plus | 1920x1080 | - | 5.0M | 55.7M | 11.2x | 100% | 2318 |
| TVB翡翠台 | 1920x1080 | - | 5.0M | 128.5M | 25.7x | 100% | 2318 |
| 翡翠台 | 1920x1080 | - | 5.0M | 63.0M | 12.6x | 100% | 2318 |
| 翡翠 | 1920x1080 | - | 5.0M | 78.4M | 15.7x | 100% | 2318 |
| 翡翠台 | 1920x1080 | - | 5.0M | 54.3M | 10.9x | 100% | 2318 |
| 明珠台 | 1920x1080 | - | 5.0M | 59.1M | 11.8x | 100% | 2318 |
| 明珠台 | 1920x1080 | - | 5.0M | 65.8M | 13.2x | 100% | 2317 |
| 翡翠台 | 3840x2160 | aac 131k | 15.3M | 71.6M | 4.7x | 100% | 2314 |
| 凤凰中文 | 1920x1080 | aac | 5.0M | 147.2M | 29.4x | 100% | 2312 |
| ViuTV | 1920x1080 | - | 4.6M | 165.6M | 36.0x | 100% | 2310 |

> 音轨码率低于音轨阈值会标 ⚠ 并被降权：这种源视频很好但声音是噪音。

> 由 iptv-pipeline 自动生成 2026-10-18T04:48:57+00:00
