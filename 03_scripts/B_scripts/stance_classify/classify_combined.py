import csv
from collections import Counter

# ===== Frame classification from reason + text =====
# Keywords for text_clean content

def score_keywords(text, kw_list):
    if not text:
        return 0
    return sum(1 for kw in kw_list if kw in text)

# Frame keyword lists for text_clean
TEXT_ORIG = ['原唱', '唯一原唱', '双原唱', '原唱身份', '首发原唱', '原唱者']
TEXT_COPY = ['版权', '授权', '版权费', '收回版权', '著作权', '演唱权', '永久演唱权', '版权方']
TEXT_CREAT = ['创作', '创作者', '词曲', '作词作曲', '写歌', '原创音乐人', '作词', '作曲']
TEXT_MEM = ['告别', '十年', '回忆', '怀旧', '青春', '泪', '遗憾', '感动', '情怀', '泪目', '经典', '老歌']
TEXT_LEGAL = ['法律', '证据', '声明', '合同', '合法', '维权', '依法', '律师', '法庭']
TEXT_FAN = ['粉丝', '饭圈', '吵架', '背刺', '互撕', '骂', '对立', '冲突', '引战', '拉踩', '开撕', '互怼',
              '不要脸', '恶心', '有病', '疯了', '垃圾', '滚', '闭嘴', '装', '绿茶', '白莲', '戏多',
              '撕破脸', '翻桌', '背刺', '反咬', '破防', '硬气']
TEXT_PLAT = ['博主', '网红', '营销号', '热搜', '炒作', '带节奏', '挑拨', '舆论', '争议',
              '旺仔小乔', '挑拨离间', '吃瓜', '路人']

# Frame keyword lists for stance_llm_reason
REASON_ORIG = ['原唱', '唯一原唱', '双原唱', '原唱身份', '首发原唱']
REASON_COPY = ['版权', '授权', '版权费', '收回版权', '著作权', '演唱权', '永久演唱权', '版权问题', '授权收回', '收回授权']
REASON_CREAT = ['创作', '创作者', '词曲', '作词作曲', '写歌', '原创音乐人']
REASON_MEM = ['告别', '十年', '回忆', '怀旧', '泪', '遗憾', '感动', '情怀']
REASON_LEGAL = ['法律', '证据', '声明', '合同', '合法', '维权', '依法']
REASON_FAN = ['粉丝', '饭圈', '吵架', '背刺', '互撕', '骂', '对立', '冲突', '劝架', '劝停', '互骂',
               '贬低', '攻击', '恶意', '反感', '不满', '厌恶', '批评', '指责']
REASON_PLAT = ['博主', '网红', '营销号', '热搜', '炒作', '带节奏', '挑拨', '舆论', '争议']


def classify_frame_combined(reason, text):
    scores = {}

    # Weight: reason 0.6, text 0.4
    def add_score(category, kw_list_text, kw_list_reason):
        s = 0
        s += score_keywords(text, kw_list_text) * 1.0
        s += score_keywords(reason, kw_list_reason) * 2.0
        if s > 0:
            scores[category] = s

    add_score('original_singer', TEXT_ORIG, REASON_ORIG)
    add_score('copyright_authorization', TEXT_COPY, REASON_COPY)
    add_score('creator_identity', TEXT_CREAT, REASON_CREAT)
    add_score('memory_emotion', TEXT_MEM, REASON_MEM)
    add_score('legal_discussion', TEXT_LEGAL, REASON_LEGAL)
    add_score('fan_conflict', TEXT_FAN, REASON_FAN)
    add_score('platform_meta', TEXT_PLAT, REASON_PLAT)

    # Heuristics: 劝停/反感争论 -> fan_conflict
    if any(t in reason for t in ['劝', '反感', '厌烦', '烦', '不满']) and \
       any(t in reason for t in ['争论', '争吵', '粉丝', '饭圈', '撕', '骂']):
        scores['fan_conflict'] = scores.get('fan_conflict', 0) + 1.5

    # 劝/别吵/别撕 in text -> fan_conflict
    if any(t in text for t in ['别吵', '别撕', '别骂', '劝你们', '别争']):
        scores['fan_conflict'] = scores.get('fan_conflict', 0) + 2

    # 张碧晨+原唱 in text -> original_singer
    if '张碧晨' in text and '原唱' in text:
        scores['original_singer'] = scores.get('original_singer', 0) + 2
    if '汪苏泷' in text and ('创作' in text or '词曲' in text or '写' in text):
        scores['creator_identity'] = scores.get('creator_identity', 0) + 2
    if '汪苏泷' in text and ('版权' in text or '授权' in text or '收回' in text):
        scores['copyright_authorization'] = scores.get('copyright_authorization', 0) + 2

    # 告别+年轮/歌 in text -> memory_emotion
    if '告别' in text and any(t in text for t in ['年轮', '歌', '作品']):
        scores['memory_emotion'] = scores.get('memory_emotion', 0) + 2

    if not scores:
        return 'unclear', 0.0

    best = max(scores, key=scores.get)
    best_score = scores[best]
    total = sum(scores.values())
    confidence = round(min(1.0, (best_score / total) * min(1.0, best_score * 0.1 + 0.2)), 4)
    return best, confidence


# ===== Emotion classification from reason + text =====

TEXT_SUPP = ['支持', '加油', '好听', '喜欢', '爱', '好听', '棒', '好', '精彩', '期待']
TEXT_ANGRY = ['愤怒', '气', '恶心', '不要脸', '过分', '恶心', '无语', '有病']
TEXT_SAD = ['遗憾', '难过', '可惜', '心疼', '难受', '泪', '哭了', '心酸', '无奈']
TEXT_MOCK = ['哈哈', '笑死', '呵呵', '搞笑', '笑', '讽刺', '就这']
TEXT_CONF = ['为什么', '不懂', '不明白', '搞不懂', '什么操作', '疑惑']
TEXT_UNCLEAR = []  # no specific text indicators for unclear

REASON_SUPP = ['支持', '祝福', '赞扬', '力挺', '认可', '肯定', '赞同', '维护', '称赞', '加油', '期待']
REASON_ANGRY = ['愤怒', '不满', '批评', '指责', '质问', '批判', '反感', '厌恶']
REASON_SAD = ['遗憾', '难过', '同情', '惋惜', '无妄之灾', '心疼', '伤心', '无奈']
REASON_MOCK = ['讽刺', '嘲讽', '反问', '反讽', '嘲笑', '调侃', '玩梗']
REASON_CONF = ['疑惑', '不解', '困惑', '疑问', '不懂', '纳闷', '费解']
REASON_UNCLEAR = ['无法判断', '语义不足', '信息不足', '仅为引子', '没有立场', '不明确']


def classify_emotion_combined(reason, text):
    scores = {}

    def add_score(category, kw_text, kw_reason):
        s = 0
        s += score_keywords(text, kw_text) * 1.0
        s += score_keywords(reason, kw_reason) * 2.0
        if s > 0:
            scores[category] = s

    add_score('supportive', TEXT_SUPP, REASON_SUPP)
    add_score('angry', TEXT_ANGRY, REASON_ANGRY)
    add_score('sad', TEXT_SAD, REASON_SAD)
    add_score('mocking', TEXT_MOCK, REASON_MOCK)
    add_score('confused', TEXT_CONF, REASON_CONF)

    # Check for unclear indicators in reason
    unclear_score = score_keywords(reason, REASON_UNCLEAR)
    if unclear_score:
        scores['unclear'] = unclear_score * 2.0

    if not scores:
        return 'unclear', 0.0

    best = max(scores, key=scores.get)
    best_score = scores[best]
    total = sum(scores.values())
    confidence = round(min(1.0, (best_score / total) * min(1.0, best_score * 0.1 + 0.2)), 4)
    return best, confidence


with open('data.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    fieldnames = [fn for fn in reader.fieldnames if fn != 'stance_confidence']
    rows = list(reader)

frame_stats = Counter()
emotion_stats = Counter()

new_rows = []
for row in rows:
    reason = row['stance_llm_reason']
    text = row['text_clean']

    frame_val, frame_conf = classify_frame_combined(reason, text)
    emotion_val, emotion_conf = classify_emotion_combined(reason, text)

    row['frame'] = frame_val
    row['emotion'] = emotion_val
    row['frame_confidence'] = str(frame_conf)

    del row['stance_confidence']

    new_rows.append(row)

    frame_stats[frame_val] += 1
    emotion_stats[emotion_val] += 1

with open('data_combined.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(new_rows)

print('=== Frame distribution (reason + text_clean) ===')
for k, v in frame_stats.most_common():
    print(f'  {k}: {v} ({v/50:.1f}%)')

print()
print('=== Emotion distribution (reason + text_clean) ===')
for k, v in emotion_stats.most_common():
    print(f'  {k}: {v} ({v/50:.1f}%)')

print(f'\nDone! {len(new_rows)} rows to data_combined.csv')
