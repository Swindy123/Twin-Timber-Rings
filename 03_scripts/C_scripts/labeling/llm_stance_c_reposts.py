#!/usr/bin/env python3
"""LLM-assisted stance labelling for C-group repost data.

Input:  output_recrawl/weibo_reposts_api_clean_multihop.csv
Output: output_recrawl/weibo_reposts_api_clean_multihop_llm_stance.csv

The script uses an OpenAI-compatible /v1/chat/completions endpoint. You can
provide STANCE_API_BASE_URL + STANCE_API_KEY, or let it try GitHub Copilot via
`gh auth token` like the b2 script did.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests


ROOT = Path(r"D:\nl")
INPUT_PATH = ROOT / "output_recrawl" / "weibo_reposts_api_clean_multihop.csv"
OUTPUT_PATH = ROOT / "output_recrawl" / "weibo_reposts_api_clean_multihop_llm_stance.csv"
GITHUB_COPY_PATH = ROOT / "data_collection" / "data" / "C-recrawl" / "weibo_reposts_api_clean_multihop_llm_stance.csv"

LABELS = ["support_zhang", "support_wang", "neutral", "anti_fanwar", "unclear"]

SYSTEM_PROMPT = """你是一个严格的微博立场判定器。只根据给定文本判断立场，必须输出纯 JSON。

标签只能是：
- support_zhang：支持张碧晨、唯一原唱叙事、强调张碧晨版本/告别年轮/不由就不唱等。
- support_wang：支持汪苏泷、创作者/词曲/版权/授权叙事、强调尊重创作者、版权费、双原唱等。
- neutral：中立陈述、新闻转述、事实说明、法律条款解释，没有明显站队。
- anti_fanwar：反感双方粉丝争吵、劝停争议、批评互撕或饭圈化。
- unclear：语义不足、玩梗太短、无法判断、与事件无关。

判定规则：
1. 只输出 JSON，格式为 {"stance":"标签","confidence":0到1的小数,"reason":"一句短理由"}。
2. 不要输出 Markdown，不要输出代码块。
3. 只提到人名但没有态度时，优先 neutral 或 unclear。
4. 明显劝停、反感互撕时，优先 anti_fanwar。
5. 同时出现多个倾向时，判断主导倾向；无法判断则 unclear。
"""


@dataclass
class ApiConfig:
    base_url: str
    api_key: str
    model: str
    delay: float = 1.5
    timeout: int = 60
    max_retries: int = 6


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
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
    raise ValueError(f"Cannot parse JSON from response: {raw[:200]}")


def get_config() -> ApiConfig:
    model = os.getenv("STANCE_MODEL", "gpt-4o-mini-2024-07-18").strip()
    delay = float(os.getenv("STANCE_DELAY", "1.5"))
    base_url = os.getenv("STANCE_API_BASE_URL", "").strip()
    api_key = os.getenv("STANCE_API_KEY", "").strip()
    if base_url and api_key:
        return ApiConfig(base_url=base_url, api_key=api_key, model=model, delay=delay)

    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
    token = result.stdout.strip()
    return ApiConfig(base_url="https://api.githubcopilot.com", api_key=token, model=model, delay=delay)


def call_llm(session: requests.Session, config: ApiConfig, text: str) -> tuple[str, float, str]:
    url = config.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
        "Editor-Version": "vscode/1.95.0",
        "X-Github-Api-Version": "2023-07-07",
    }
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请判断这条微博转发文本的立场：\n{text}"},
        ],
        "temperature": 0.1,
    }

    last_error: Exception | None = None
    for attempt in range(1, config.max_retries + 1):
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=config.timeout)
            if resp.status_code == 429:
                time.sleep(max(10, attempt * 8))
                continue
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = extract_json(content)
            stance = str(parsed.get("stance", "unclear")).strip()
            if stance not in LABELS:
                stance = "unclear"
            confidence = float(parsed.get("confidence", 0.0) or 0.0)
            confidence = max(0.0, min(1.0, confidence))
            reason = str(parsed.get("reason", "")).strip()[:300]
            return stance, confidence, reason
        except Exception as exc:
            last_error = exc
            time.sleep(attempt * 3)
    return "unclear", 0.0, f"request_failed: {last_error}"


def is_done(reason: Any) -> bool:
    if pd.isna(reason):
        return False
    text = str(reason)
    return bool(text) and not text.startswith("request_failed:")


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM stance labelling for C-group reposts")
    parser.add_argument("--input", default=str(INPUT_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--limit", type=int, default=0, help="Only process N pending rows; 0 means all")
    parser.add_argument("--start-from", type=int, default=None)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        raise FileNotFoundError(input_path)

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

    pending = [i for i in range(len(df)) if not is_done(df.at[i, "stance_llm_reason"])]
    if args.start_from is not None:
        pending = [i for i in pending if i >= args.start_from]
    if args.limit and args.limit > 0:
        pending = pending[: args.limit]

    config = get_config()
    session = requests.Session()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"API: {config.base_url}")
    print(f"Model: {config.model}")
    print(f"Pending this run: {len(pending)}")

    for n, idx in enumerate(pending, start=1):
        text = clean_text(df.at[idx, text_col])
        if not text:
            df.at[idx, "stance_llm"] = "unclear"
            df.at[idx, "stance_llm_confidence"] = 0.0
            df.at[idx, "stance_llm_reason"] = "empty_text"
        else:
            stance, conf, reason = call_llm(session, config, text)
            df.at[idx, "stance_llm"] = stance
            df.at[idx, "stance_llm_confidence"] = conf
            df.at[idx, "stance_llm_reason"] = reason

        if n % 20 == 0:
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            print(f"checkpoint: {n}/{len(pending)}")
        time.sleep(config.delay)

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
