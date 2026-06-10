import pandas as pd
import os

# 定义文件路径
files = [
    'all_weibo_texts_clean.csv',
    'platform_cases_clean.csv',
    'qqmusic_comments_clean.csv',
    'weibo_posts_clean.csv',
    'weibo_reposts_clean.csv'
]

base_path = r'e:\大学\大二\大二下\数据可视化\大作业_传播学\output'

for filename in files:
    filepath = os.path.join(base_path, filename)
    if not os.path.exists(filepath):
        print(f"\n{'='*80}")
        print(f"文件不存在: {filename}")
        continue
    
    print(f"\n{'='*80}")
    print(f"文件: {filename}")
    print(f"{'='*80}")
    
    try:
        df = pd.read_csv(filepath)
        print(f"总行数: {len(df)}")
        print(f"总列数: {len(df.columns)}")
        print(f"\n字段列表: {df.columns.tolist()}")
        
        print(f"\n{'-'*80}")
        print("各字段详细信息:")
        print(f"{'-'*80}")
        
        for col in df.columns:
            unique_vals = df[col].dropna().unique()
            n_unique = len(unique_vals)
            
            # 判断是否是时间字段
            is_time_field = any(keyword in col.lower() for keyword in ['time', 'date', 'crawl'])
            
            print(f"\n【{col}】")
            print(f"  唯一值数量: {n_unique}")
            print(f"  空值数量: {df[col].isna().sum()}")
            
            # 如果是分类字段或取值较少，显示详细分布
            if n_unique <= 15 or col in ['stance', 'frame', 'emotion', 'event_stage', 'author_type', 
                                         'data_type', 'platform', 'keyword_hit', 'is_valid']:
                value_counts = pd.Series(unique_vals).value_counts()
                print(f"  取值分布:")
                for val, count in value_counts.items():
                    print(f"    - '{val}': {count}次 ({count/len(df)*100:.2f}%)")
            
            # 如果是时间字段，检查格式一致性
            elif is_time_field:
                sample_vals = list(unique_vals[:5])
                print(f"  示例值: {sample_vals}")
                # 简单检查格式是否一致
                if n_unique > 0:
                    first_val = str(unique_vals[0])
                    # 检查是否有明显不同的格式
                    formats_consistent = True
                    for val in unique_vals[:20]:  # 检查前20个值
                        val_str = str(val)
                        # 简单的格式检查：长度差异不应太大
                        if abs(len(val_str) - len(first_val)) > 5:
                            formats_consistent = False
                            break
                    print(f"  格式一致性: {'✓ 基本一致' if formats_consistent else '✗ 存在差异'}")
            
            # 数值型字段
            elif df[col].dtype in ['int64', 'float64']:
                print(f"  数据类型: {df[col].dtype}")
                print(f"  最小值: {df[col].min()}")
                print(f"  最大值: {df[col].max()}")
                print(f"  平均值: {df[col].mean():.2f}")
                print(f"  中位数: {df[col].median()}")
            
            # 文本字段且取值很多
            else:
                print(f"  数据类型: {df[col].dtype}")
                sample_vals = list(unique_vals[:5])
                print(f"  示例值: {[str(v)[:50] for v in sample_vals]}")
                
    except Exception as e:
        print(f"读取文件时出错: {e}")

print("\n" + "="*80)
print("分析完成!")
print("="*80)
