#!/usr/bin/env python3
"""
批量立场判定脚本：读取 data.csv 的 text_clean，调用可配置的 OpenAI 兼容聊天接口，
将结果写回新字段 stance_llm，并支持断点续传、增量保存、重试和进度条。

重要说明：
1. GitHub Copilot 本身没有稳定、公开、通用的 Python HTTP API 可直接调用。
2. 本脚本采用“OpenAI 兼容”接口设计，适用于：
   - 你自己本地搭建的兼容服务
   - 你通过本地代理转发到某个模型服务的接口
   - 任何兼容 /v1/chat/completions 的服务
3. 如果你确实有可用的 Copilot 代理端点，可将其填入环境变量 STANCE_API_BASE_URL。

环境变量：
    STANCE_API_BASE_URL   接口根地址，例如 http://127.0.0.1:8000/v1
    STANCE_API_KEY        认证 token；若接口不需要，可留空
    STANCE_MODEL          模型名，例如 gpt-4o-mini / your-local-model
    STANCE_INPUT_FILE     输入 CSV，默认 data.csv
    STANCE_OUTPUT_FILE    输出 CSV，默认 data_copilot_cleaned.csv
    STANCE_START_FROM     从第几行开始继续处理（0-based，默认自动从已完成部分推断）

依赖：
    pip install pandas requests tqdm

用法：
    python scripts/llm_stance_batch.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import requests
from tqdm import tqdm


LABELS = ["support_zhang", "support_wang", "neutral", "anti_fanwar", "unclear"]

STANCE_PROMPT = """你是一个严格的微博立场判定器。请仅根据给定文本判断其立场，必须输出纯 JSON，不要输出多余解释。

标签定义：
- support_zhang: 支持张碧晨、原唱叙事、强调“原唱/唯一原唱/告别年轮/不唱就不听”等
- support_wang: 支持汪苏泷、创作者/版权/授权叙事、强调作词作曲、版权费、双原唱等
- neutral: 中立、陈述事实、信息转述、无明显站队
- anti_fanwar: 反感饭圈争议、反感吵架、劝停争论、批评双方拉扯
- unclear: 无法判断、语义不足、与事件无关、讽刺难判

判定规则：
1. 只输出 JSON，格式为 {"stance":"标签","confidence":0到1之间的小数,"reason":"一句短理由"}
2. stance 必须且只能是以上 5 个标签之一
3. reason 要简短，不要复述原文太多
4. 如果文本同时出现多种倾向，优先判断最强的主导倾向
5. 如果只是提到事件但没有明确态度，标 neutral
6. 如果文本明显在劝停争论、反感互撕，标 anti_fanwar
"""


@dataclass
class ApiConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60
    max_retries: int = 8
    retry_backoff: float = 3.0
    request_delay: float = 1.5


RULE_REASON_MARKERS = (
    "叙事信号",
    "规则未命中",
    "沿用原 stance",
    "偏中立陈述",
    "语义不足或无法判断",
    "多倾向并列",
    "攻击张碧晨",
    "攻击汪苏泷",
    "反感饭圈互撕或劝停争论",
)


def read_csv_with_fallback(path: str) -> pd.DataFrame:
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb18030"]
    last_error: Optional[Exception] = None
    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"无法读取 CSV: {path}") from last_error


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def build_messages(text: str) -> list[dict[str, str]]:
    user_prompt = (
        "请判断下面这条微博/评论的立场，只返回 JSON。\n\n"
        f"文本：{text}\n\n"
        "输出要求：必须是严格 JSON，不要 Markdown，不要代码块。"
    )
    return [
        {"role": "system", "content": STANCE_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    # 优先尝试直接解析
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        pass

    # 再从文本中抓取第一个 JSON 对象
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"无法从响应中解析 JSON: {raw_text[:300]}")


def validate_stance(value: Any) -> str:
    stance = str(value).strip()
    if stance not in LABELS:
        return "unclear"
    return stance


def is_successful_llm_label(reason: Any) -> bool:
    if pd.isna(reason):
        return False
    text = str(reason).strip()
    if not text or text == "empty_text":
        return text == "empty_text"
    if text.startswith("request_failed:") or text.startswith("unexpected_error:"):
        return False
    return not any(marker in text for marker in RULE_REASON_MARKERS)


def call_chat_api(session: requests.Session, config: ApiConfig, text: str) -> Tuple[str, float, str, str]:
    url = config.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
        "Editor-Version": "vscode/1.95.0",
        "X-Github-Api-Version": "2023-07-07",
    }

    payload = {
        "model": config.model,
        "messages": build_messages(text),
        "temperature": 0.2,
    }

    last_error: Optional[Exception] = None
    for attempt in range(1, config.max_retries + 1):
        try:
            response = session.post(url, headers=headers, json=payload, timeout=config.timeout)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after else config.retry_backoff * attempt * 2
                wait_seconds = max(wait_seconds, 10.0)
                time.sleep(wait_seconds)
                last_error = requests.HTTPError(f"429 Too Many Requests (waited {wait_seconds:.0f}s)")
                continue

            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            parsed = extract_json_object(content)
            stance = validate_stance(parsed.get("stance", "unclear"))
            confidence = parsed.get("confidence", 0.0)
            try:
                confidence = float(confidence)
            except Exception:  # noqa: BLE001
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))
            reason = str(parsed.get("reason", ""))[:300]
            return stance, confidence, reason, content
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < config.max_retries:
                time.sleep(config.retry_backoff * attempt)
            else:
                break

    return "unclear", 0.0, f"request_failed: {last_error}", ""


def validate_copilot_auth(config: ApiConfig) -> None:
    """启动前探测 Copilot 接口是否可用，避免跑几千条后才发现 401。"""
    session = requests.Session()
    url = config.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
        "Editor-Version": "vscode/1.95.0",
        "X-Github-Api-Version": "2023-07-07",
    }
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": "reply with ok"}],
        "temperature": 0,
        "max_tokens": 5,
    }
    response = session.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code == 401:
        hint = (
            "Copilot 认证失败 (401)。请确认：\n"
            "  1. GitHub 账号已订阅 Copilot\n"
            "  2. 终端执行 gh auth login 重新登录\n"
            "  3. 或使用带 Copilot Requests 权限的 fine-grained PAT，设置：\n"
            "     STANCE_API_BASE_URL=https://api.githubcopilot.com\n"
            "     STANCE_API_KEY=github_pat_xxxx"
        )
        if config.api_key.startswith("ghp_"):
            hint += "\n  注意：经典 ghp_ token 不支持 Copilot，需 OAuth 或 github_pat_ token。"
        raise RuntimeError(hint)
    if response.status_code == 429:
        print("[WARN] 接口限流 (429)，将自动慢速重试…")
        return
    response.raise_for_status()
    print("[OK] Copilot 接口探测通过")


def get_config() -> ApiConfig:
    model = os.getenv("STANCE_MODEL", "gpt-4o-mini-2024-07-18").strip()
    delay = float(os.getenv("STANCE_DELAY", "1.5"))

    env_base = os.getenv("STANCE_API_BASE_URL", "").strip()
    env_key = os.getenv("STANCE_API_KEY", "").strip()
    if env_base and env_key:
        print(f"[OK] 使用环境变量接口: {env_base}，模型: {model}")
        return ApiConfig(base_url=env_base, api_key=env_key, model=model, request_delay=delay)

    print("[INFO] 正在通过 GitHub CLI 自动抓取 Copilot Token...")
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
        token = result.stdout.strip()
        base_url = "https://api.githubcopilot.com"
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "无法通过 gh 获取 Token！请先在终端运行 `gh auth login`，"
            "或设置 STANCE_API_BASE_URL + STANCE_API_KEY。"
        ) from exc

    print(f"[OK] 成功对接 Copilot 接口，当前模型: {model}")
    return ApiConfig(base_url=base_url, api_key=token, model=model, request_delay=delay)


def collect_pending_indices(df: pd.DataFrame, start_from: Optional[int]) -> list[int]:
    if start_from is not None:
        return list(range(max(0, int(start_from)), len(df)))

    pending: list[int] = []
    for idx in range(len(df)):
        reason = df.at[idx, "stance_llm_reason"] if "stance_llm_reason" in df.columns else pd.NA
        if is_successful_llm_label(reason):
            continue
        pending.append(idx)
    return pending


def save_checkpoint(df: pd.DataFrame, output_path: str) -> None:
    df.to_csv(output_path, index=False, encoding="utf-8-sig")


def main() -> None:
    base_dir = os.getcwd()
    input_file = os.getenv("STANCE_INPUT_FILE", os.path.join(base_dir, "data.csv"))
    output_file = os.getenv("STANCE_OUTPUT_FILE", os.path.join(base_dir, "data_copilot_cleaned.csv"))
    start_from_env = os.getenv("STANCE_START_FROM", "").strip()
    start_from = int(start_from_env) if start_from_env else None

    df = read_csv_with_fallback(input_file)
    if "text_clean" not in df.columns:
        raise RuntimeError("输入文件缺少 text_clean 列")

    # 初始化结果列，保留原始 stance 以便追踪
    if "stance_llm" not in df.columns:
        df["stance_llm"] = pd.NA
    if "stance_llm_confidence" not in df.columns:
        df["stance_llm_confidence"] = pd.NA
    if "stance_llm_reason" not in df.columns:
        df["stance_llm_reason"] = pd.NA

    if os.path.exists(output_file):
        saved = read_csv_with_fallback(output_file)
        if len(saved) == len(df) and {"stance_llm", "stance_llm_confidence", "stance_llm_reason"}.issubset(saved.columns):
            for col in ["stance_llm", "stance_llm_confidence", "stance_llm_reason"]:
                df[col] = saved[col]

    pending_indices = collect_pending_indices(df, start_from)
    config = get_config()
    validate_copilot_auth(config)
    session = requests.Session()

    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"接口: {config.base_url}")
    print(f"模型: {config.model}")
    print(f"待 LLM 处理: {len(pending_indices)} 条，已完成 LLM: {len(df) - len(pending_indices)} 条")

    if not pending_indices:
        print("所有行均已有有效 LLM 标注，无需继续。")
        return

    processed_since_save = 0
    for idx in tqdm(pending_indices, desc="Stance detection", unit="row"):
        if not is_successful_llm_label(df.at[idx, "stance_llm_reason"]):
            df.at[idx, "stance_llm"] = pd.NA
            df.at[idx, "stance_llm_confidence"] = pd.NA

        text = normalize_text(df.at[idx, "text_clean"])

        if not text:
            df.at[idx, "stance_llm"] = "unclear"
            df.at[idx, "stance_llm_confidence"] = 0.0
            df.at[idx, "stance_llm_reason"] = "empty_text"
            processed_since_save += 1
            if processed_since_save >= 20:
                save_checkpoint(df, output_file)
                processed_since_save = 0
            time.sleep(config.request_delay)
            continue

        try:
            stance, confidence, reason, _raw = call_chat_api(session, config, text)
            if reason.startswith("request_failed:"):
                # 失败时不写入 stance_llm，便于下次续跑
                df.at[idx, "stance_llm_reason"] = reason
            else:
                df.at[idx, "stance_llm"] = stance
                df.at[idx, "stance_llm_confidence"] = confidence
                df.at[idx, "stance_llm_reason"] = reason
        except Exception as exc:  # noqa: BLE001
            df.at[idx, "stance_llm_reason"] = f"unexpected_error: {exc}"

        processed_since_save += 1
        if processed_since_save >= 20:
            save_checkpoint(df, output_file)
            processed_since_save = 0

        time.sleep(config.request_delay)

    save_checkpoint(df, output_file)
    remaining = len(collect_pending_indices(df, None))
    print(f"本轮结束，仍待 LLM 处理: {remaining} 条。")
    if remaining == 0:
        print("全部 LLM 标注完成。")


if __name__ == "__main__":
    main()
