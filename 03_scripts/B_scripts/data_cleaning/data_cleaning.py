import pandas as pd
import jieba
import jieba.analyse
import os
import re
import csv
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# ==================== 配置部分 ====================
INPUT_DIR = r'E:\大学\大二\大二下\数据可视化\大作业_传播学\0606\predicted_stance备份'
OUTPUT_DIR = r'E:\大学\大二\大二下\数据可视化\大作业_传播学\0606\cleaned_data_20250606'

# 创建输出目录
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 月份映射字典
MONTH_MAP = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}

def parse_weibo_time(time_str):
    """
    增强版时间解析：
    - 支持带干扰文字的时间，如 '2025-08-01 08:05 转赞人数超过100'
    - 支持无秒格式 '2025-08-01 08:05'
    - 支持斜杠格式 '2025/7/26 23:30'
    - 保留原有所有格式
    """
    if pd.isna(time_str) or str(time_str).strip() == '':
        return None

    time_str = str(time_str).strip()

    # 从字符串开头提取可能的日期时间片段（秒可选）
    time_extract = re.match(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)', time_str)
    if time_extract:
        time_str = time_extract.group(1)

    # 微博英文格式
    weibo_pattern = r'[A-Z][a-z]{2}\s+([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\s+[+\-]\d{4}\s+(\d{4})'
    match = re.match(weibo_pattern, time_str)
    if match:
        month_str, day, hour, minute, second, year = match.groups()
        month = MONTH_MAP.get(month_str)
        if month:
            try:
                return datetime(int(year), month, int(day), int(hour), int(minute), int(second))
            except:
                pass

    # 中文格式 2025年07月25日 10:40
    chinese_pattern = r'(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})'
    match = re.match(chinese_pattern, time_str)
    if match:
        year, month, day, hour, minute = match.groups()
        try:
            return datetime(int(year), int(month), int(day), int(hour), int(minute))
        except:
            pass

    # 缺少年份的中文 04月19日 16:17
    no_year_pattern = r'(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})'
    match = re.match(no_year_pattern, time_str)
    if match:
        month, day, hour, minute = match.groups()
        try:
            return datetime(2026, int(month), int(day), int(hour), int(minute))
        except:
            pass

    # 标准带秒 2025-07-25 02:16:00
    standard_pattern = r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})'
    match = re.match(standard_pattern, time_str)
    if match:
        year, month, day, hour, minute, second = match.groups()
        try:
            return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
        except:
            pass

    # 标准无秒 2025-08-01 08:05
    standard_no_sec = r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$'
    match = re.match(standard_no_sec, time_str)
    if match:
        year, month, day, hour, minute = match.groups()
        try:
            return datetime(int(year), int(month), int(day), int(hour), int(minute))
        except:
            pass

    # 斜杠格式 2025/7/26 23:30 或 2025/7/26 23:30:32
    slash_pattern = r'(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{2}):(\d{2})(?::(\d{2}))?'
    match = re.match(slash_pattern, time_str)
    if match:
        year, month, day, hour, minute, sec = match.groups()
        sec = int(sec) if sec else 0
        try:
            return datetime(int(year), int(month), int(day), int(hour), int(minute), sec)
        except:
            pass

    # 仅日期 2025-07-25
    date_only_pattern = r'(\d{4})-(\d{2})-(\d{2})$'
    match = re.match(date_only_pattern, time_str)
    if match:
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day))
        except:
            pass

    return None


# 定义事件阶段划分规则
def classify_event_stage(time_str):
    dt = parse_weibo_time(time_str)
    if dt is None:
        return 'unknown'

    pre_event_end = datetime(2025, 7, 21, 23, 59, 59)
    outbreak_start = datetime(2025, 7, 22, 0, 0, 0)
    outbreak_end = datetime(2025, 7, 24, 23, 59, 59)
    response_start = datetime(2025, 7, 25, 0, 0, 0)
    response_end = datetime(2025, 7, 26, 23, 59, 59)
    debate_start = datetime(2025, 7, 27, 0, 0, 0)
    debate_end = datetime(2025, 7, 31, 23, 59, 59)
    cooldown_start = datetime(2025, 8, 1, 0, 0, 0)

    if dt <= pre_event_end:
        return 'pre_event'
    elif outbreak_start <= dt <= outbreak_end:
        return 'outbreak'
    elif response_start <= dt <= response_end:
        return 'response'
    elif debate_start <= dt <= debate_end:
        return 'debate'
    elif dt >= cooldown_start:
        return 'cooldown'
    else:
        return 'unknown'


# ==================== 关键词提取 ====================
try:
    with open('stopwords.txt', 'r', encoding='utf-8') as f:
        STOP_WORDS = set([line.strip() for line in f if line.strip()])
    print(f"已加载外部停用词表，共 {len(STOP_WORDS)} 个词")
except FileNotFoundError:
    STOP_WORDS = set([
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
        '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
        '自己', '这', '他', '她', '它', '那', '什么', '怎么', '吗', '呢', '啊', '吧', '哦',
        '还', '又', '被', '让', '从', '为', '与', '而', '如果', '但是', '因为', '所以',
        '虽然', '可以', '可能', '这个', '那个', '一下', '一个', '已经', '还是', '或者',
        '不过', '不是', '就是', '也是', '只是', '还是', '还有', '然后', '最后', '当然',
        '真的', '哈哈', '转发', '微博', '视频', '网页', '链接'
    ])

EVENT_KEYWORDS = {
    '张碧晨', '汪苏泷', '年轮', '原唱', '版权', '翻唱', '授权', '收回', '回应', '声明',
    '旺仔小乔', '演唱会', '演唱', '歌曲', '歌手', '著作权', '法律责任', '原创', '争议',
    '热搜', '实销', '专辑', '主题曲', '巡演', '联合国', '词曲创作', '劳动成果',
    '双原唱', '周深', '黄霄云', '华晨宇', 'OST', '工作室', '粉丝', '证明',
    '合法权益', '否认', '强调', '记得', '对接', '没收', '感谢', '热爱', '成长',
    '支持', '期待', '发声', '合唱', '收视率', '好听', '实力', '喜欢', '作品',
    '发行', '言论', '误解', '郑重', '维护', '剧方', '无妄之灾', '对立', '唯一', '引导', '官方',
    '理性讨论', '别吵了', '律师函', '维权', '站队', '版权方', '路人', '饭圈', '公关', '辟谣',
    '杜鹃', '唯一原唱', '告别', '体面', '双输' ,'赵丽颖', '花千骨'
}

def extract_keywords(text, topK=15):
    if pd.isna(text) or str(text).strip() == '':
        return ''
    try:
        keywords = jieba.analyse.extract_tags(
            str(text), topK=topK, withWeight=False,
            allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vd', 'vn', 'a', 'ad', 'an')
        )
        filtered = [kw for kw in keywords if kw not in STOP_WORDS and len(kw) > 1 and kw in EVENT_KEYWORDS]
        return ';'.join(filtered[:10])
    except Exception:
        return ''


def process_csv_file(input_path, output_filename, text_column='text'):
    print(f"\n{'='*60}")
    print(f"开始处理文件: {os.path.basename(input_path)}")
    print(f"{'='*60}")

    print("正在读取数据...")
    try:
        df = pd.read_csv(input_path, encoding='utf-8-sig', on_bad_lines='skip')
    except:
        df = pd.read_csv(input_path, encoding='utf-8', on_bad_lines='skip')

    print(f"成功读取行数: {len(df)}")
    print(f"列名: {df.columns.tolist()}")

    # 时间列处理
    time_columns = ['comment_time', 'publish_time', 'repost_time', 'source_publish_time']
    time_col = None
    for col in time_columns:
        if col in df.columns:
            time_col = col
            break

    if time_col is None:
        print("⚠ 警告: 未找到时间列，将跳过event_stage分类")
        df['event_stage'] = 'unknown'
    else:
        print(f"✓ 使用时间列: {time_col}")
        print("正在分类事件阶段...")
        print(f"\n时间列示例（前5条）:")
        for i, val in enumerate(df[time_col].head(5)):
            parsed = parse_weibo_time(val)
            stage = classify_event_stage(val)
            print(f"  {i+1}. 原始: {val}")
            print(f"     解析后: {parsed}")
            print(f"     阶段: {stage}")

        df['event_stage'] = df[time_col].apply(classify_event_stage)

        # 过滤掉因CSV列错位产生的非法阶段值（只保留五个合法阶段）
        valid_stages = ['pre_event', 'outbreak', 'response', 'debate', 'cooldown']
        df = df[df['event_stage'].isin(valid_stages)].copy()

        stage_counts = df['event_stage'].value_counts()
        print("\n事件阶段分布:")
        for stage, count in stage_counts.items():
            percentage = count / len(df) * 100
            print(f"  {stage}: {count} 条 ({percentage:.2f}%)")

    # 文本列处理
    text_columns = [text_column, 'comment_text', 'repost_text', 'text']
    actual_text_col = None
    for col in text_columns:
        if col in df.columns:
            actual_text_col = col
            break

    if actual_text_col is None:
        print("⚠ 警告: 未找到文本列，将跳过关键词提取")
        df['keyword_hit'] = ''
    else:
        print(f"\n✓ 使用文本列: {actual_text_col}")
        print("正在提取关键词（这可能需要几分钟）...")
        total = len(df)
        batch_size = 2000
        keyword_hits = []
        for i in range(0, total, batch_size):
            batch = df[actual_text_col].iloc[i:i+batch_size]
            batch_keywords = batch.apply(extract_keywords)
            keyword_hits.extend(batch_keywords)
            progress = min(i + batch_size, total)
            if progress % 5000 == 0 or progress == total:
                print(f"  进度: {progress}/{total} ({progress/total*100:.1f}%)")
        df['keyword_hit'] = keyword_hits

        print("\n关键词提取示例（前10条非空结果）:")
        non_empty_keywords = df[df['keyword_hit'] != ''][['keyword_hit']].head(10)
        for idx, row in non_empty_keywords.iterrows():
            print(f"  {idx}: {row['keyword_hit']}")

    output_path = os.path.join(OUTPUT_DIR, output_filename)
    print(f"\n正在保存结果到: {output_path}")
    df.to_csv(output_path, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)

    print(f"\n✓ 文件处理完成!")
    print(f"  输出文件: {output_filename}")
    print(f"  总行数: {len(df)}")
    print(f"  总列数: {len(df.columns)}")
    return df


# ==================== 主程序 ====================
if __name__ == '__main__':
    print("=" * 60)
    print("微博数据清洗脚本 v2.0")
    print("功能: 添加event_stage和keyword_hit列")
    print("=" * 60)

    print("\n加载分词词典...")
    custom_words = [
        '张碧晨', '汪苏泷', '年轮', '原唱', '版权', '旺仔小乔',
        '演唱会', '工作室', '回应', '争议', '热搜', '粉丝',
        '周深', '黄霄云', '华晨宇', 'OST', '双原唱',
        '翻唱', '著作权法', '实销', '巡演', '词曲创作', '劳动成果',
        '合法权益', '发布会', '演唱者', '创作者', '声明函', '再版',
        '剧方', '作词', '作曲', '唯一原唱',  '体面', '双输', '告别'
        '赵丽颖', '花千骨'
    ]
    for word in custom_words:
        jieba.add_word(word)
    print(f"已添加 {len(custom_words)} 个自定义词汇")

    files_to_process = [
        {
            'input': os.path.join(INPUT_DIR, 'weibo_comments_all_predicted.csv'),
            'output': 'weibo_comments_all_predicted_cleaned.csv',
            'text_col': 'comment_text'
        },
        {
            'input': os.path.join(INPUT_DIR, 'weibo_posts_predicted.csv'),
            'output': 'weibo_posts_predicted_cleaned.csv',
            'text_col': 'text'
        },
        {
            'input': os.path.join(INPUT_DIR, 'weibo_reposts_api_clean_multihop_filtered_predicted.csv'),
            'output': 'weibo_reposts_api_clean_multihop_filtered_predicted_cleaned.csv',
            'text_col': 'repost_text'
        }
    ]

    results = {}
    for file_info in files_to_process:
        if os.path.exists(file_info['input']):
            try:
                result_df = process_csv_file(
                    file_info['input'],
                    file_info['output'],
                    file_info['text_col']
                )
                results[file_info['output']] = result_df
            except Exception as e:
                print(f"\n✗ 处理文件 {file_info['output']} 时出错: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            print(f"\n⚠ 文件不存在: {file_info['input']}")

    print("\n" + "=" * 60)
    print("所有文件处理完成!")
    print("=" * 60)
    print(f"\n输出目录: {OUTPUT_DIR}")
    print("\n已生成的文件:")
    for filename in results.keys():
        filepath = os.path.join(OUTPUT_DIR, filename)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"  ✓ {filename} ({size_mb:.2f} MB)")
