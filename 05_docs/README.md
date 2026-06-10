# 双生年轮：微博舆论场中《年轮》原唱与版权争议的传播可视分析

Twin Annual Rings: Visual Analysis of the Propagation of "Nianlun" Original Singer and Copyright Dispute in the Weibo Public Opinion Field

---

## 项目概述

本项目以微博数据为主，B站、抖音、知乎、豆瓣、QQ音乐为辅助平台，围绕张碧晨与汪苏泷关于歌曲《年轮》的原唱身份、版权与授权争议，通过数据采集、清洗、规则/LLM标注与可视化，揭示社交网络中的传播模式、叙事分化与平台差异。

**核心问题：** 同一首《年轮》，如何在微博舆论场中分裂为"原唱身份"与"创作者/版权"两套并行叙事？

### 目录结构

```
Homework3/
├── 01_crawler/       # 数据采集代码 (A-D组)
├── 02_data/          # 原始/清洗/过滤数据 (A-E组)
├── 03_scripts/       # 数据清洗、分析、可视化代码 (A-E组)
├── 04_figures/       # 输出图表 HTML+PNG + 整合仪表盘
└── 05_docs/          # 标签定义 + 设计规范 + 完整项目文档
```

### 数据来源

| 平台 | 数据类型 | 采集时间 |
|------|---------|---------|
| 微博 | 主帖、评论、转发 | 2025年7月–9月 |
| B站 | 视频+热门评论 | 2025年 |
| 抖音 | 视频+热门评论 | 2025年 |
| 知乎 | 回答+评论 | 2025年 |
| 豆瓣 | 帖子+评论 | 2025年 |
| QQ音乐 | 歌曲评论 | 2025年 |

### 研究方法

```
数据采集 → 数据清洗 → 规则/LLM标注 → 统计分析 → 可视化 → 整合呈现
```

### 标签体系

详细定义见 `05_docs/含义.txt`：

| 维度 | 可选值 |
|------|--------|
| **stance** 立场 | `support_zhang` / `support_wang` / `neutral` / `anti_fanwar` / `unclear` |
| **frame** 叙事框架 | `original_singer` / `copyright_authorization` / `creator_identity` / `memory_emotion` / `legal_discussion` / `fan_conflict` / `platform_meta` / `unclear` |
| **emotion** 情绪 | `angry` / `sad` / `mocking` / `supportive` / `neutral` / `confused` / `unclear` |
| **event_stage** 事件阶段 | `pre_event` / `outbreak` / `response` / `debate` / `cooldown` |

### 各组分工

| 组 | 姓名 | 角色 | 一句话定位 | 核心产出 |
|----|------|------|-----------|---------|
| **A** | 平倩如 | 时间线与热度分析 | 我负责说明事件何时爆发。 | 图1 事件时间线、图2 热度趋势 |
| **B** | 宋薇 | 立场与情绪分析 | 我负责说明网友如何站队和表达情绪。 | 图3 立场分布、图4 双阵营词云对比、图5 立场流变、图18 同质化内容分布 |
| **C** | 陈子怡 | 传播链与网络分析 | 我负责说明微博传播网络如何扩散。 | 图6 传播网络、图7 Top源帖子、图8 Top转发节点、图9 账号类型网络、图10 传播矩阵 |
| **D** | 张欣 | 关键词与叙事分析 | 我负责说明争议叙事如何演化。 | 图11 关键词Top30、图12 叙事桑基图、图15 双阵营框架对比、图16 豆瓣证据链、图17 双生起源时间轴、图19 主帖vs评论vs转发立场对比 |
| **E** | 严宇畅 | 双生年轮与整合 | 我负责把"双生年轮"概念做成最终展示。 | 图13 双生年轮、图14 平台对比、整合仪表盘 |

> **A 做时间，B 做态度，C 做传播，D 做内容，E 做双生概念和最终整合。**

---

## 运行说明

### 环境配置

```bash
# 基础依赖
pip install pandas numpy matplotlib pyecharts networkx jieba scikit-learn requests openpyxl

# C组转发链爬虫需 Playwright
pip install playwright
playwright install

# B组 LLM 标注需 OpenAI 兼容 API
pip install openai
```

### 第一步：数据采集

```bash
# ------ A组: 微博主帖爬虫 ------
python 01_crawler/A_wb_posts/crawl_weibo.py

# ------ B组: 微博评论爬虫 (需先配置 Cookie) ------
# 参考 01_crawler/B_wb_comments/使用指南.txt
python 01_crawler/B_wb_comments/weibo_crawler.py

# ------ C组: 微博转发链爬虫 ------
python 01_crawler/C_wb_reposts/c_weibo_repost_chain_collector.py
python 01_crawler/C_wb_reposts/recrawl_weibo_reposts_api.py
python 01_crawler/C_wb_reposts/recrawl_weibo_reposts_multihop.py

# ------ D组: 跨平台爬虫 ------
python 01_crawler/D_opd/bilibili_scraper.py
python 01_crawler/D_opd/douyin_scraper.py
python 01_crawler/D_opd/douban_scraper.py
python 01_crawler/D_opd/zhihu_scraper.py
python 01_crawler/D_opd/qqmusic_scraper.py
python 01_crawler/D_opd/merge_platform.py
```

### 第二步：数据清洗

```bash
# ------ B组 数据清洗 ------
python 03_scripts/B_scripts/data_cleaning/data_cleaning.py
python 03_scripts/B_scripts/data_cleaning/clean_weibo.py
python 03_scripts/B_scripts/data_cleaning/weibo_final_merge.py

# ------ E组 多阶段清洗流水线 (按编号顺序执行) ------
python 03_scripts/E_scripts/data_cleaning/run_data_cleaning_stage1.py
python 03_scripts/E_scripts/data_cleaning/run_labeling_stage2.py
python 03_scripts/E_scripts/data_cleaning/run_stage3_timefix.py
python 03_scripts/E_scripts/data_cleaning/run_stage4_comments.py
python 03_scripts/E_scripts/data_cleaning/run_final_cleanup.py
```

### 第三步：规则标注 / LLM 标注

```bash
# ------ B组 立场分类 ------
python 03_scripts/B_scripts/stance_filtering/filter_comments.py
python 03_scripts/B_scripts/stance_filtering/filter_reposts.py
python 03_scripts/B_scripts/stance_classify/classify_combined.py
python 03_scripts/B_scripts/stance_classify/llm_stance_batch.py
python 03_scripts/B_scripts/stance_training/train_predict.py

# ------ C组 转发标注 ------
python 03_scripts/C_scripts/labeling/label_c_reposts_with_b2_rules.py
python 03_scripts/C_scripts/labeling/llm_stance_c_reposts.py
```

### 第四步：生成可视化

```bash
# ------ A组: 图1-2 时间线与热度 ------
python 03_scripts/A_scripts/visualization/fig_01_event_timeline.py
python 03_scripts/A_scripts/visualization/fig_02_heat_trend.py

# ------ B组: 图3-5 立场与情绪 ------
python 03_scripts/B_scripts/visualization/plot_fig03_fig04.py
python 03_scripts/B_scripts/visualization/plot_fig05_stance_over_time.py

# ------ C组: 图6-9 传播网络 ------
python 03_scripts/C_scripts/visualization/analyze_repost_network.py

# ------ D组: 图10-13 关键词与叙事 ------
python 03_scripts/D_scripts/visualization/D_analysis_v2.py

# ------ E组: 图13-14 双生年轮与平台对比 ------
python 03_scripts/E_scripts/visualization/fig_13_twin_rings.py
python 03_scripts/E_scripts/visualization/fig_14_platform_comparison.py
```

### 第五步：查看结果

所有图表输出至 `04_figures/` 下各组对应文件夹：

- **HTML 文件** — 浏览器直接打开，支持交互
- **PNG 文件** — 静态图片，适用于 PPT / 报告
- **仪表盘** — `04_figures/dashboard/twin_rings_dashboard_reconstructed.html`

---

## 各组产出对应关系

| 组 | 姓名 | 采集脚本 | 处理脚本 | 输出目录 |
|----|------|---------|---------|---------|
| **A** | 平倩如 | `01_crawler/A_wb_posts/` | `03_scripts/A_scripts/visualization/` | `04_figures/A_figures/` (图1-2) |
| **B** | 宋薇 | `01_crawler/B_wb_comments/` | `03_scripts/B_scripts/` | `04_figures/B_figures/` (图3-5, 18) |
| **C** | 陈子怡 | `01_crawler/C_wb_reposts/` | `03_scripts/C_scripts/` | `04_figures/C_figures/` (图6-10) |
| **D** | 张欣 | `01_crawler/D_opd/` | `03_scripts/D_scripts/` | `04_figures/D_figures/` (图11-12, 15-17, 19) |
| **E** | 严宇畅 | — | `03_scripts/E_scripts/` | `04_figures/E_figures/` (图13-14) |

---

## 图表清单

| 图号 | 名称 | 组 | 格式 |
|------|------|----|------|
| 图1 | 事件时间线：从共同记忆到争议爆发 | A | HTML+PNG |
| 图2 | 热度趋势：微博讨论量的阶段性爆发 | A | HTML+PNG |
| 图3 | 立场分布：原唱与版权叙事的分化 | B | HTML+PNG |
| 图4 | 双阵营词云对比 | B | PNG |
| 图5 | 立场流变：网友态度的阶段演化 | B | HTML+PNG |
| 图6 | 传播网络：核心微博与转发节点 | C | HTML+PNG |
| 图7 | Top源帖子分析 | C | PNG |
| 图8 | Top转发节点分析 | C | PNG |
| 图9 | 账号类型网络分析 | C | HTML+PNG |
| 图10 | 源类型传播矩阵 | C | PNG |
| 图11 | 关键词Top30 | D | HTML+PNG |
| 图12 | 叙事桑基图：关键词如何流向立场 | D | HTML+PNG |
| 图13 | 双生年轮：两套叙事的并行生长 | E | HTML+PNG |
| 图14 | 平台对比：微博/B站/抖音/音乐平台 | E | HTML+PNG |
| 图15 | 双阵营话题框架对比 | D | PNG |
| 图16 | 豆瓣张碧晨支持率分析 | D | PNG |
| 图17 | 双生起源时间轴 | D | PNG |
| 图18 | 同质化内容分布 | B | PNG |
| 图19 | 主帖vs评论vs转发立场对比 | D | PNG |

---

## 设计规范（赤陶松烟）

完整规范见 `05_docs/风格规范.md`，完整分析报告见 `05_docs/文档/项目文档.md`，采用**赤陶赭石**与**松烟墨绿**的冷暖对照。

| 含义 | 色值 | 说明 |
|------|------|------|
| 张碧晨叙事 | `#C07858` | 原唱身份、OST、温暖回忆 |
| 汪苏泷叙事 | `#5A7A6A` | 创作者、版权、理性力量 |
| 中立 | `#8C8C8C` | 中立讨论、无法判断 |
| 冲突 | `#A05050` | 愤怒、反感饭圈 |
| 回忆 | `#D4B898` | 遗憾、怀旧、情感沉淀 |
| 法律 | `#6A8A7A` | 版权、法律解释 |
| 重叠 | `#9A8A7A` | 共同关键词、混合叙事 |

---

## 核心结论

1. **节点触发型传播**：微博讨论量并非平稳增长，而是在关键事件节点附近集中爆发。
2. **混合叙事**：评论区的争议不只是"支持谁"，而是混合了原唱身份、创作者身份、版权授权和粉丝冲突等多种框架。
3. **多中心扩散**：传播由多个核心源微博共同构成传播中心，再通过粉丝号、营销号和普通用户形成二次扩散。
4. **叙事演变**：舆论前期集中在"原唱"→中期转向"版权/授权"→后期出现"体面/双输/饭圈"等情绪性词汇。
5. **平台差异**：微博爆发快、B站偏考据、抖音偏情绪、音乐平台偏回忆沉淀。

---

## 有趣的发现

### Case 1：双方不是在吵同一件事情

两套词汇体系几乎不重叠——汪方谈"版权""授权""收回""合同"，张方谈"原唱""花千骨""OST""十年"。当一方讨论法律问题，另一方讨论情感记忆，这根本不是对话，而是两套话语体系擦肩而过。

### Case 2：统一话术刷屏

评论区出现大量完全相同的模板评论，最高单条重复 **1513 次**。经分析非商业水军，而是粉丝自发组织化复制粘贴——当讨论从"表达观点"退化到"复制粘贴模板"，争议已不再是关于《年轮》，而是话语权的组织化争夺。

### Case 3：不同平台，不同世界

| 平台 | 支持张碧晨 | 支持汪苏泷 |
|------|:--------:|:--------:|
| 豆瓣 | **59.1%** | 8.0% |
| B站 | 19.4% | **80.6%** |
| 知乎 | 22.9% | **30.9%** |
| 抖音 | 14.8% | 33.3% |

同一首歌，不同平台呈现截然不同的立场分布——平台社区文化预设了"谁是对的"。

详细分析见 `文档/项目文档.md`。

---

## 交付物

- `04_figures/` — 所有图表文件（HTML + PNG）
- `04_figures/dashboard/twin_rings_dashboard_reconstructed.html` — 整合仪表盘
- `05_docs/含义.txt` — 标签定义说明
- `05_docs/风格规范.md` — 完整设计规范
- `05_docs/文档/项目文档.md` — 完整项目分析文档

---

## 成员分工

| 成员 | 姓名 | 专业班级 | 学号 | 角色 | 答辩内容 |
|------|------|:-------:|:----:|------|---------|
| A | 平倩如 | 计科2303 | 2312190307 | 时间线与热度分析 | 时间线和热度峰值 |
| B | 宋薇 | 计科2303 | 2312190317 | 立场与情绪分析 | 立场、情绪、高赞评论 |
| C | 陈子怡 | 计科2303 | 2312190329 | 传播链与网络分析 | 转发网络、核心节点、传播路径 |
| D | 张欣 | 计科2303 | 2312190333 | 关键词与叙事分析 | 关键词演化和叙事桑基图 |
| E | 严宇畅 | 大数据2401 | 2402100117 | 总设计与整合 | 主视觉、平台差异、总结观点 |
