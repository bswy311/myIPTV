# IPTV 直播源检测报告

- 运行时间：2026-10-13T14:19:16+00:00 → 2026-10-13T14:24:07+00:00（291.6 秒）
- 解析到流：**12286** 条
- 筛选后：3850 条，去重后：2038 条
- 实际探测：2009 条（拉黑跳过 1078 条）
- 可用：**590** 条（29.4%），失效：341 条
- 频道数：177，发布：177 个频道 / 343 条线路

## 流类型分布

- `hls`：554
- `mp4`：25
- `ts`：6
- `flv`：3
- `dash`：2

## 带宽实测概览

- 平均下载速度：**19.2 Mbps**（最低 0.8，最高 103.0）
- 平均视频码率：**3.5 Mbps**
- 带宽余量 ≥2x（基本不会卡）：**96/144** 条（占 67%）

> 余量 = 实测速度 ÷ 视频码率。余量 <1 必定卡；1~2 勉强；>2 流畅。

## 分组统计

| 分组 | 可用线路 | 频道数 |
|---|---|---|
| 央视 | 217 | 39 |
| 卫视 | 237 | 43 |
| 吉林 | 7 | 6 |
| 长春 | 1 | 1 |
| 港澳台 | 72 | 48 |
| 国际新闻 | 35 | 20 |
| 其他 | 21 | 20 |

## 采集源

| 源 | 条数 | 状态 |
|---|---|---|
| local-extra | 1 | 正常 |
| bestfan-cctv | 72 | 正常 |
| bestfan-province | 90 | 正常 |
| bestfan-all | 173 | 正常 |
| bestfan-all-direct | 173 | 正常 |
| vbskycn-ipv4 | 521 | 正常 |
| vbskycn-ipv4-gh | 521 | 正常 |
| chinaiptv-cntv | 405 | 正常 |
| iptv-org-sports | 454 | 正常 |
| iptv-org-cn | 147 | 正常 |
| iptv-org-hk | 18 | 正常 |
| iptv-org-tw | 26 | 正常 |
| iptv-org-zho | 216 | 正常 |
| iptv-org-news | 1015 | 正常 |
| suxuang-iptv | 1225 | 正常 |
| suxuang-iptv-gh | 1225 | 正常 |
| gh:myIPTV | 658 | 正常 |
| gh:myIPTV | 359 | 正常 |
| gh:iptv | 497 | 正常 |
| gh:iptv | 497 | 正常 |
| gh:iptv | 0 | 失败：HTTPStatusError: Client error '404 Not Found' for url 'https://raw.githubusercontent.com/app-bot-server/iptv/main/lista.m3u8'
For more information check: https://developer.mozilla.org/en-US/docs/Web/H |
| gh:iptv-bridge | 636 | 正常 |
| gh:m3u-autoupdate | 2748 | 正常 |
| gh:iptv | 221 | 正常 |
| gh:m3u-autoupdate | 5 | 正常 |
| gh:IPTV-M3U-TOOL | 71 | 正常 |
| gh:Xixi-iptv | 46 | 正常 |
| gh:Xixi-iptv | 20 | 正常 |
| gh:iptv | 109 | 正常 |
| gh:Xixi-iptv | 17 | 正常 |

## 带宽实测（决定会不会卡）

| 频道 | 分辨率 | 音轨 | 码率 | 实测速度 | 余量 | 稳定性 | 评分 |
|---|---|---|---|---|---|---|---|
| Bloomberg tv+ 🇺🇸 | 3840x2160 | aac 344k | 10.0M | 52.2M | 5.2x | 100% | 2346 |
| NHK World-Japan | 1920x1080 | - | 7.0M | 93.6M | 13.4x | 100% | 2341 |
| CGTN 英语 | 1920x1080 | aac | 5.9M | 66.1M | 11.3x | 100% | 2324 |
| NBC News Now | 1920x1080 | aac | 5.3M | 37.1M | 7.1x | 100% | 2319 |
| NBC News Now | 1920x1080 | aac | 5.3M | 77.2M | 14.7x | 100% | 2318 |
| NBC News Now | 1920x1080 | aac | 5.3M | 39.8M | 7.6x | 100% | 2318 |
| CNN International | 1920x1080 | aac | 8.9M | 60.2M | 6.8x | 100% | 2309 |
| CNBC UK | 1920x1080 | aac | 4.7M | 77.8M | 16.5x | 100% | 2308 |
| CNN 🇺🇸 | 1920x1080 | aac | 4.7M | 42.0M | 8.9x | 100% | 2308 |
| NBC News Now 🇺🇸 | 1920x1080 | aac | 5.3M | 38.5M | 7.3x | 100% | 2306 |
| Reuters TV | 1920x1080 | aac | 4.7M | 41.9M | 8.9x | 100% | 2304 |
| CGTN 英语 | 1920x1080 | aac 49k | 4.5M | 32.9M | 7.2x | 100% | 2298 |
| CNN | 1920x1080 | aac | 4.7M | 29.4M | 6.2x | 100% | 2295 |
| CGTN News 🇬🇧 | 1920x1080 | aac 49k | 4.5M | 41.4M | 9.1x | 100% | 2295 |
| CGTN 财经 | 1920x1080 | aac | 4.7M | 26.3M | 5.6x | 100% | 2269 |
| 深圳卫视 | 1920x1080 | aac 158k | 2.9M | 17.2M | 6.0x | 100% | 2264 |
| TVBS Asia | 1920x1080 | aac 93k | 2.9M | 17.6M | 6.1x | 100% | 2260 |
| 华丽翡翠台 | 1920x1080 | aac 103k | 3.6M | 18.6M | 5.2x | 100% | 2226 |
| 特种兵之火凤凰 | 1920x1080 | aac 106k | 0.3M | 25.0M | 76.7x | 100% | 2215 |
| CNN International | 1920x1080 | aac | 8.9M | 35.3M | 4.0x | 100% | 2194 |
| Al Jazeera English | 1920x1080 | aac | 6.1M | 26.0M | 4.2x | 100% | 2192 |
| 澳视澳门 | 1920x1080 | aac 97k | 3.0M | 15.2M | 5.0x | 100% | 2167 |
| 翡翠 | 1920x1080 | aac 180k | 4.3M | 17.9M | 4.2x | 100% | 2149 |
| bloomberg tv | 1280x720 | aac 146k | 1.2M | 89.9M | 74.9x | 100% | 2138 |
| Bloomberg TV Asia | 1280x720 | aac 58k | 1.2M | 35.4M | 29.5x | 100% | 2131 |
| 明珠台 | 1920x1080 | aac 379k | 4.3M | 16.1M | 3.8x | 100% | 2125 |
| CCTV-7 国防军事 | 1280x720 | aac 159k | 0.4M | 28.7M | 68.3x | 100% | 2122 |
| DW English | 1920x1080 | aac 98k | 5.1M | 18.7M | 3.7x | 100% | 2118 |
| [NFL] Arizona Cardinals vs New York Jets (OVO) | 1280x720 | aac 138k | 0.7M | 11.2M | 15.9x | 100% | 2116 |
| CCTV-8 电视剧 | 1280x720 | aac 62k | 0.5M | 103.0M | 188.6x | 100% | 2116 |

> 音轨码率低于音轨阈值会标 ⚠ 并被降权：这种源视频很好但声音是噪音。

> 由 iptv-pipeline 自动生成 2026-10-13T14:24:07+00:00
