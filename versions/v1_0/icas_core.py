# -*- coding: utf-8 -*-

"""
ICAS v1.0 核心模块兼容层。

历史文档中 v1.0 的核心模块名为 `icas_core.py`。当前仓库主线中的
实现已经迁移到 `src/icas_core.py`，这里保留同名入口并显式转发。
"""

import importlib.util
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

_SPEC = importlib.util.spec_from_file_location("_icas_core_src", SRC_DIR / "icas_core.py")
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"无法加载源模块: {SRC_DIR / 'icas_core.py'}")

_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

analyze_classroom = _MODULE.analyze_classroom
generate_ultimate_html = _MODULE.generate_ultimate_html
read_excel_transcription = _MODULE.read_excel_transcription
read_word_document = _MODULE.read_word_document
call_volc_agent = _MODULE.call_volc_agent
clean_json_string = _MODULE.clean_json_string

BASE_URL = _MODULE.BASE_URL
MODEL_NAME = _MODULE.MODEL_NAME
