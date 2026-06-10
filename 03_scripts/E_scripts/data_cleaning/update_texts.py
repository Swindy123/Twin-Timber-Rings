import pandas as pd
from pathlib import Path

# 获取脚本所在目录（即“新数据汇总”文件夹）
base_dir = Path(__file__).resolve().parent

# 输入文件相对路径
comments_file = base_dir / 'weibo_comments_clean.csv'
texts_file = base_dir / 'all_weibo_texts_clean.csv'

# 需要更新的列
update_cols = ['frame', 'emotion', 'keyword_hit', 'frame_confidence', 'confidence']
# 匹配键
key_cols = ['text_raw', 'like_count', 'author_name']

# 读取两个 CSV
print("读取数据...")
comments_df = pd.read_csv(comments_file)
texts_df = pd.read_csv(texts_file)

# 预处理匹配键，保证类型一致
# text_raw 和 author_name 转为字符串，去掉首尾空格，缺失填充空字符串
for col in ['text_raw', 'author_name']:
    comments_df[col] = comments_df[col].astype(str).str.strip().fillna('')
    texts_df[col] = texts_df[col].astype(str).str.strip().fillna('')

# like_count 转为整数（无法转换的用 -1 填充，因为点赞数不应为负）
comments_df['like_count'] = pd.to_numeric(comments_df['like_count'], errors='coerce').fillna(-1).astype(int)
texts_df['like_count'] = pd.to_numeric(texts_df['like_count'], errors='coerce').fillna(-1).astype(int)

# 如果 weibo_comments 中有重复的键，保留第一条并给出提示
dup_keys = comments_df.duplicated(subset=key_cols, keep=False)
if dup_keys.any():
    n_dup = dup_keys.sum()
    print(f"警告：weibo_comments_clean.csv 中存在 {n_dup} 行重复的匹配键，将只保留每组的第一条进行更新。")
    comments_df = comments_df.drop_duplicates(subset=key_cols, keep='first')

# 给 texts 添加原始行索引，方便更新后写回
texts_df['_orig_idx'] = texts_df.index

# 内连接，找出所有能匹配的行
merged = texts_df.merge(
    comments_df[key_cols + update_cols],
    on=key_cols,
    how='inner',
    suffixes=('_old', '')
)

num_updated = len(merged)
print(f"匹配到 {num_updated} 条需要更新的数据。")

if num_updated > 0:
    # 用 comments 的值更新 texts 中对应的行
    # 获取需要更新的原始索引
    target_idx = merged['_orig_idx']
    # 从 merged 中取出更新列的值（注意：由于 suffixes，更新列就是原始列名）
    new_values = merged[update_cols].values
    # 执行更新
    texts_df.loc[target_idx, update_cols] = new_values

    # 删除辅助索引列
    texts_df.drop(columns='_orig_idx', inplace=True)

    # 保存回原文件（覆盖）
    texts_df.to_csv(texts_file, index=False, encoding='utf-8-sig')
    print(f"更新完成，已将 {num_updated} 条数据写回 all_weibo_texts_clean.csv。")
else:
    texts_df.drop(columns='_orig_idx', inplace=True)
    print("没有找到匹配的数据，未进行任何更新。")