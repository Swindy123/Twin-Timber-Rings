#!/usr/bin/env python3
"""Use Gemini CLI to label stance for C-group repost data.

This script calls Gemini from the command line for each repost text and writes
the same columns as the API version:
  stance_llm, stance_llm_confidence, stance_llm_reason

Default command:
  gemini -p "<prompt>"

If Gemini CLI is not installed globally, pass a command explicitly, for example:
  --command "npx -y @google/gemini-cli"
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(r"D:\nl")
INPUT_PATH = ROOT / "output_recrawl" / "weibo_reposts_api_clean_multihop.csv"
OUTPUT_PATH = ROOT / "output_recrawl" / "weibo_reposts_api_clean_multihop_gemini_stance.csv"
GITHUB_COPY_PATH = ROOT / "data_collection" / "data" / "C-recrawl" / "weibo_reposts_api_clean_multihop_gemini_stance.csv"

LABELS = {"support_zhang", "support_wang", "neutral", "anti_fanwar", "unclear"}

PROMPT_TEMPLATE = """你是一个严格的微博立场判定器。请只根据文本判断立场，并且只输出 JSON，不要 Markdown，不要代码块。

标签只能是：
- support_zhang：支持张碧晨、唯一原唱叙事、强调张碧晨版本/告别年轮/不由就不唱等。
- support_wang：支持汪苏泷、创作者/词曲/版权/授权叙事、强调尊重创作者、版权费、双原唱等。
- neutral：中立陈述、新闻转述、事实说明、法律条款解释，没有明显站队。
- anti_fanwar：反感双方粉丝争吵、劝停争议、批评互撕或饭圈化。
- unclear：语义不足、玩梗太短、无法判断、与事件无关。

输出格式必须严格为：
{{"stance":"标签","confidence":0到1的小数,"reason":"一句短理由"}}

待判断文本：
{text}
"""


def read_csv(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise RuntimeError(f"Cannot read CSV: {path}")


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    text = re.sub(r"http\S+|网页链接|查看图片", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:600]


def extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*?\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
    raise ValueError(f"Cannot parse JSON from Gemini output: {raw[:300]}")


def is_done(reason: Any) -> bool:
    if pd.isna(reason):
        return False
    text = str(reason).strip()
    return bool(text) and not text.startswith(("request_failed:", "parse_failed:"))


def call_gemini(command: list[str], prompt_arg: str, prompt: str, timeout: int) -> tuple[str, float, str]:
    cmd = [*command, prompt_arg, prompt]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        raw = (result.stdout or "").strip()
        if result.returncode != 0:
            err = (result.stderr or raw or "unknown error").strip()
            return "unclear", 0.0, f"request_failed: {err[:280]}"
        parsed = extract_json(raw)
        stance = str(parsed.get("stance", "unclear")).strip()
        if stance not in LABELS:
            stance = "unclear"
        try:
            confidence = float(parsed.get("confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        reason = str(parsed.get("reason", "")).strip()[:300]
        return stance, confidence, reason
    except Exception as exc:
        return "unclear", 0.0, f"request_failed: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gemini CLI stance labelling for C-group reposts")
    parser.add_argument("--input", default=str(INPUT_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--command", default="gemini", help='Gemini command, e.g. "gemini" or "npx -y @google/gemini-cli"')
    parser.add_argument("--prompt-arg", default="-p", help="CLI argument used to pass a one-shot prompt")
    parser.add_argument("--limit", type=int, default=0, help="Only process N pending rows; 0 means all")
    parser.add_argument("--start-from", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    df = read_csv(input_path)
    if output_path.exists():
        saved = read_csv(output_path)
        if len(saved) == len(df):
            df = saved

    for col in ("stance_llm", "stance_llm_confidence", "stance_llm_reason"):
        if col not in df.columns:
            df[col] = pd.NA

    text_col = "repost_text" if "repost_text" in df.columns else "text_clean"
    if text_col not in df.columns:
        raise ValueError("Need repost_text or text_clean column")

    command = shlex.split(args.command)
    exe = command[0]
    if shutil.which(exe) is None:
        raise RuntimeError(
            f"Command not found: {exe}. Install Gemini CLI first, or use --command \"npx -y @google/gemini-cli\"."
        )

    pending = [i for i in range(len(df)) if not is_done(df.at[i, "stance_llm_reason"])]
    if args.start_from is not None:
        pending = [i for i in pending if i >= args.start_from]
    if args.limit and args.limit > 0:
        pending = pending[: args.limit]

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Command: {' '.join(command)} {args.prompt_arg} <prompt>")
    print(f"Pending this run: {len(pending)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    for n, idx in enumerate(pending, start=1):
        text = clean_text(df.at[idx, text_col])
        if not text:
            stance, conf, reason = "unclear", 0.0, "empty_text"
        else:
            prompt = PROMPT_TEMPLATE.format(text=text)
            stance, conf, reason = call_gemini(command, args.prompt_arg, prompt, args.timeout)

        df.at[idx, "stance_llm"] = stance
        df.at[idx, "stance_llm_confidence"] = conf
        df.at[idx, "stance_llm_reason"] = reason

        if n % 10 == 0:
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            print(f"checkpoint: {n}/{len(pending)}")
        time.sleep(args.delay)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    GITHUB_COPY_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output_path, GITHUB_COPY_PATH)

    print("Done. Files written:")
    print(output_path)
    print(GITHUB_COPY_PATH)
    print(df["stance_llm"].value_counts(dropna=False).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
