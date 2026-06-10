"""C 组传播链：提交包路径（相对 data_collection，不硬编码 D:\\nl）。"""
from __future__ import annotations

from pathlib import Path

# data_collection/C-chenziyi
CHENZIYI_DIR = Path(__file__).resolve().parent
DATA_COLLECTION_DIR = CHENZIYI_DIR.parent
PROJECT_ROOT = DATA_COLLECTION_DIR.parent

DATA_DIR = DATA_COLLECTION_DIR / "data"
C_DATA_DIR = DATA_DIR / "C-data"
C_RECRAWL_DIR = DATA_DIR / "C-recrawl"

SOURCE_PATH = C_DATA_DIR / "top_source_posts.csv"
RECRAWL_DIR = C_RECRAWL_DIR
PROFILE_DIR = PROJECT_ROOT / ".weibo_recrawl_profile"

# 成员 A 主帖（若需重跑 collector）
WEIBO_POSTS_PATH = C_DATA_DIR / "weibo_posts.csv"

# 转发文本补充（可选）
EDATA_REPOST_PATH = C_DATA_DIR / "weibo_reposts_clean_supplement.csv"

FIG_DIR = CHENZIYI_DIR / "figures"
REPORT_DIR = CHENZIYI_DIR
