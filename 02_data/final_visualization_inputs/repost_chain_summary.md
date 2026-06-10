# 微博传播链采集摘要

- 生成时间：2026-06-06 12:11:38
- 数据模式：自动浏览器采集模式
- 读取微博主帖：10718 条
- 筛选核心传播源微博：50 条
- 成功获得转发数据的微博：0 条
- 总共获得转发记录：0 条
- 传播节点数量：48
- 传播边数量：0

## 采集失败微博
- 无记录。

## 高频转发节点
- 新浪热点：0 次，类型 media
- 梨视频：0 次，类型 ordinary_user
- 汉堡闷酥饼：0 次，类型 ordinary_user
- 水上财源：0 次，类型 ordinary_user
- 财日月：0 次，类型 ordinary_user
- 尽力橘200803：0 次，类型 ordinary_user
- 金城武的阿武：0 次，类型 ordinary_user
- Limerence_Flozacho：0 次，类型 ordinary_user
- 徐曾光光光：0 次，类型 ordinary_user
- 芙蓉花待鱼：0 次，类型 ordinary_user

## 账号类型参与数量
- ordinary_user：44
- media：4

## 输出文件说明
- output/top_source_posts.csv：按传播得分筛出的核心微博主帖。
- output/weibo_reposts_raw.csv：自动采集或手动导入后的原始转发记录。
- output/weibo_reposts_clean.csv：清洗后的转发记录，包含 parent_user 和 user_type。
- output/repost_edges.csv：传播边表，可导入 Gephi、Cytoscape、ECharts、D3。
- output/repost_nodes.csv：传播节点表，可与边表一起构建传播网络图。
- output/repost_chain_summary.md：本摘要。

## 后续可视化建议
- 传播网络图：使用 repost_edges.csv 的 source_user -> target_user 画有向图，用 repost_nodes.csv 给节点着色。
- 账号类型堆叠图：按 user_type 统计参与传播的账号类型。
- 高频节点排行：按 repost_count 展示关键扩散者。
- 传播链层级图：将 direct_repost 与 chain_repost 分开，观察原微博扩散和二次扩散。
- 时间序列图：用 repost_time 展示转发热度随时间变化。