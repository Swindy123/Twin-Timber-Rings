#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目路径：代码在 code/，数据在项目根目录，图表在 figures/。"""

from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
ROOT_DIR = CODE_DIR.parent
DATA_DIR = ROOT_DIR
FIG_DIR = ROOT_DIR / "figures"

FIG_DIR.mkdir(exist_ok=True)
