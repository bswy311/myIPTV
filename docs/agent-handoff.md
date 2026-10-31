# Agent 交接文档

> **会话开始必读**。读完即可直接干活，不必重新探索仓库。
> **会话收尾必写**：新坑写进 §3、工作写进 §6、待办写进 §7；过时内容直接删，宁短勿长。
> 原则：只记「不看就绕不过去」的内容，不写流水账，每节保持精炼。

最后更新：2026-10-31

---

## 1. 项目速览

IPTV 直播源自动采集→深检→剔除→发布（Python，仅依赖 httpx + PyYAML）。
流水线 7 步在 `src/iptv/pipeline.py::run_pipeline`：采集 → 源发现 → 筛选 → 归一化/去重 → 分层探测+带宽测速 → 历史库 → 发布。
全部可调参数集中在 `config/config.yaml`（注释极详，改配置不动代码）。
详细设计文档：`README.md`（含踩坑来历，写代码前先查对应章节）。

## 2. 关键模块地图

| 文件 | 一句话 |
|---|---|
| `validate.py` | 核心：两阶段探测（高并发可达性 → 低并发带宽测速），评分 `compute_score` |
| `h264.py` / `tsinfo.py` | 从流里解真实分辨率 / 音轨码率（九成清单不声明 RESOLUTION） |
| `normalize.py` | 频道名归一化、英文名本地化、筛选与分类 |
| `history.py` | 历史战绩 JSON，驱动拉黑（连续失败 4 次）与 72h 自动复活 |
| `discover.py` | 每轮自动搜新源，按 新频道数/命中率/上限 三指标自动常驻或淘汰 |
| `epg.py` / `publish.py` / `server.py` | EPG 自托管 / 生成 M3U+报告+网页 / 局域网 8899 订阅服务 |

## 3. 踩坑记录（只记可复发的坑，已修的写明修法所在）

- **墙钟预算**：`bw_total_timeout` 必须 ≥ 内层（拉清单+下完 `bw_sample_bytes`）。内层必须自己看 deadline 提前收工（`validate._limit`），否则外层 `wait_for` cancel 会把已下载数据一起丢，好源被误判超时。曾误杀 122 条流。回归测试：`tests/test_bandwidth.py`。
- **音轨残缺判定宁漏勿错**：只认「真测出低码率」（kbps>0 且 < `audio_min_kbps`）。曾把「PMT 声明了音轨但样本没抓到包」也算残缺，误伤 20 个正常频道（fMP4 易撞出假 PAT/PMT）。
- **分辨率是硬档位不是加分**：同频道内排序键 `(resolution_rank(height), audio_bad, -score)`，标清再快也排高清后。但 `height=0`（解不出 SPS）不当作非高清——fMP4/HEVC 多为 4K，误降权损失更大。
- **筛选先本地化英文名**：`Beijing Satellite TV` → `北京卫视` 再匹配关键词，否则 iptv-org 的 cn 源 122 条只剩 17 条。
- **子串关键词误命中**：不要写裸的 `tvb`（命中 fTVBolivia）、`f1`（命中 TF1）、`jade/pearl/phoenix`（捞进黎巴嫩/广播/凤凰城台）。TVB/凤凰靠英文名本地化成中文名后再命中中文词。
- **EPG 必须自托管**：`live.fanmingming.cn` 已失效；每轮把 e.xml 下到 `output/`（只发布不提交，7MB）随 Pages 发布。
- **镜像源**：GitHub 原始地址在本机时通时不通，所有 GitHub 源配 ghproxy/jsdelivr 镜像 + 直连双份，重复 URL 自动去重。
- **禁止回收自己的发布文件**：`live.m3u/live_full.m3u` 再作为输入会把错误分组和旧线路不断放大。`discover.py` 必须在新搜索、候选合并、历史常驻源三个入口排除本仓库的 raw GitHub / jsDelivr URL；`discover.enabled=false` 时也不能加载常驻源。
- **频道名优先于上游分组**：`group-title` 只能兜底，不能和频道名混在同一关键词串里抢分类，否则“北京卫视 + 央视分组”会错进央视。修复在 `normalize.categorize()`，回归在 `tests/test_normalize.py`。
- **HTTP 200 不等于能看**：非 HLS 第二阶段也必须真实下载样本并计算速度；当前最低速度 3000kbps，已知码率时余量至少 1.5 倍。历史每轮只记一次，测速慢不能按死源累计。发布候选还要独立复测，不能用第一轮结果直接冒充稳定。

## 4. 架构决策（为什么这么设计）

- 两阶段探测并发必须悬殊（200 vs 16）：测速阶段高并发会自己占满宽带，测出的速度全是假的。
- 排序按 `headroom = speed ÷ bitrate` 优先，不是绝对速度：供得上数据 > 画质 > 延迟。
- 历史库 JSON 足够（规模千级），不上数据库；写入用 tempfile + `os.replace` 原子替换。
- 源发现三指标缺一不可：`min_new_channels` 防无价值源、`min_hit_rate` 防全量泛列表（iptv-org index 命中率仅 3%）、`max_new_channels` 防巨型聚合列表冲垮列表。
- 断崖保护：频道数 < 上次 50% 拒绝覆盖 output，防网络抽风冲掉电视上能用的列表。

## 5. 配方（现成做法，直接抄）

- 跑全量：`python main.py run`；本机验证：`python main.py serve` → PotPlayer 订阅 `http://127.0.0.1:8899/live.m3u`
- 跑测试：`python -m pytest tests/ -x -q`
- 量宽带定 `bw_concurrency`：`python tools/speedtest.py -p 6`
- 体检某条流：`python tools/tsprobe.py <url>`（PID/音轨帧/SPS 分辨率）
- 手工加频道：`config/sources/local.m3u`；手动重置历史：`python main.py reset -y`

## 6. 工作记录（只留最近一次的结论，旧的删）

**2026-10-31**：修复分类被 `group-title` 污染、自我采集、非 HLS 测速空转和历史双计；暂停随机 GitHub 搜源，只用注册表及有质量记录的常驻源。76 项直接运行回归通过。完整运行探测 2630 条、初筛 208 条，首轮发布 60 频道/135 线路；随后对 132 条候选独立复测，再淘汰 33 条，最终 `output/live.m3u` 为 **55 频道/99 线路**。北京、吉林、浙江卫视另做约 19~24 秒连续分片抽查，均为 1080p 且音视频轨完整；这不等于已在用户电视上逐台目视确认。

统计口径注意：`data/last_run.json` 仍记录完整运行的 60/135；`data/probed.json` 已被重建为 132 条复测候选（99 条通过），最终数量以 `output/stats.json` 和 M3U 为准。复测数据写 JSON 必须显式 `encoding="utf-8"`，Windows 默认 GBK 会因 URL 特殊字符截断文件。本轮修复与精选结果已提交并推送（`6cddcb8`）。

本机推送注意：仓库 local git config 配了代理 127.0.0.1:7897（Clash），代理没开时直连会被 GFW 重置（API 能通但 git 通道被掐）；开代理后直接 git push 即可。远端可能有 CI 自动提交，先 git pull --rebase -X theirs（冲突以远端为准，那是 CI 新生成的 output/data）。SSH 443 通道也试过，握手被掐，不可靠。

## 7. 待办（按优先级）

1. 电视端抽查主列表，确认实际解码、音画和频道内容；发现错台按精确 URL 排除，不靠频道名整台封杀。
2. **加 error_breakdown 统计**：按超时/DNS/4xx/清单无效/带宽不足归类进 stats 和 report.md，作为调参依据。
3. （可选）镜像源竞速取一（FIRST_COMPLETED），省重复下载 ~1MB/轮。
4. （可选）`last_ok < 24h` 的健康源跳过第一阶段直达测速。

## 8. 用户偏好

- 中文交流；代码注释用中文、密度向现有代码看齐（现有代码注释解释「为什么」）。
- 改配置优先于改代码；改完要跑 `tests/` 回归。
- 本会话任务完成后主动更新本文档 + memory，不等提醒。

## 9. 修订记录

- 2026-10-27 初版：从全仓通读中沉淀架构/坑/配方；登记 8 条优化方案待办。
- 2026-10-27 二次：本地跑通全流程；CI 增加 jsDelivr 缓存自动刷新（电视端订阅走 CDN 解决 github.io 不稳）；已推送远端并触发 CI。记录本机 git 代理推坑。
- 2026-10-31：修复分类、自我采集与测速根因；双轮实测后精选为 55 频道/99 线路，并记录复测数据统计口径。
