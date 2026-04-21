# -*- coding: utf-8 -*-
"""
ICAS 分析结果本地缓存 (SQLite)

缓存策略:
  - 以 转录文本+教案文本 的 SHA256 哈希作为匹配键
  - 内容不变直接读缓存，内容有修改自动重新分析
  - 核心分析(core)和扩展分析(extended)分别缓存

用法:
  from icas_cache import get_cached_core, save_cached_core, ...
"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path

# 数据库文件位于 data/ 目录
DB_PATH = Path(__file__).parent.parent / "data" / "icas_cache.db"


def _get_conn():
    """获取数据库连接，自动建表"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS core_cache (
            cache_key    TEXT PRIMARY KEY,
            folder_name  TEXT,
            trans_hash   TEXT,
            design_hash  TEXT,
            full_data    TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_sec REAL
        );
        CREATE TABLE IF NOT EXISTS extended_cache (
            cache_key      TEXT PRIMARY KEY,
            folder_name    TEXT,
            trans_hash     TEXT,
            extended_data  TEXT,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_sec   REAL
        );
    """)
    conn.commit()
    return conn


def _sha256(text: str) -> str:
    """计算文本的 SHA256 哈希"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ─── 公开 API ─────────────────────────────────────────


def make_cache_key(transcription_text: str, design_text: str = "") -> str:
    """生成缓存键: sha256(转录) + '::' + sha256(教案)"""
    t_hash = _sha256(transcription_text)
    d_hash = _sha256(design_text) if design_text else _sha256("")
    return f"{t_hash}::{d_hash}"


def make_extended_cache_key(transcription_text: str) -> str:
    """扩展分析缓存键: 仅用转录哈希（扩展分析不依赖教案）"""
    return _sha256(transcription_text)


def get_cached_core(transcription_text: str, design_text: str = ""):
    """
    查询核心分析缓存。
    命中返回 (report_data dict, meta dict)，未命中返回 None
    """
    cache_key = make_cache_key(transcription_text, design_text)
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT full_data, folder_name, created_at, duration_sec FROM core_cache WHERE cache_key=?",
            (cache_key,)
        ).fetchone()
        if row:
            return json.loads(row["full_data"]), {
                "folder": row["folder_name"],
                "created": row["created_at"],
                "duration": row["duration_sec"],
            }
        return None
    finally:
        conn.close()


def save_cached_core(cache_key, folder_name, transcription_text, design_text,
                     report_data, duration_sec):
    """保存核心分析结果到缓存"""
    t_hash = _sha256(transcription_text)
    d_hash = _sha256(design_text) if design_text else _sha256("")
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO core_cache
               (cache_key, folder_name, trans_hash, design_hash, full_data, duration_sec)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (cache_key, folder_name, t_hash, d_hash,
             json.dumps(report_data, ensure_ascii=False), duration_sec)
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_extended(transcription_text: str):
    """
    查询扩展分析缓存。
    命中返回 (extended_data dict, meta dict)，未命中返回 None
    """
    cache_key = make_extended_cache_key(transcription_text)
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT extended_data, folder_name, created_at, duration_sec FROM extended_cache WHERE cache_key=?",
            (cache_key,)
        ).fetchone()
        if row:
            return json.loads(row["extended_data"]), {
                "folder": row["folder_name"],
                "created": row["created_at"],
                "duration": row["duration_sec"],
            }
        return None
    finally:
        conn.close()


def save_cached_extended(cache_key, folder_name, transcription_text,
                         extended_data, duration_sec):
    """保存扩展分析结果到缓存"""
    t_hash = _sha256(transcription_text)
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO extended_cache
               (cache_key, folder_name, trans_hash, extended_data, duration_sec)
               VALUES (?, ?, ?, ?, ?)""",
            (cache_key, folder_name, t_hash,
             json.dumps(extended_data, ensure_ascii=False), duration_sec)
        )
        conn.commit()
    finally:
        conn.close()


def list_cache():
    """列出所有缓存条目，返回 list of dict"""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT 'core' AS type, folder_name, trans_hash, created_at, duration_sec
            FROM core_cache
            UNION ALL
            SELECT 'extended' AS type, folder_name, trans_hash, created_at, duration_sec
            FROM extended_cache
            ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def clear_cache(folder_name=None):
    """
    清除缓存。
    folder_name=None: 清除全部
    folder_name=str: 仅清除指定文件夹
    返回删除的记录数
    """
    conn = _get_conn()
    try:
        if folder_name:
            c1 = conn.execute("DELETE FROM core_cache WHERE folder_name=?", (folder_name,))
            c2 = conn.execute("DELETE FROM extended_cache WHERE folder_name=?", (folder_name,))
            conn.commit()
            return c1.rowcount + c2.rowcount
        else:
            c1 = conn.execute("DELETE FROM core_cache")
            c2 = conn.execute("DELETE FROM extended_cache")
            conn.commit()
            return c1.rowcount + c2.rowcount
    finally:
        conn.close()


def print_cache_status():
    """打印缓存状态表（用于 --cache-list）"""
    entries = list_cache()
    if not entries:
        print("\n  (缓存为空)")
        return
    print(f"\n  共 {len(entries)} 条缓存记录:")
    print(f"  {'类型':<12} {'文件夹':<20} {'创建时间':<22} {'耗时(秒)':<10}")
    print("  " + "-" * 66)
    for e in entries:
        t = "核心分析" if e["type"] == "core" else "扩展分析"
        print(f"  {t:<12} {e['folder_name']:<20} {e['created']:<22} {e['duration_sec']:<10.1f}")
    print()
