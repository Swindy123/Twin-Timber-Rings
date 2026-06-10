import pandas as pd

# 读取原始CSV文件
df = pd.read_csv('weibo_comments_raw_cp.csv')

# 删除完全重复的行，保留首次出现
df_dedup = df.drop_duplicates(keep='first')

# 保存到新文件（避免覆盖原文件，可自行修改文件名）
df_dedup.to_csv('weibo_comments_raw_cp_dedup.csv', index=False)

print(f"去重完成！原始行数: {len(df)}，去重后行数: {len(df_dedup)}")