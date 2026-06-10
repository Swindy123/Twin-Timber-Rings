import pandas as pd
import numpy as np

print("=" * 80)
print("CSV文件数据统计报告")
print("=" * 80)

# 读取第一个CSV文件
print("\n" + "=" * 80)
print("文件1: all_weibo_texts_clean.csv")
print("=" * 80)

df1 = pd.read_csv('all_weibo_texts_clean.csv')

print(f"\n【基本信息】")
print(f"总行数: {len(df1):,}")
print(f"总列数: {len(df1.columns)}")
print(f"列名: {list(df1.columns)}")

print(f"\n【数据类型分布】")
print(df1.dtypes)

print(f"\n【缺失值统计】")
missing = df1.isnull().sum()
missing_pct = (df1.isnull().sum() / len(df1) * 100).round(2)
missing_df = pd.DataFrame({
    '缺失数量': missing,
    '缺失比例(%)': missing_pct
})
print(missing_df[missing_df['缺失数量'] > 0])

print(f"\n【数值列统计描述】")
numeric_cols = df1.select_dtypes(include=[np.number]).columns
if len(numeric_cols) > 0:
    print(df1[numeric_cols].describe())
else:
    print("无数值类型列")

print(f"\n【分类列唯一值统计】")
categorical_cols = df1.select_dtypes(include=['object']).columns
for col in categorical_cols[:5]:  # 只显示前5个分类列
    unique_count = df1[col].nunique()
    print(f"{col}: {unique_count} 个唯一值")
    if unique_count <= 20:
        print(f"  唯一值列表: {df1[col].value_counts().head(10).to_dict()}")

# 新增：针对 all_weibo_texts_clean.csv 的指定列详细统计
print(f"\n【指定列分类详细统计 - 文件1】")
specified_cols_1 = ['data_type', 'author_type', 'stance', 'frame', 'emotion', 'event_stage']
for col in specified_cols_1:
    if col in df1.columns:
        counts = df1[col].value_counts(dropna=False)
        print(f"\n{col} : 共 {df1[col].nunique()} 类, 总计 {len(df1)} 条")
        print(counts.to_string())
    else:
        print(f"\n{col} : 列不存在")

# 读取第二个CSV文件
print("\n" + "=" * 80)
print("文件2: platform_cases_clean.csv")
print("=" * 80)

df2 = pd.read_csv('platform_cases_clean.csv')

print(f"\n【基本信息】")
print(f"总行数: {len(df2):,}")
print(f"总列数: {len(df2.columns)}")
print(f"列名: {list(df2.columns)}")

print(f"\n【数据类型分布】")
print(df2.dtypes)

print(f"\n【缺失值统计】")
missing2 = df2.isnull().sum()
missing_pct2 = (df2.isnull().sum() / len(df2) * 100).round(2)
missing_df2 = pd.DataFrame({
    '缺失数量': missing2,
    '缺失比例(%)': missing_pct2
})
print(missing_df2[missing_df2['缺失数量'] > 0])

print(f"\n【数值列统计描述】")
numeric_cols2 = df2.select_dtypes(include=[np.number]).columns
if len(numeric_cols2) > 0:
    print(df2[numeric_cols2].describe())
else:
    print("无数值类型列")

print(f"\n【分类列唯一值统计】")
categorical_cols2 = df2.select_dtypes(include=['object']).columns
for col in categorical_cols2[:5]:  # 只显示前5个分类列
    unique_count = df2[col].nunique()
    print(f"{col}: {unique_count} 个唯一值")
    if unique_count <= 20:
        print(f"  唯一值列表: {df2[col].value_counts().head(10).to_dict()}")

# 新增：针对 platform_cases_clean.csv 的指定列详细统计
print(f"\n【指定列分类详细统计 - 文件2】")
specified_cols_2 = ['stance', 'emotion', 'frame', 'event_stage']
for col in specified_cols_2:
    if col in df2.columns:
        counts = df2[col].value_counts(dropna=False)
        print(f"\n{col} : 共 {df2[col].nunique()} 类, 总计 {len(df2)} 条")
        print(counts.to_string())
    else:
        print(f"\n{col} : 列不存在")

print("\n" + "=" * 80)
print("统计完成!")
print("=" * 80)