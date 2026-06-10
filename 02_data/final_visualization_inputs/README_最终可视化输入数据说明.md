# C组最终可视化输入数据说明

这个文件夹只放最终可视化脚本 `03_scripts/visualization/analyze_repost_network.py` 实际读取的数据文件。

## 核心输入

- `top_source_posts.csv`：核心源微博清单，对应脚本中的 `SOURCE_PATH`。
- `repost_edges_multihop.csv`：多层传播链边表，对应脚本中的 `EDGE_PATH`。
- `repost_nodes_multihop.csv`：多层传播链节点表，对应脚本中的 `NODE_PATH`。
- `weibo_reposts_api_clean_multihop_labeled.csv`：带立场字段的多层转发清洗数据，对应脚本中的 `REPOST_CLEAN_PATH`。

## 辅助输入

- `recrawl_time_window_summary.csv`：重爬时间窗统计，对应脚本中的 `TIME_WINDOW_PATH`。
- `weibo_reposts_api_raw.csv`：API 原始转发 CSV，脚本用它统计原始行数。
- `repost_chain_summary.md`：旧传播链摘要，脚本用于报告中的补充说明。
- `weibo_reposts_clean_E_data.csv`：E 组/补充转发文本来源，对应脚本中的 `E_data/weibo_reposts_clean.csv`。

## 说明

最终网络图只保留 `fig_06_repost_network.html`，不再生成重复的 `fig_05_repost_network.html`。
