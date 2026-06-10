"""
c_weibo_repost_chain_collector.py

Course project helper for member C:
"Twin Annual Rings: propagation-chain analysis of the Weibo public opinion field
around the original singer and copyright dispute of 'Nianlun'."

The script:
1. Reads weibo_posts.csv.
2. Cleans interaction counts.
3. Selects top source posts by spread score.
4. Optionally tries to collect publicly visible reposts with Playwright.
5. Supports a manual fallback file, manual_reposts.csv.
6. Exports clean repost records, network edges, network nodes, and a summary.

Compliance notes:
- This script does not bypass login, captcha, access limits, or anti-bot systems.
- If Weibo asks for login/captcha or blocks access, the script records the reason
  and skips that post.
- Browser access is intentionally slow and capped at 200 reposts per source post.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


INPUT_POSTS = "weibo_posts.csv"
MANUAL_REPOSTS = "manual_reposts.csv"
OUTPUT_DIR = Path("output")

TOP_N_SOURCE_POSTS = 20
MAX_REPOSTS_PER_POST = 200
DEFAULT_SLEEP_SECONDS = 3.0

TOP_SOURCE_COLUMNS = [
    "source_post_id",
    "source_post_url",
    "source_author",
    "publish_time",
    "text",
    "repost_count",
    "comment_count",
    "like_count",
    "spread_score",
]

RAW_REPOST_COLUMNS = [
    "source_post_id",
    "source_post_url",
    "source_author",
    "repost_user",
    "repost_user_url",
    "repost_time",
    "repost_text",
    "repost_like_count",
    "repost_user_desc",
    "repost_user_verified",
    "crawl_time",
]

CLEAN_REPOST_COLUMNS = [
    "source_post_id",
    "source_post_url",
    "source_author",
    "repost_user",
    "repost_user_url",
    "repost_time",
    "repost_text_raw",
    "repost_text_clean",
    "parent_user",
    "repost_like_count",
    "repost_user_desc",
    "repost_user_verified",
    "user_type",
    "crawl_time",
]

EDGE_COLUMNS = [
    "source_post_id",
    "source_post_url",
    "source_user",
    "target_user",
    "edge_type",
    "repost_time",
    "repost_text",
    "crawl_time",
]

NODE_COLUMNS = [
    "user_name",
    "user_url",
    "user_type",
    "is_source_author",
    "post_count",
    "repost_count",
    "first_seen_time",
    "last_seen_time",
]


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "gbk"]
    last_error: Optional[Exception] = None
    for encoding in encodings:
        try:
            print(f"[读取] 尝试使用编码 {encoding} 读取 {path}")
            return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
        except UnicodeDecodeError as exc:
            last_error = exc
        except pd.errors.EmptyDataError:
            print(f"[提示] {path} 是空文件，将按空表处理。")
            return pd.DataFrame()
    raise RuntimeError(f"无法读取 {path}，已尝试编码：{', '.join(encodings)}。错误：{last_error}")


def write_csv(df: pd.DataFrame, path: Path, columns: Optional[List[str]] = None) -> None:
    ensure_output_dir()
    if columns is not None:
        for column in columns:
            if column not in df.columns:
                df[column] = ""
        df = df[columns]
    df.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    print(f"[输出] {path} ({len(df)} 行)")


def get_value(row: pd.Series, column: str, default: str = "") -> str:
    if column not in row.index:
        return default
    value = row.get(column, default)
    if pd.isna(value):
        return default
    return str(value).strip()


def ensure_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    df = df.copy()
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df


def parse_count(value: object) -> int:
    """Convert Weibo-like count strings to integers.

    Examples:
    - "1.2万" -> 12000
    - "3万+" -> 30000
    - "转发 563" -> 563
    - "" -> 0
    """
    if value is None or pd.isna(value):
        return 0

    text = str(value).strip()
    if not text:
        return 0

    text = text.replace(",", "").replace("，", "").replace("+", "")
    text = re.sub(r"(转发|评论|赞|点赞|喜欢|次|人)", "", text)
    text = text.strip()

    multiplier = 1
    if "亿" in text:
        multiplier = 100_000_000
        text = text.replace("亿", "")
    elif "万" in text:
        multiplier = 10_000
        text = text.replace("万", "")

    number_match = re.search(r"\d+(?:\.\d+)?", text)
    if not number_match:
        return 0

    try:
        return int(float(number_match.group()) * multiplier)
    except ValueError:
        return 0


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_repost_user(value: object) -> str:
    user = clean_text(value)
    # Common UI labels that can be captured when Weibo's page markup changes.
    invalid_labels = {
        "公开",
        "转发",
        "评论",
        "赞",
        "点赞",
        "分享",
        "收藏",
        "微博",
        "展开",
        "收起",
    }
    if user in invalid_labels:
        return ""
    return user


def extract_post_id(row: pd.Series) -> str:
    post_id = get_value(row, "post_id")
    if post_id:
        return post_id
    url = get_value(row, "url")
    if not url:
        return ""
    match = re.search(r"(?:weibo\.com|m\.weibo\.cn)/(?:status/)?([A-Za-z0-9]+)", url)
    if match:
        return match.group(1)
    return url.rstrip("/").split("/")[-1]


def load_source_posts(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[错误] 未找到输入文件：{path.resolve()}")
        print("[提示] 请把成员 A 提供的 weibo_posts.csv 放在脚本同目录下，然后重新运行。")
        return pd.DataFrame()

    df = read_csv_with_fallback(path)
    print(f"[读取] 微博主帖数量：{len(df)}")
    df = ensure_columns(
        df,
        [
            "post_id",
            "url",
            "author_name",
            "publish_time",
            "text",
            "repost_count",
            "comment_count",
            "like_count",
        ],
    )

    df["post_id"] = df.apply(extract_post_id, axis=1)
    df["repost_count"] = df["repost_count"].apply(parse_count)
    df["comment_count"] = df["comment_count"].apply(parse_count)
    df["like_count"] = df["like_count"].apply(parse_count)
    df["spread_score"] = (
        df["repost_count"] * 0.5 + df["comment_count"] * 0.3 + df["like_count"] * 0.2
    )
    return df


def select_top_sources(posts_df: pd.DataFrame, top_n: int = TOP_N_SOURCE_POSTS) -> pd.DataFrame:
    if posts_df.empty:
        top_df = pd.DataFrame(columns=TOP_SOURCE_COLUMNS)
        write_csv(top_df, OUTPUT_DIR / "top_source_posts.csv", TOP_SOURCE_COLUMNS)
        return top_df

    sorted_df = posts_df.sort_values("spread_score", ascending=False).head(top_n).copy()
    top_df = pd.DataFrame(
        {
            "source_post_id": sorted_df.get("post_id", ""),
            "source_post_url": sorted_df.get("url", ""),
            "source_author": sorted_df.get("author_name", ""),
            "publish_time": sorted_df.get("publish_time", ""),
            "text": sorted_df.get("text", ""),
            "repost_count": sorted_df.get("repost_count", 0),
            "comment_count": sorted_df.get("comment_count", 0),
            "like_count": sorted_df.get("like_count", 0),
            "spread_score": sorted_df.get("spread_score", 0),
        }
    )
    print(f"[筛选] 已筛选核心传播源微博：{len(top_df)} 条")
    write_csv(top_df, OUTPUT_DIR / "top_source_posts.csv", TOP_SOURCE_COLUMNS)
    return top_df


def detect_access_issue(page_text: str) -> Optional[str]:
    text = page_text or ""
    checks = [
        ("验证码", "页面出现验证码"),
        ("安全验证", "页面要求安全验证"),
        ("访问频繁", "访问频繁"),
        ("登录", "页面要求登录"),
        ("权限", "页面权限不足"),
        ("抱歉，此微博", "微博不可见或已删除"),
        ("不存在", "微博不存在或不可见"),
        ("暂时无法查看", "暂时无法查看"),
    ]
    for marker, reason in checks:
        if marker in text:
            return reason
    return None


def build_repost_url(source_url: str, source_post_id: str) -> str:
    """Build a normal browser URL for the repost page.

    Weibo URL rules change over time, so this is intentionally conservative. The
    script first opens the original URL, then tries the repost tab/button. This
    fallback URL only helps when the post id is enough for a standard status URL.
    """
    if source_url:
        return source_url
    if source_post_id:
        return f"https://weibo.com/status/{source_post_id}"
    return ""


def parse_repost_item_text(text: str) -> Dict[str, str]:
    """Best-effort parser for visible repost cards.

    Weibo page markup changes frequently. This parser keeps the script runnable
    and avoids fragile private API calls. Missing fields remain blank.
    """
    text = clean_text(text)
    result = {
        "repost_user": "",
        "repost_time": "",
        "repost_text": text,
        "repost_like_count": "",
    }

    if not text:
        return result

    # Common visible pattern: "用户名：转发内容 ..." or "用户名 转发了 ..."
    user_match = re.match(r"^@?([\u4e00-\u9fa5A-Za-z0-9_\-·.]{2,30})[:：\s]", text)
    if user_match:
        result["repost_user"] = user_match.group(1).strip()

    time_match = re.search(
        r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s*\d{0,2}:?\d{0,2}|"
        r"\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}|"
        r"今天\s*\d{1,2}:\d{2}|昨天\s*\d{1,2}:\d{2}|"
        r"\d+\s*(?:秒|分钟|小时)前)",
        text,
    )
    if time_match:
        result["repost_time"] = time_match.group(1).strip()

    like_match = re.search(r"(?:赞|点赞)\s*(\d+(?:\.\d+)?\s*[万亿]?\+?)", text)
    if like_match:
        result["repost_like_count"] = like_match.group(1).strip()

    return result


def visible_repost_locators(page) -> List:
    """Return likely repost item locators without using private endpoints."""
    selector_candidates = [
        "div[action-type='feed_list_item']",
        "div[node-type='feed_list_item']",
        "article",
        "div.card-wrap",
        "div[class*='Feed']",
        "div[class*='vue-recycle-scroller__item-view']",
    ]
    locators = []
    for selector in selector_candidates:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                locators.append(locator)
        except Exception:
            continue
    return locators


def try_click_repost_tab(page) -> bool:
    text_candidates = ["转发", "转发列表"]
    for text in text_candidates:
        try:
            locator = page.get_by_text(text, exact=False).first
            if locator.count() > 0:
                locator.click(timeout=3000)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


def collect_reposts_for_source(
    page,
    source: pd.Series,
    max_reposts: int = MAX_REPOSTS_PER_POST,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
) -> Tuple[List[Dict[str, str]], Optional[str]]:
    source_post_id = get_value(source, "source_post_id")
    source_post_url = get_value(source, "source_post_url")
    source_author = get_value(source, "source_author")
    target_url = build_repost_url(source_post_url, source_post_id)

    if not target_url:
        return [], "缺少微博链接，无法打开"

    print(f"[采集] 打开微博：{source_post_id or target_url}")
    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(2500)
    except Exception as exc:
        return [], f"页面打开失败：{exc}"

    try:
        issue = detect_access_issue(page.inner_text("body", timeout=5000))
        if issue:
            return [], issue
    except Exception:
        pass

    clicked = try_click_repost_tab(page)
    if not clicked:
        print("[采集] 未找到明确的转发入口，将尝试解析当前页面公开可见内容。")

    rows: List[Dict[str, str]] = []
    seen_keys = set()
    stagnant_rounds = 0
    last_count = 0

    while len(rows) < max_reposts and stagnant_rounds < 4:
        try:
            body_text = page.inner_text("body", timeout=5000)
            issue = detect_access_issue(body_text)
            if issue:
                return rows, issue if not rows else None
        except Exception:
            body_text = ""

        locators = visible_repost_locators(page)
        for locator in locators:
            try:
                count = min(locator.count(), 80)
            except Exception:
                continue

            for index in range(count):
                if len(rows) >= max_reposts:
                    break
                try:
                    item = locator.nth(index)
                    item_text = item.inner_text(timeout=1000)
                except Exception:
                    continue

                parsed = parse_repost_item_text(item_text)
                repost_user = normalize_repost_user(parsed.get("repost_user", ""))
                repost_text = parsed.get("repost_text", "")
                if not repost_text:
                    continue

                key = (repost_user, repost_text[:80])
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                user_url = ""
                try:
                    link = item.locator("a[href*='/u/'], a[href*='weibo.com/']").first
                    if link.count() > 0:
                        user_url = link.get_attribute("href") or ""
                        if user_url.startswith("//"):
                            user_url = "https:" + user_url
                except Exception:
                    user_url = ""

                rows.append(
                    {
                        "source_post_id": source_post_id,
                        "source_post_url": source_post_url,
                        "source_author": source_author,
                        "repost_user": repost_user,
                        "repost_user_url": user_url,
                        "repost_time": parsed.get("repost_time", ""),
                        "repost_text": repost_text,
                        "repost_like_count": parsed.get("repost_like_count", ""),
                        "repost_user_desc": "",
                        "repost_user_verified": "",
                        "crawl_time": now_string(),
                    }
                )

        print(f"[采集] 当前微博已采集 {len(rows)} / {max_reposts} 条公开可见转发")

        if len(rows) == last_count:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0
            last_count = len(rows)

        if len(rows) >= max_reposts:
            break

        try:
            page.mouse.wheel(0, 1800)
            page.wait_for_timeout(int(sleep_seconds * 1000))
        except Exception:
            time.sleep(sleep_seconds)

    if not rows:
        return rows, "未采集到公开可见转发，可能需要登录、页面结构变化或转发列表不可见"
    return rows, None


def collect_reposts_with_playwright(
    top_sources: pd.DataFrame,
    max_reposts: int,
    sleep_seconds: float,
    headless: bool,
) -> Tuple[pd.DataFrame, List[Dict[str, str]]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[提示] 未安装 Playwright，跳过自动采集。")
        print("[安装] pip install playwright pandas")
        print("[安装] playwright install")
        return pd.DataFrame(columns=RAW_REPOST_COLUMNS), [
            {
                "source_post_id": "",
                "source_post_url": "",
                "source_author": "",
                "reason": "未安装 Playwright",
            }
        ]

    all_rows: List[Dict[str, str]] = []
    failures: List[Dict[str, str]] = []
    profile_dir = str(Path(".weibo_browser_profile").resolve())

    print("[采集] 将启动浏览器正常访问微博页面。")
    print("[提示] 如果页面要求登录，请在打开的浏览器中手动登录；脚本不会绕过登录或验证码。")

    with sync_playwright() as p:
        browser_type = p.chromium
        context = browser_type.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=headless,
            viewport={"width": 1360, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()

        if not headless:
            print("[等待] 如需手动登录，请在 60 秒内完成；若已登录可直接等待脚本继续。")
            page.goto("https://weibo.com", wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(60_000)

        for index, source in top_sources.iterrows():
            source_post_id = get_value(source, "source_post_id")
            print(f"[进度] {index + 1}/{len(top_sources)} source_post_id={source_post_id}")
            rows, failure_reason = collect_reposts_for_source(
                page=page,
                source=source,
                max_reposts=max_reposts,
                sleep_seconds=sleep_seconds,
            )
            all_rows.extend(rows)
            if failure_reason:
                failures.append(
                    {
                        "source_post_id": source_post_id,
                        "source_post_url": get_value(source, "source_post_url"),
                        "source_author": get_value(source, "source_author"),
                        "reason": failure_reason,
                    }
                )
                print(f"[跳过] {source_post_id}：{failure_reason}")
            time.sleep(sleep_seconds)

        context.close()

    raw_df = pd.DataFrame(all_rows)
    raw_df = ensure_columns(raw_df, RAW_REPOST_COLUMNS)
    return raw_df[RAW_REPOST_COLUMNS], failures


def extract_parent_user(repost_text: str, source_author: str) -> Tuple[str, str]:
    text = clean_text(repost_text)
    mentions = re.findall(r"//@([^:\s：/]+)\s*[:：]", text)
    if mentions:
        return mentions[0].strip(), "chain_repost"
    if source_author:
        return source_author, "direct_repost"
    return "", "unknown"


def classify_user(
    user_name: str = "",
    desc: str = "",
    verified: str = "",
    text: str = "",
) -> str:
    combined = f"{user_name} {desc} {verified} {text}".lower()
    if not combined.strip():
        return "unknown"

    rules = [
        (
            "media",
            [
                "新闻",
                "日报",
                "晚报",
                "财经",
                "娱乐",
                "电视台",
                "广播",
                "观察",
                "澎湃",
                "新浪",
                "搜狐",
                "网易",
                "腾讯",
                "凤凰",
                "头条",
                "时报",
                "传媒",
            ],
        ),
        (
            "marketing",
            ["娱乐圈", "吃瓜", "扒圈", "爆料", "八卦", "热搜", "娱记", "瓜主", "冲浪", "星闻"],
        ),
        (
            "fan_account",
            ["后援会", "超话", "站子", "个站", "粉丝团", "应援", "数据组", "打投", "安利", "守护", "唯粉"],
        ),
        (
            "legal_account",
            ["律师", "法律", "法务", "知识产权", "版权", "著作权", "普法", "律所"],
        ),
        (
            "music_account",
            ["音乐", "乐评", "歌单", "ost", "华语音乐", "唱作人", "作词", "作曲", "编曲"],
        ),
    ]

    for user_type, keywords in rules:
        if any(keyword in combined for keyword in keywords):
            return user_type

    if user_name or desc or text:
        return "ordinary_user"
    return "unknown"


def clean_reposts(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df.empty:
        return pd.DataFrame(columns=CLEAN_REPOST_COLUMNS)

    raw_df = ensure_columns(raw_df, RAW_REPOST_COLUMNS)
    rows = []
    for _, row in raw_df.iterrows():
        source_author = get_value(row, "source_author")
        repost_text_raw = get_value(row, "repost_text")
        repost_text_clean = clean_text(repost_text_raw)
        parent_user, edge_type = extract_parent_user(repost_text_clean, source_author)
        user_type = classify_user(
            user_name=get_value(row, "repost_user"),
            desc=get_value(row, "repost_user_desc"),
            verified=get_value(row, "repost_user_verified"),
            text=repost_text_clean,
        )
        rows.append(
            {
                "source_post_id": get_value(row, "source_post_id"),
                "source_post_url": get_value(row, "source_post_url"),
                "source_author": source_author,
                "repost_user": normalize_repost_user(get_value(row, "repost_user")),
                "repost_user_url": get_value(row, "repost_user_url"),
                "repost_time": get_value(row, "repost_time"),
                "repost_text_raw": repost_text_raw,
                "repost_text_clean": repost_text_clean,
                "parent_user": parent_user,
                "repost_like_count": parse_count(get_value(row, "repost_like_count")),
                "repost_user_desc": get_value(row, "repost_user_desc"),
                "repost_user_verified": get_value(row, "repost_user_verified"),
                "user_type": user_type,
                "crawl_time": get_value(row, "crawl_time") or now_string(),
                "_edge_type": edge_type,
            }
        )

    clean_df = pd.DataFrame(rows)
    clean_df = ensure_columns(clean_df, CLEAN_REPOST_COLUMNS + ["_edge_type"])
    return clean_df


def build_edges(clean_df: pd.DataFrame) -> pd.DataFrame:
    if clean_df.empty:
        return pd.DataFrame(columns=EDGE_COLUMNS)

    rows = []
    for _, row in clean_df.iterrows():
        target_user = get_value(row, "repost_user")
        source_user = get_value(row, "parent_user") or get_value(row, "source_author")
        edge_type = get_value(row, "_edge_type")
        if not edge_type:
            edge_type = "chain_repost" if source_user != get_value(row, "source_author") else "direct_repost"
        if not source_user or not target_user:
            edge_type = "unknown"
        rows.append(
            {
                "source_post_id": get_value(row, "source_post_id"),
                "source_post_url": get_value(row, "source_post_url"),
                "source_user": source_user,
                "target_user": target_user,
                "edge_type": edge_type,
                "repost_time": get_value(row, "repost_time"),
                "repost_text": get_value(row, "repost_text_clean"),
                "crawl_time": get_value(row, "crawl_time"),
            }
        )
    return pd.DataFrame(rows, columns=EDGE_COLUMNS)


def min_nonempty(values: Iterable[str]) -> str:
    cleaned = [value for value in values if value]
    return min(cleaned) if cleaned else ""


def max_nonempty(values: Iterable[str]) -> str:
    cleaned = [value for value in values if value]
    return max(cleaned) if cleaned else ""


def build_nodes(clean_df: pd.DataFrame, top_sources: pd.DataFrame) -> pd.DataFrame:
    source_authors = set()
    source_post_count = Counter()
    for _, row in top_sources.iterrows():
        author = get_value(row, "source_author")
        if author:
            source_authors.add(author)
            source_post_count[author] += 1

    user_records: Dict[str, Dict[str, object]] = {}

    for author in source_authors:
        user_records[author] = {
            "user_name": author,
            "user_url": "",
            "user_type": classify_user(user_name=author),
            "is_source_author": True,
            "post_count": source_post_count[author],
            "repost_count": 0,
            "times": [],
        }

    for _, row in clean_df.iterrows():
        user_name = get_value(row, "repost_user")
        if not user_name:
            continue

        if user_name not in user_records:
            user_records[user_name] = {
                "user_name": user_name,
                "user_url": get_value(row, "repost_user_url"),
                "user_type": get_value(row, "user_type") or classify_user(user_name=user_name),
                "is_source_author": user_name in source_authors,
                "post_count": source_post_count[user_name],
                "repost_count": 0,
                "times": [],
            }
        record = user_records[user_name]
        if not record.get("user_url"):
            record["user_url"] = get_value(row, "repost_user_url")
        record["repost_count"] = int(record.get("repost_count", 0)) + 1
        if get_value(row, "repost_time"):
            record["times"].append(get_value(row, "repost_time"))
        elif get_value(row, "crawl_time"):
            record["times"].append(get_value(row, "crawl_time"))

    rows = []
    for record in user_records.values():
        times = record.get("times", [])
        rows.append(
            {
                "user_name": record.get("user_name", ""),
                "user_url": record.get("user_url", ""),
                "user_type": record.get("user_type", "unknown"),
                "is_source_author": bool(record.get("is_source_author", False)),
                "post_count": int(record.get("post_count", 0)),
                "repost_count": int(record.get("repost_count", 0)),
                "first_seen_time": min_nonempty(times),
                "last_seen_time": max_nonempty(times),
            }
        )

    nodes_df = pd.DataFrame(rows, columns=NODE_COLUMNS)
    if not nodes_df.empty:
        nodes_df = nodes_df.sort_values(["repost_count", "post_count"], ascending=False)
    return nodes_df


def load_manual_reposts(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    print(f"[兜底] 检测到 {path}，将优先使用手动导入数据生成传播链。")
    manual_df = read_csv_with_fallback(path)
    manual_df = ensure_columns(manual_df, RAW_REPOST_COLUMNS)
    return manual_df[RAW_REPOST_COLUMNS]


def write_summary(
    posts_df: pd.DataFrame,
    top_sources: pd.DataFrame,
    raw_reposts: pd.DataFrame,
    clean_reposts_df: pd.DataFrame,
    edges_df: pd.DataFrame,
    nodes_df: pd.DataFrame,
    failures: List[Dict[str, str]],
    used_manual: bool,
) -> None:
    ensure_output_dir()
    successful_sources = (
        clean_reposts_df["source_post_id"].nunique()
        if not clean_reposts_df.empty and "source_post_id" in clean_reposts_df.columns
        else 0
    )

    high_frequency_nodes = []
    if not nodes_df.empty:
        high_frequency_nodes = (
            nodes_df.sort_values("repost_count", ascending=False)
            .head(10)[["user_name", "user_type", "repost_count"]]
            .to_dict("records")
        )

    type_counts = Counter()
    if not nodes_df.empty and "user_type" in nodes_df.columns:
        type_counts.update(nodes_df["user_type"].fillna("unknown").replace("", "unknown").tolist())

    lines = [
        "# 微博传播链采集摘要",
        "",
        f"- 生成时间：{now_string()}",
        f"- 数据模式：{'手动导入兜底模式' if used_manual else '自动浏览器采集模式'}",
        f"- 读取微博主帖：{len(posts_df)} 条",
        f"- 筛选核心传播源微博：{len(top_sources)} 条",
        f"- 成功获得转发数据的微博：{successful_sources} 条",
        f"- 总共获得转发记录：{len(clean_reposts_df)} 条",
        f"- 传播节点数量：{len(nodes_df)}",
        f"- 传播边数量：{len(edges_df)}",
        "",
        "## 采集失败微博",
    ]

    if failures:
        for item in failures:
            lines.append(
                f"- {item.get('source_post_id', '')} | {item.get('source_author', '')} | "
                f"{item.get('source_post_url', '')} | 原因：{item.get('reason', '')}"
            )
    else:
        lines.append("- 无记录。")

    lines.extend(["", "## 高频转发节点"])
    if high_frequency_nodes:
        for item in high_frequency_nodes:
            lines.append(
                f"- {item.get('user_name', '')}：{item.get('repost_count', 0)} 次，"
                f"类型 {item.get('user_type', 'unknown')}"
            )
    else:
        lines.append("- 暂无。")

    lines.extend(["", "## 账号类型参与数量"])
    if type_counts:
        for user_type, count in type_counts.most_common():
            lines.append(f"- {user_type}：{count}")
    else:
        lines.append("- 暂无。")

    lines.extend(
        [
            "",
            "## 输出文件说明",
            "- output/top_source_posts.csv：按传播得分筛出的核心微博主帖。",
            "- output/weibo_reposts_raw.csv：自动采集或手动导入后的原始转发记录。",
            "- output/weibo_reposts_clean.csv：清洗后的转发记录，包含 parent_user 和 user_type。",
            "- output/repost_edges.csv：传播边表，可导入 Gephi、Cytoscape、ECharts、D3。",
            "- output/repost_nodes.csv：传播节点表，可与边表一起构建传播网络图。",
            "- output/repost_chain_summary.md：本摘要。",
            "",
            "## 后续可视化建议",
            "- 传播网络图：使用 repost_edges.csv 的 source_user -> target_user 画有向图，用 repost_nodes.csv 给节点着色。",
            "- 账号类型堆叠图：按 user_type 统计参与传播的账号类型。",
            "- 高频节点排行：按 repost_count 展示关键扩散者。",
            "- 传播链层级图：将 direct_repost 与 chain_repost 分开，观察原微博扩散和二次扩散。",
            "- 时间序列图：用 repost_time 展示转发热度随时间变化。",
        ]
    )

    path = OUTPUT_DIR / "repost_chain_summary.md"
    path.write_text("\n".join(lines), encoding="utf-8-sig")
    print(f"[输出] {path}")


def run_pipeline(args: argparse.Namespace) -> None:
    ensure_output_dir()

    posts_path = Path(args.posts)
    manual_path = Path(args.manual)

    posts_df = load_source_posts(posts_path)
    top_sources = select_top_sources(posts_df, top_n=args.top_n)

    failures: List[Dict[str, str]] = []
    used_manual = False

    manual_df = load_manual_reposts(manual_path)
    if manual_df is not None:
        raw_reposts = manual_df
        used_manual = True
    elif args.no_auto:
        print("[采集] 已指定 --no-auto，跳过浏览器自动采集。")
        raw_reposts = pd.DataFrame(columns=RAW_REPOST_COLUMNS)
    elif top_sources.empty:
        print("[采集] 无核心传播源，跳过自动采集。")
        raw_reposts = pd.DataFrame(columns=RAW_REPOST_COLUMNS)
    else:
        raw_reposts, failures = collect_reposts_with_playwright(
            top_sources=top_sources,
            max_reposts=args.max_reposts,
            sleep_seconds=args.sleep,
            headless=args.headless,
        )

    raw_reposts = ensure_columns(raw_reposts, RAW_REPOST_COLUMNS)[RAW_REPOST_COLUMNS]
    write_csv(raw_reposts, OUTPUT_DIR / "weibo_reposts_raw.csv", RAW_REPOST_COLUMNS)

    clean_df = clean_reposts(raw_reposts)
    clean_export_df = clean_df.drop(columns=["_edge_type"], errors="ignore")
    write_csv(clean_export_df, OUTPUT_DIR / "weibo_reposts_clean.csv", CLEAN_REPOST_COLUMNS)

    edges_df = build_edges(clean_df)
    write_csv(edges_df, OUTPUT_DIR / "repost_edges.csv", EDGE_COLUMNS)

    nodes_df = build_nodes(clean_df, top_sources)
    write_csv(nodes_df, OUTPUT_DIR / "repost_nodes.csv", NODE_COLUMNS)

    write_summary(
        posts_df=posts_df,
        top_sources=top_sources,
        raw_reposts=raw_reposts,
        clean_reposts_df=clean_export_df,
        edges_df=edges_df,
        nodes_df=nodes_df,
        failures=failures,
        used_manual=used_manual,
    )

    print("[完成] 微博传播链数据处理结束。")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="微博传播链采集与传播网络数据生成脚本。只采集正常可访问的公开样本数据。"
    )
    parser.add_argument("--posts", default=INPUT_POSTS, help="微博主帖输入文件，默认 weibo_posts.csv")
    parser.add_argument("--manual", default=MANUAL_REPOSTS, help="手动转发兜底文件，默认 manual_reposts.csv")
    parser.add_argument("--top-n", type=int, default=TOP_N_SOURCE_POSTS, help="筛选核心传播源数量，默认 20")
    parser.add_argument(
        "--max-reposts",
        type=int,
        default=MAX_REPOSTS_PER_POST,
        help="每条微博最多采集转发数，默认 200",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="翻页/滚动间隔秒数，默认 3 秒",
    )
    parser.add_argument("--headless", action="store_true", help="无头浏览器模式，不方便手动登录")
    parser.add_argument("--no-auto", action="store_true", help="跳过自动采集，仅生成主帖筛选和已有手动数据结果")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        run_pipeline(args)
    except KeyboardInterrupt:
        print("\n[中止] 用户手动中止。已生成的文件会保留。")
        sys.exit(130)
    except Exception as exc:
        print(f"[错误] 脚本运行失败：{exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
