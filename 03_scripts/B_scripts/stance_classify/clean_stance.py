#!/usr/bin/env python3
"""
清洗并按规则修正 `stance` 标签的脚本。

用法:
    python scripts/clean_stance.py

会读取当前目录下的 `data.csv`，对 `stance` 为 'neutral' 的行根据 `text_clean` 命中规则强制修正为
'support_zhang' 或 'support_wang'，并将结果保存为 `data_rule_cleaned.csv`。
"""
import os
import sys
import pandas as pd


def try_read_csv(path):
    """尝试使用多种编码读取 CSV。"""
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb18030"]
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise UnicodeDecodeError(f"无法用常见编码读取文件: {path}")


def main():
    workspace_cwd = os.getcwd()
    data_paths = [
        os.path.join(workspace_cwd, "data.csv"),
        os.path.join(os.path.dirname(__file__), "data.csv"),
    ]
    data_path = None
    for p in data_paths:
        if p and os.path.exists(p):
            data_path = p
            break
    if data_path is None:
        print("未找到 data.csv，请把脚本放在工程根目录或确保 data.csv 在当前工作目录。")
        sys.exit(1)

    print(f"读取文件: {data_path}")
    df = try_read_csv(data_path)

    # 确保必要列存在
    if "text_clean" not in df.columns or "stance" not in df.columns:
        print("输入文件必须包含 'text_clean' 和 'stance' 两列。")
        sys.exit(1)

    # 关键词规则（小写）
    zhang_keywords = [
        '如果不是张碧晨', '原唱粉', '不唱我们就不听了', '吃相难看', '版权绑架'
    ]
    wang_keywords = [
        '房东', '租客', '换锁', '吃饱了砸锅', '端起碗吃饭', '当场抓包', '支持汪苏泷'
    ]

    zhang_keywords = [k.lower() for k in zhang_keywords]
    wang_keywords = [k.lower() for k in wang_keywords]

    # 统计函数
    labels_of_interest = ['support_zhang', 'support_wang', 'neutral', 'anti_fanwar', 'unclear']

    def get_counts(series):
        counts = {lab: 0 for lab in labels_of_interest}
        vc = series.value_counts(dropna=False)
        for lab in labels_of_interest:
            if lab in vc:
                counts[lab] = int(vc[lab])
        return counts

    before_counts = get_counts(df['stance'].fillna(''))

    # 修正规则：对所有行应用规则（不再仅对 'neutral'），当命中关键词则覆盖原始标签
    def fix_row(row):
        orig = row.get('stance')
        if pd.isna(orig):
            orig = ''
        text = row.get('text_clean', '')
        if pd.isna(text):
            text = ''
        text_l = str(text).lower()

        # 优先匹配张碧晨关键词（命中则覆盖为 support_zhang）
        for kw in zhang_keywords:
            if kw in text_l:
                return 'support_zhang'

        # 其次匹配汪苏泷关键词（命中则覆盖为 support_wang）
        for kw in wang_keywords:
            if kw in text_l:
                return 'support_wang'

        # 未命中任何规则则保留原标签
        return orig

    # 应用修正
    df['stance'] = df.apply(fix_row, axis=1)

    after_counts = get_counts(df['stance'].fillna(''))

    # 打印前后统计
    print("\n修正前计数:")
    for k, v in before_counts.items():
        print(f"  {k}: {v}")

    print("\n修正后计数:")
    for k, v in after_counts.items():
        print(f"  {k}: {v}")

    out_path = os.path.join(workspace_cwd, 'data_rule_cleaned.csv')
    df.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"\n已保存清洗后的文件: {out_path}")


if __name__ == '__main__':
    main()
