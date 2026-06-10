import csv
import re
import os

MIN_CHARS = 4
MIN_CHINESE_CHARS = 2

ADS_KEYWORDS = [
    '加V', '私信', '优惠', '免费领取', '免费送', '免费拿',
    '点击链接', '复制打开', '淘宝', '天猫', '拼多多', '京东',
    '公众号', '微信', '小程序', '二维码', '扫码',
    '代购', '批发', '厂家直销', '一件代发',
    '兼职', '日赚', '日结', '工资日结',
    '抽奖', '中奖', '恭喜获得', '幸运用户',
    '投资', '理财', '稳赚', '高收益',
    '股票', '期货', '外汇', '数字货币',
    '主播', '直播间', '刷礼物', '打赏',
    '互粉', '互赞', '互评', '涨粉',
    '看上图', '看主页', '看简介', '看我置顶',
    '找我', '私我', '滴滴我',
    '点击头像', '点头像', '看背景',
    '关注我', '加关注',
    'QQ群', 'V群', '微信群',
    '下单', '购买', '包邮', '特价',
    '亲测', '实测', '良心推荐',
    '10年', '20年', '30年', '百年', '老店',
    '不解释', '懂的来', '懂的都懂',
    '有偿', '付费', '收费',
    '网址', '链接', '直达', '入口',
    '领取', '兑换', '红包',
    '转发', '@好友',
]

URL_PATTERN = re.compile(r'https?://t\.cn/\S+', re.IGNORECASE)

EMOJI_PATTERN = re.compile(
    '[\U0001F600-\U0001F64F'
    '\U0001F300-\U0001F5FF'
    '\U0001F680-\U0001F6FF'
    '\U0001F1E0-\U0001F1FF'
    '\U00002702-\U000027B0'
    '\U000024C2-\U0001F251'
    '\U0001F900-\U0001F9FF'
    '\U0001FA00-\U0001FA6F'
    '\U0001FA70-\U0001FAFF'
    '\U00002600-\U000026FF'
    '\U0000FE00-\U0000FE0F'
    '\U0000200D'
    ']', flags=re.UNICODE)

PUNCTUATION_ONLY = re.compile(r'^[\s\[\]\(\)\{\}\[\]【】（）！，。、：；？""''…~～\-—\.\,\!\?\/\\@#\$\^&\*\+=\|`<>《》""''「」『』·\U0000FE00-\U0000FE0F]+$')

MENTION_OR_HASHTAG_ONLY = re.compile(r'^[@#\w\s\[\]\(\)\{\}\[\]【】（）！，。、：；？""''…~～\-—\.\,\!\?\/\\\u4e00-\u9fff]{0,10}$')

def has_meaningful_text(text):
    stripped = text.strip()
    if not stripped:
        return False
    if PUNCTUATION_ONLY.match(stripped):
        return False
    no_emoji = EMOJI_PATTERN.sub('', stripped).strip()
    if not no_emoji:
        return False
    no_emoji_and_url = URL_PATTERN.sub('', no_emoji).strip()
    if not no_emoji_and_url:
        return False
    meaningful_chars = len(re.findall(r'[\u4e00-\u9fff\u0800-\u4e00a-zA-Z0-9]', text))
    if meaningful_chars < MIN_CHARS:
        return False
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if chinese_chars < MIN_CHINESE_CHARS:
        return False
    return True

def is_ad_spam(text):
    text_lower = text.lower()
    for kw in ADS_KEYWORDS:
        if kw in text:
            return True
    url_count = len(URL_PATTERN.findall(text))
    if url_count >= 3:
        return True
    mention_count = text.count('@')
    if mention_count >= 10:
        return True
    if len(text) >= 50:
        repeated_ratio = max(text.count(c) for c in set(text)) / len(text)
        if repeated_ratio > 0.5:
            return True
    return False

def main():
    input_path = 'weibo_reposts_api_clean_multihop.csv'
    output_dir = 'filtered'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'weibo_reposts_api_clean_multihop_filtered.csv')

    kept = 0
    filtered_total = 0
    reasons = {'empty': 0, 'short': 0, 'nonsense': 0, 'ad_spam': 0}

    with open(input_path, 'r', encoding='utf-8') as inf, \
         open(output_path, 'w', encoding='utf-8', newline='') as outf:
        reader = csv.reader(inf)
        writer = csv.writer(outf)

        header = next(reader)
        writer.writerow(header)

        # Find the repost_text column index
        try:
            text_col = header.index('repost_text')
        except ValueError:
            print('ERROR: repost_text column not found in header')
            return

        for row in reader:
            if not row:
                filtered_total += 1
                reasons['empty'] += 1
                continue

            try:
                comment_text = row[text_col]
            except IndexError:
                filtered_total += 1
                reasons['empty'] += 1
                continue

            if not comment_text or not comment_text.strip():
                filtered_total += 1
                reasons['empty'] += 1
                continue

            text = comment_text.strip()

            if not has_meaningful_text(text):
                filtered_total += 1
                if len(text) < MIN_CHARS:
                    reasons['short'] += 1
                else:
                    reasons['nonsense'] += 1
                continue

            if is_ad_spam(text):
                filtered_total += 1
                reasons['ad_spam'] += 1
                continue

            writer.writerow(row)
            kept += 1

    total = kept + filtered_total
    print(f'  {input_path}: kept {kept}/{total}')
    print(f'    empty: {reasons["empty"]}')
    print(f'    short: {reasons["short"]}')
    print(f'    nonsense: {reasons["nonsense"]}')
    print(f'    ad/spam: {reasons["ad_spam"]}')
    print(f'  output: {output_path}')

if __name__ == '__main__':
    main()
