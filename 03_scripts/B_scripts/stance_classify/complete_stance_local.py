#!/usr/bin/env python3
"""
补全 data_copilot_cleaned.csv 中未完成或 API 失败的 stance_llm 标注。
保留已成功调用 LLM 的行，对其余行使用与 STANCE_PROMPT 一致的规则引擎判定。
"""
from __future__ import annotations

import os
import re
from typing import Tuple

import pandas as pd
from tqdm import tqdm

LABELS = ["support_zhang", "support_wang", "neutral", "anti_fanwar", "unclear"]

# support_zhang: 原唱叙事、支持张碧晨
ZHANG_PATTERNS = [
    r"支持张碧晨", r"张碧晨.*(原唱|唯一|唱)", r"(唯一|真正|才是|就是)原唱",
    r"原唱.*张碧晨", r"张碧晨方", r"告别年轮", r"不唱就不听", r"不唱我们就不听",
    r"原唱不可替代", r"原唱粉", r"首发就是原唱", r"张碧晨的演唱", r"张的版本",
    r"张姓歌手", r"老姐姐", r"碧晨", r"张碧晨",
    r"如果不是张碧晨",
]

# support_wang: 创作者/版权叙事、支持汪苏泷
WANG_PATTERNS = [
    r"支持汪苏泷", r"汪苏泷.*(词曲|版权|创作|有理|体面|无妄)", r"词曲.*汪苏泷",
    r"汪苏泷方", r"双原唱", r"作词作曲", r"词曲权", r"版权费", r"著作权",
    r"房东", r"租客", r"换锁", r"吃饱了砸锅", r"端起碗吃饭", r"当场抓包",
    r"没有词曲", r"吃尽红利", r"旺仔小乔", r"泷泷", r"汪苏泷", r"wsl",
    r"创作.*(演唱|者)", r"词曲创作", r"法理高地", r"授权收回", r"收回.*授权",
    r"《年轮》回家", r"十万伏特",
]

# anti_fanwar: 反感饭圈互撕
FANWAR_PATTERNS = [
    r"饭圈", r"粉丝撕", r"别撕", r"别吵", r"吵架", r"互撕", r"控评",
    r"两家粉丝", r"写小论文", r"挑起对立", r"无妄之灾", r"双输", r"体面",
    r"莫名其妙", r"路人", r"颠婆", r"茶言茶语", r"背刺", r"农夫与蛇",
    r"低情商", r"挽尊", r"嘴硬", r"打文字战", r"颠倒黑白", r"傲娇",
    r"租房租久", r"当成自己房子",
]

# 攻击张碧晨 → 实际 support_wang
ATTACK_ZHANG_PATTERNS = [
    r"不尊重.*劳动", r"宣称.*唯一原唱", r"操作双标", r"双标",
    r"硬要说.*唯一原唱", r"你方在傲娇", r"吃相难看", r"版权绑架",
    r"砸人饭碗", r"欺负人", r"背刺", r"一脚把他踹",
]

# 攻击汪苏泷 → 实际 support_zhang  
ATTACK_WANG_PATTERNS = [
    r"汪苏泷.*(错|抢|不要脸)", r"词曲都是wsl", r"只负责唱",
]

NEUTRAL_PATTERNS = [
    r"^(回复|转发)$", r"^[\W\d]+$", r"哈哈+", r"笑", r"^\S{1,3}$",
    r"合同", r"永久演唱权", r"声明", r"著作方", r"法律", r"条款",
    r"信息转述", r"发布了", r"据报道",
]


def read_csv(path: str) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise RuntimeError(f"无法读取: {path}")


def normalize(text) -> str:
    if pd.isna(text):
        return ""
    return re.sub(r"\s+", " ", str(text).strip())


def count_patterns(text: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))


def needs_relabel(row) -> bool:
    if pd.isna(row.get("stance_llm")):
        return True
    reason = str(row.get("stance_llm_reason", ""))
    return "request_failed" in reason or "unexpected_error" in reason


def classify_text(text: str, orig_stance: str = "", frame: str = "", keyword_hit: str = "") -> Tuple[str, float, str]:
    if not text or text in ("回复", "转发"):
        return "unclear", 0.0, "empty_text"

    t = text.lower()
    ctx = f"{text} {orig_stance} {frame} {keyword_hit}"

    zhang = count_patterns(ctx, ZHANG_PATTERNS)
    wang = count_patterns(ctx, WANG_PATTERNS)
    fanwar = count_patterns(ctx, FANWAR_PATTERNS)
    atk_z = count_patterns(ctx, ATTACK_ZHANG_PATTERNS)
    atk_w = count_patterns(ctx, ATTACK_WANG_PATTERNS)
    neutral_hits = count_patterns(text, NEUTRAL_PATTERNS)

    # 交叉攻击修正
    if zhang > 0 and atk_z > 0:
        return "support_wang", 0.75, "支持张碧晨语境但攻击张碧晨方，判为支持汪苏泷叙事"
    if wang > 0 and atk_w > 0:
        return "support_zhang", 0.75, "支持汪苏泷语境但攻击汪苏泷，判为支持张碧晨叙事"
    if atk_z > 0 and wang == 0:
        return "support_wang", 0.7, "文本攻击张碧晨方/唯一原唱叙事"
    if atk_w > 0 and zhang == 0:
        return "support_zhang", 0.7, "文本攻击汪苏泷/词曲方"

    scores = {
        "support_zhang": zhang,
        "support_wang": wang,
        "anti_fanwar": fanwar,
    }
    max_score = max(scores.values())

    if max_score == 0:
        if neutral_hits > 0 or orig_stance == "neutral":
            return "neutral", 0.55, "无明显站队，偏中立陈述"
        if orig_stance in LABELS and orig_stance != "unclear":
            return orig_stance, 0.5, f"规则未命中，沿用原 stance={orig_stance}"
        if frame in ("legal_discussion", "copyright_authorization", "platform_meta"):
            return "neutral", 0.5, f"叙事框架为{frame}，偏事实/法律陈述"
        return "unclear", 0.3, "语义不足或无法判断"

    winners = [k for k, v in scores.items() if v == max_score]
    if len(winners) > 1:
        if orig_stance in winners:
            return orig_stance, 0.6, "多倾向并列，沿用原 stance"
        if fanwar in winners and fanwar == max_score:
            return "anti_fanwar", 0.6, "反感饭圈/争议表达"
        return "unclear", 0.4, "多种立场信号并列，难以判定主导倾向"

    label = winners[0]
    conf = min(0.95, 0.55 + max_score * 0.1)
    reasons = {
        "support_zhang": "原唱/张碧晨叙事信号",
        "support_wang": "创作者/版权/汪苏泷叙事信号",
        "anti_fanwar": "反感饭圈互撕或劝停争论",
    }
    return label, conf, reasons[label]


def main() -> None:
    base = os.getcwd()
    output_file = os.path.join(base, "data_copilot_cleaned.csv")
    input_file = os.path.join(base, "data.csv")

    if os.path.exists(output_file):
        df = read_csv(output_file)
    else:
        df = read_csv(input_file)

    for col in ("stance_llm", "stance_llm_confidence", "stance_llm_reason"):
        if col not in df.columns:
            df[col] = pd.NA

    mask = df.apply(needs_relabel, axis=1)
    todo = int(mask.sum())
    print(f"待补全: {todo} / {len(df)}")

    for idx in tqdm(df.index[mask], desc="Completing stance", unit="row"):
        text = normalize(df.at[idx, "text_clean"])
        orig = str(df.at[idx, "stance"]) if "stance" in df.columns and pd.notna(df.at[idx, "stance"]) else ""
        frame = str(df.at[idx, "frame"]) if "frame" in df.columns and pd.notna(df.at[idx, "frame"]) else ""
        kw = str(df.at[idx, "keyword_hit"]) if "keyword_hit" in df.columns and pd.notna(df.at[idx, "keyword_hit"]) else ""

        stance, conf, reason = classify_text(text, orig, frame, kw)
        df.at[idx, "stance_llm"] = stance
        df.at[idx, "stance_llm_confidence"] = conf
        df.at[idx, "stance_llm_reason"] = reason

    df.to_csv(output_file, index=False, encoding="utf-8-sig")

    filled = df["stance_llm"].notna().sum()
    failed = df["stance_llm_reason"].astype(str).str.contains("request_failed").sum()
    print(f"\n完成: stance_llm 已填 {filled}/{len(df)}")
    print(f"仍含 request_failed: {failed}")
    print("\nstance_llm 分布:")
    print(df["stance_llm"].value_counts().to_string())
    print(f"\n已保存: {output_file}")


if __name__ == "__main__":
    main()
