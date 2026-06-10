# C 组（陈子怡）传播链：代码与数据提交说明

## 一、本目录代码（`data_collection/C-chenziyi/`）

| 脚本 | 作用 | 是否主链路 |
|------|------|------------|
| `c_weibo_repost_chain_collector.py` | 从 `weibo_posts.csv` 筛 top20 源帖，生成 `top_source_posts` 等（课程初版 / Playwright） | 源帖筛选 |
| `recrawl_weibo_reposts_api.py` | **一层 API 重爬**：20 源 × repostTimeline，热门/当天/+1/+3/+7 | **是** |
| `recrawl_weibo_reposts_multihop.py` | **多层爬取**：二层种子×50，三层止损；依赖上一层或 `--reuse-layer1` | **是** |
| `label_c_reposts_with_b2_rules.py` | 借鉴 b2 组弱规则方法，对 C 组多跳转发文本补充 `stance_b2_rule` / `frame_b2_rule` / `emotion_weak_rule`，不改原始 CSV | 可选标注 |
| `llm_stance_c_reposts.py` | OpenAI 兼容 API 版大模型立场标注，输出 `stance_llm` / `stance_llm_confidence` / `stance_llm_reason` | 可选标注 |
| `llm_stance_c_reposts_gemini_cli.py` | Gemini CLI 版大模型立场标注，适合已有 Gemini CLI 登录环境时使用 | 可选标注 |
| `c_project_paths.py` | 路径配置（指向 `data/C-data`、`data/C-recrawl`） | 配置 |

### 仍在 `final_analysis/`、未复制到本目录（非提交主链路）

| 脚本 | 说明 |
|------|------|
| `recrawl_weibo_reposts_structured.py` | 早期结构化爬取试验 |
| `debug_weibo_repost_requests.py` 等 `debug_*.py` | 调试接口 |
| `audit_and_repair_repost_data.py` | 旧 `output/` 边表审计 |
| `repair_output_derived_files.py` | 旧 `output/` 衍生修复 |

---

## 二、数据目录（`data_collection/data/`）

### `C-data/` — 源数据与元数据

| 文件 | 说明 |
|------|------|
| `weibo_posts.csv` | 成员 A 主帖全量（筛 top20 用） |
| `top_source_posts.csv` | 核心源 top20（爬虫种子 + 图 07 平台互动量） |
| `weibo_reposts_clean_supplement.csv` | 可选转发文本补充（原 `E_data/weibo_reposts_clean.csv`） |
| `repost_chain_summary.md` | 采集摘要（若有） |
| `weibo_reposts_raw.csv` / `weibo_reposts_clean.csv` / `repost_edges.csv` / `repost_nodes.csv` | 课程初版 collector 产出（对照用） |

### `C-recrawl/` — API 重爬与多层处理结果

| 文件 | 说明 |
|------|------|
| `weibo_reposts_api_raw.csv` | 一层 raw |
| `weibo_reposts_api_clean.csv` | 一层 clean（约 935 行） |
| `repost_edges_api.csv` / `repost_nodes_api.csv` | 一层边/节点 |
| `recrawl_time_window_summary.csv` | 每源时间窗 |
| `recrawl_api_quality_check.md` | 一层质量说明 |
| `weibo_reposts_api_raw_multihop.csv` | 多层 raw |
| `weibo_reposts_api_clean_multihop.csv` | 多层 clean（含 hop 1/2/3） |
| `repost_edges_multihop.csv` / `repost_nodes_multihop.csv` | **传播链分析优先边表** |
| `hot_repost_seeds.csv` | 二层种子 |
| `multihop_crawl_summary.md` | 多层规模汇总 |
| `weibo_reposts_api_clean_labeled.csv` | 带 stance 标注的 clean（分析中间表） |
| `weibo_reposts_api_clean_multihop_labeled.csv` | 多跳 clean 的弱规则标注副本；由 `label_c_reposts_with_b2_rules.py` 生成 |
| `数据收集与处理说明.md` | 流程说明 |

### 可视化产出

可视化代码、HTML/PNG 图表和最终分析报告已整理到同级目录：

`visualization_analysis/C-chenziyi/`

`data_collection/` 仅作为数据收集、清洗、弱标注和数据文件提交目录。

---

## 三、推荐运行顺序

在项目根目录 `D:\nl`（或解压后的等价根目录）执行：

```powershell
cd D:\nl\data_collection\C-chenziyi

# 0) 若尚无 top_source_posts，且已有 data/C-data/weibo_posts.csv
python c_weibo_repost_chain_collector.py --no-auto

# 1) 一层 API（需微博登录，浏览器 profile 在项目根 .weibo_recrawl_profile）
python recrawl_weibo_reposts_api.py --headful

# 2) 多层（可复用已提交的一层 clean）
python recrawl_weibo_reposts_multihop.py --reuse-layer1 --headful

# 3) 可选：借鉴 b2 方法给 C 组多跳转发文本补充弱规则标签
python label_c_reposts_with_b2_rules.py

# 4) 可选：用 Gemini CLI 做大模型辅助立场标注，建议先小批量验证
python llm_stance_c_reposts_gemini_cli.py --limit 20

# 如果没有全局 gemini 命令，可尝试 npx 方式
python llm_stance_c_reposts_gemini_cli.py --command "npx -y @google/gemini-cli" --limit 20
```

可视化分析与出图请到：

```powershell
cd D:\nl
D:\anaconda\python.exe visualization_analysis\C-chenziyi\analyze_repost_network.py
```

依赖：`pandas`、`playwright`（爬虫）、`networkx`、`matplotlib`（分析图）。

说明：b2 组方法主要适合复用为“立场 / 叙事框架”的弱监督标注。`emotion_weak_rule` 只是关键词弱规则，适合做探索性辅助，不建议在答辩中表述为高置信度情感识别。

---

## 四、与开发目录对应关系

| 开发时路径 | 提交包路径 |
|------------|------------|
| `final_analysis/recrawl_*.py` | `C-chenziyi/recrawl_*.py` |
| `final_analysis/analyze_repost_network.py` | `visualization_analysis/C-chenziyi/analyze_repost_network.py` |
| `output/top_source_posts.csv` | `data/C-data/top_source_posts.csv` |
| `output_recrawl/*` | `data/C-recrawl/*` |
| `E_data/weibo_reposts_clean.csv` | `data/C-data/weibo_reposts_clean_supplement.csv` |
