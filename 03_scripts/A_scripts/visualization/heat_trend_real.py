#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 weibo_posts_clean.csv（is_valid=1）主帖互动指标统计传播热度（按 publish_time 聚合到天）。
仅纳入 publish_time 含明确「2025」年份的主帖；不对「05月22日」等无年份时间补全年份。
"""

from __future__ import annotations

import re

import pandas as pd

from paths import ROOT_DIR

POSTS_FILE = ROOT_DIR / "weibo_posts_clean.csv"
OUT_CSV = ROOT_DIR / "heat_trend_real.csv"

DATE_START = pd.Timestamp("2025-07-22")
DATE_END = pd.Timestamp("2025-08-10 23:59:59")

# 2025年07月25日 10:40
CN_2025_DATETIME = re.compile(
    r"2025年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})"
)
# 2025-07-25 10:40:00
ISO_2025_PREFIX = re.compile(r"^2025-\d{2}-\d{2}")


def has_explicit_2025_year(value: object) -> bool:
    """publish_time 是否包含明确 2025 年份。"""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none"}:
        return False
    return bool("2025年" in text or ISO_2025_PREFIX.match(text))


def parse_explicit_2025_time(raw: pd.Series) -> pd.Series:
    """仅解析已含 2025 年份的 publish_time，不做无年份推断。"""
    result = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    text = raw.astype(str)

    for idx, val in text.items():
        if not has_explicit_2025_year(val):
            continue
        m = CN_2025_DATETIME.search(val)
        if m:
            mo, d, h, mi = map(int, m.groups())
            try:
                result.at[idx] = pd.Timestamp(2025, mo, d, h, mi)
            except ValueError:
                pass
            continue
        if ISO_2025_PREFIX.match(val.strip()):
            parsed = pd.to_datetime(val, errors="coerce")
            if pd.notna(parsed) and int(parsed.year) == 2025:
                result.at[idx] = parsed

    return result


def peak_date(counts: pd.Series) -> tuple[str | None, int]:
    """返回峰值日期及对应数量。"""
    if counts.empty:
        return None, 0
    idx = counts.idxmax()
    return idx, int(counts.loc[idx])


def build_heat_trend_real() -> tuple[pd.DataFrame, dict]:
    posts = pd.read_csv(POSTS_FILE, encoding="utf-8-sig")
    posts = posts.loc[posts["is_valid"] == 1].copy()
    for col in ("comment_count", "repost_count"):
        posts[col] = pd.to_numeric(posts[col], errors="coerce").fillna(0).astype(int)

    explicit_mask = posts["publish_time"].apply(has_explicit_2025_year)
    posts_explicit = posts.loc[explicit_mask]
    pub_dt = parse_explicit_2025_time(posts_explicit["publish_time"])

    in_window = pub_dt.notna() & (pub_dt >= DATE_START) & (pub_dt <= DATE_END)
    sub = posts_explicit.loc[in_window].copy()
    sub["_pub_dt"] = pub_dt[in_window]
    sub["_date"] = sub["_pub_dt"].dt.strftime("%Y-%m-%d")

    daily = (
        sub.groupby("_date", sort=True)
        .agg(
            post_count=("id", "count"),
            comment_count=("comment_count", "sum"),
            repost_count=("repost_count", "sum"),
        )
        .astype(int)
    )

    all_dates = pd.date_range(DATE_START.normalize(), DATE_END.normalize(), freq="D")
    heat = pd.DataFrame({"date": all_dates.strftime("%Y-%m-%d")})
    heat = heat.merge(daily.reset_index().rename(columns={"_date": "date"}), on="date", how="left")
    for col in ("post_count", "comment_count", "repost_count"):
        heat[col] = heat[col].fillna(0).astype(int)

    post_peak_date, post_peak_val = peak_date(heat.set_index("date")["post_count"])
    comment_peak_date, comment_peak_val = peak_date(heat.set_index("date")["comment_count"])
    repost_peak_date, repost_peak_val = peak_date(heat.set_index("date")["repost_count"])

    stats = {
        "window": f"{DATE_START.strftime('%Y-%m-%d')} ~ {DATE_END.strftime('%Y-%m-%d')}",
        "posts_total": int(len(posts)),
        "posts_valid": int(len(posts)),
        "posts_explicit_2025": int(explicit_mask.sum()),
        "posts_excluded_no_year": int((~explicit_mask).sum()),
        "posts_in_window": int(len(sub)),
        "posts_explicit_outside_window": int(explicit_mask.sum() - len(sub)),
        "post_peak_date": post_peak_date,
        "post_peak_count": post_peak_val,
        "comment_peak_date": comment_peak_date,
        "comment_peak_count": comment_peak_val,
        "repost_peak_date": repost_peak_date,
        "repost_peak_count": repost_peak_val,
    }
    return heat, stats


def main() -> None:
    heat, stats = build_heat_trend_real()
    heat.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"已输出: {OUT_CSV}（{len(heat)} 天）")
    print(f"窗口: {stats['window']}")
    print(f"有效主帖（is_valid=1）: {stats['posts_valid']}，含明确2025年: {stats['posts_explicit_2025']}")
    print(f"排除无年份时间: {stats['posts_excluded_no_year']} 条")
    print(f"窗口内纳入统计: {stats['posts_in_window']} 条")
    print(f"发帖峰值: {stats['post_peak_date']} ({stats['post_peak_count']})")
    print(f"评论互动峰值: {stats['comment_peak_date']} ({stats['comment_peak_count']:,})")
    print(f"转发互动峰值: {stats['repost_peak_date']} ({stats['repost_peak_count']:,})")


if __name__ == "__main__":
    main()
