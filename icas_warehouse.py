# -*- coding: utf-8 -*-
"""
ICAS 数据仓库层
将分析结果按学校/教师/课次维度结构化存储，支持纵向查询。

设计原则：
  - 不改动 icas_cache.py 的缓存逻辑，两套机制并行
  - cache 负责防重复分析，warehouse 负责维度聚合和纵向追踪
  - 关键数值指标冗余存储在 lessons 表，避免每次解析 JSON
"""

import json
import sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent / "icas_cache.db"


def _get_conn():
    """获取数据库连接，自动建表"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    return conn


def _init_schema(conn):
    """创建数据仓库维度表（如不存在）"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schools (
            school_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            school_id   INTEGER REFERENCES schools(school_id),
            subject     TEXT,
            grade       TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, school_id)
        );

        CREATE TABLE IF NOT EXISTS lessons (
            lesson_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id        INTEGER REFERENCES teachers(teacher_id),
            school_id         INTEGER REFERENCES schools(school_id),
            folder_name       TEXT,
            lesson_date       DATE,
            lesson_title      TEXT,
            subject           TEXT,
            grade             TEXT,
            core_cache_key    TEXT,
            extended_cache_key TEXT,
            -- 五维雷达 (0-100)
            radar_logic       REAL,
            radar_interaction REAL,
            radar_questioning REAL,
            radar_support     REAL,
            radar_management  REAL,
            -- S-T 分析
            rt_value          REAL,
            ch_value          REAL,
            -- Bloom 认知层次 (各层提问数量)
            bloom_memory      INTEGER DEFAULT 0,
            bloom_understand  INTEGER DEFAULT 0,
            bloom_apply       INTEGER DEFAULT 0,
            bloom_analyze     INTEGER DEFAULT 0,
            bloom_evaluate    INTEGER DEFAULT 0,
            bloom_create      INTEGER DEFAULT 0,
            -- Hattie 反馈 (各层级数量)
            hattie_task       INTEGER DEFAULT 0,
            hattie_process    INTEGER DEFAULT 0,
            hattie_self       INTEGER DEFAULT 0,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_lessons_teacher ON lessons(teacher_id);
        CREATE INDEX IF NOT EXISTS idx_lessons_school ON lessons(school_id);
        CREATE INDEX IF NOT EXISTS idx_lessons_date ON lessons(lesson_date);
    """)
    conn.commit()


# ─── 维度管理 ─────────────────────────────────────────


def ensure_school(name: str) -> int:
    """确保学校记录存在，返回 school_id"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT school_id FROM schools WHERE name=?", (name,)).fetchone()
        if row:
            return row["school_id"]
        cur = conn.execute("INSERT INTO schools (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def ensure_teacher(name: str, school_id: int, subject: str = None, grade: str = None) -> int:
    """确保教师记录存在，返回 teacher_id"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT teacher_id FROM teachers WHERE name=? AND school_id=?",
            (name, school_id)
        ).fetchone()
        if row:
            # 如果有新信息，更新
            if subject or grade:
                conn.execute(
                    "UPDATE teachers SET subject=COALESCE(?,subject), grade=COALESCE(?,grade) WHERE teacher_id=?",
                    (subject, grade, row["teacher_id"])
                )
                conn.commit()
            return row["teacher_id"]
        cur = conn.execute(
            "INSERT INTO teachers (name, school_id, subject, grade) VALUES (?, ?, ?, ?)",
            (name, school_id, subject, grade)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_schools():
    """列出所有学校"""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT s.school_id, s.name,
                   COUNT(DISTINCT t.teacher_id) AS teacher_count,
                   COUNT(l.lesson_id) AS lesson_count
            FROM schools s
            LEFT JOIN teachers t ON s.school_id = t.school_id
            LEFT JOIN lessons l ON s.school_id = l.school_id
            GROUP BY s.school_id, s.name
            ORDER BY s.name
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_teachers(school_id: int = None):
    """列出教师，可选按学校筛选"""
    conn = _get_conn()
    try:
        if school_id:
            rows = conn.execute("""
                SELECT t.*, s.name AS school_name,
                       COUNT(l.lesson_id) AS lesson_count
                FROM teachers t
                LEFT JOIN schools s ON t.school_id = s.school_id
                LEFT JOIN lessons l ON t.teacher_id = l.teacher_id
                WHERE t.school_id=?
                GROUP BY t.teacher_id
                ORDER BY t.name
            """, (school_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT t.*, s.name AS school_name,
                       COUNT(l.lesson_id) AS lesson_count
                FROM teachers t
                LEFT JOIN schools s ON t.school_id = s.school_id
                LEFT JOIN lessons l ON t.teacher_id = l.teacher_id
                GROUP BY t.teacher_id
                ORDER BY t.name
            """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── 数据写入 ─────────────────────────────────────────


def _extract_indicators(core_data: dict, ext_data: dict = None) -> dict:
    """从分析结果 JSON 中提取关键数值指标"""
    indicators = {}

    # 五维雷达
    radar = _dig(core_data, "deep.radar_scores")
    if radar and len(radar) >= 5:
        indicators["radar_logic"] = radar[0]
        indicators["radar_interaction"] = radar[1]
        indicators["radar_questioning"] = radar[2]
        indicators["radar_support"] = radar[3]
        indicators["radar_management"] = radar[4]

    # Bloom
    bloom = _dig(core_data, "deep.bloom_stats")
    if bloom and isinstance(bloom, list):
        bloom_map = {b.get("level", ""): b.get("count", 0) for b in bloom if isinstance(b, dict)}
        indicators["bloom_memory"] = bloom_map.get("记忆", bloom_map.get("记忆", 0))
        indicators["bloom_understand"] = bloom_map.get("理解", 0)
        indicators["bloom_apply"] = bloom_map.get("应用", 0)
        indicators["bloom_analyze"] = bloom_map.get("分析", 0)
        indicators["bloom_evaluate"] = bloom_map.get("评价", 0)
        indicators["bloom_create"] = bloom_map.get("创造", 0)

    # Hattie
    hattie = _dig(core_data, "deep.hattie_stats")
    if hattie and isinstance(hattie, dict):
        indicators["hattie_task"] = hattie.get("task_level", 0)
        indicators["hattie_process"] = hattie.get("process_level", 0)
        indicators["hattie_self"] = hattie.get("self_level", 0)

    # S-T 分析 (来自扩展数据)
    if ext_data:
        rt = _dig(ext_data, "st_analysis.rt")
        ch = _dig(ext_data, "st_analysis.ch")
        if rt is not None:
            indicators["rt_value"] = rt
        if ch is not None:
            indicators["ch_value"] = ch

    return indicators


def save_lesson(school_name: str, teacher_name: str,
                folder_name: str = None, lesson_date: str = None,
                lesson_title: str = None, subject: str = None, grade: str = None,
                core_data: dict = None, ext_data: dict = None,
                core_cache_key: str = None, extended_cache_key: str = None):
    """
    保存一次课的分析结果到数据仓库。

    自动创建学校/教师记录，提取关键指标写入 lessons 表。
    如果同一 teacher + folder_name 已存在，则更新。
    """
    conn = _get_conn()
    try:
        school_id = ensure_school(school_name)
        teacher_id = ensure_teacher(teacher_name, school_id, subject, grade)

        indicators = _extract_indicators(core_data or {}, ext_data)

        # 检查是否已有同 teacher + folder 的记录
        existing = conn.execute(
            "SELECT lesson_id FROM lessons WHERE teacher_id=? AND folder_name=?",
            (teacher_id, folder_name)
        ).fetchone()

        fields = {
            "teacher_id": teacher_id,
            "school_id": school_id,
            "folder_name": folder_name,
            "lesson_date": lesson_date,
            "lesson_title": lesson_title,
            "subject": subject,
            "grade": grade,
            "core_cache_key": core_cache_key,
            "extended_cache_key": extended_cache_key,
        }
        fields.update(indicators)

        if existing:
            sets = ", ".join(f"{k}=?" for k in fields)
            vals = list(fields.values()) + [existing["lesson_id"]]
            conn.execute(f"UPDATE lessons SET {sets} WHERE lesson_id=?", vals)
        else:
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(f"INSERT INTO lessons ({cols}) VALUES ({placeholders})",
                         list(fields.values()))

        conn.commit()
        return True
    except Exception as e:
        print(f"[仓库] 写入失败: {e}")
        return False
    finally:
        conn.close()


# ─── 纵向查询 ─────────────────────────────────────────


def get_growth_data(teacher_id: int) -> list:
    """
    获取某教师的时间序列数据。
    返回按 lesson_date 排序的课次列表，每条包含所有指标。
    """
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT l.*, t.name AS teacher_name, s.name AS school_name
            FROM lessons l
            JOIN teachers t ON l.teacher_id = t.teacher_id
            JOIN schools s ON l.school_id = s.school_id
            WHERE l.teacher_id=?
            ORDER BY l.lesson_date, l.lesson_id
        """, (teacher_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_school_overview(school_id: int) -> dict:
    """获取学校级汇总"""
    conn = _get_conn()
    try:
        # 基本信息
        school = conn.execute("SELECT * FROM schools WHERE school_id=?", (school_id,)).fetchone()
        if not school:
            return None

        # 教师列表及各维度均值
        teachers = conn.execute("""
            SELECT t.teacher_id, t.name, t.subject, t.grade,
                   COUNT(l.lesson_id) AS lesson_count,
                   ROUND(AVG(l.radar_logic), 1) AS avg_logic,
                   ROUND(AVG(l.radar_interaction), 1) AS avg_interaction,
                   ROUND(AVG(l.radar_questioning), 1) AS avg_questioning,
                   ROUND(AVG(l.radar_support), 1) AS avg_support,
                   ROUND(AVG(l.radar_management), 1) AS avg_management,
                   ROUND(AVG(l.rt_value), 2) AS avg_rt,
                   ROUND(AVG(l.ch_value), 2) AS avg_ch
            FROM teachers t
            LEFT JOIN lessons l ON t.teacher_id = l.teacher_id
            WHERE t.school_id=?
            GROUP BY t.teacher_id
            ORDER BY t.name
        """, (school_id,)).fetchall()

        # 全校各维度均值
        overall = conn.execute("""
            SELECT
                ROUND(AVG(radar_logic), 1) AS avg_logic,
                ROUND(AVG(radar_interaction), 1) AS avg_interaction,
                ROUND(AVG(radar_questioning), 1) AS avg_questioning,
                ROUND(AVG(radar_support), 1) AS avg_support,
                ROUND(AVG(radar_management), 1) AS avg_management
            FROM lessons
            WHERE school_id=?
        """, (school_id,)).fetchone()

        # 按学科汇总
        by_subject = conn.execute("""
            SELECT subject,
                   COUNT(*) AS lesson_count,
                   ROUND(AVG(radar_logic), 1) AS avg_logic,
                   ROUND(AVG(radar_interaction), 1) AS avg_interaction,
                   ROUND(AVG(radar_questioning), 1) AS avg_questioning,
                   ROUND(AVG(radar_support), 1) AS avg_support,
                   ROUND(AVG(radar_management), 1) AS avg_management
            FROM lessons
            WHERE school_id=?
            GROUP BY subject
        """, (school_id,)).fetchall()

        return {
            "school": dict(school),
            "teachers": [dict(r) for r in teachers],
            "overall": dict(overall) if overall else {},
            "by_subject": [dict(r) for r in by_subject],
        }
    finally:
        conn.close()


def get_all_lessons_for_report(school_id: int = None) -> list:
    """
    获取所有课次数据（用于学校级时序图表）。
    返回按日期排序的课次列表。
    """
    conn = _get_conn()
    try:
        if school_id:
            rows = conn.execute("""
                SELECT l.*, t.name AS teacher_name, t.subject AS teacher_subject
                FROM lessons l
                JOIN teachers t ON l.teacher_id = t.teacher_id
                WHERE l.school_id=?
                ORDER BY l.lesson_date, l.lesson_id
            """, (school_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT l.*, t.name AS teacher_name, t.subject AS teacher_subject,
                       s.name AS school_name
                FROM lessons l
                JOIN teachers t ON l.teacher_id = t.teacher_id
                JOIN schools s ON l.school_id = s.school_id
                ORDER BY l.lesson_date, l.lesson_id
            """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_teacher_comparison(teacher_ids: list) -> list:
    """多教师对比数据"""
    if not teacher_ids:
        return []
    placeholders = ",".join("?" for _ in teacher_ids)
    conn = _get_conn()
    try:
        rows = conn.execute(f"""
            SELECT t.name AS teacher_name, t.subject,
                   COUNT(l.lesson_id) AS lesson_count,
                   ROUND(AVG(l.radar_logic), 1) AS avg_logic,
                   ROUND(AVG(l.radar_interaction), 1) AS avg_interaction,
                   ROUND(AVG(l.radar_questioning), 1) AS avg_questioning,
                   ROUND(AVG(l.radar_support), 1) AS avg_support,
                   ROUND(AVG(l.radar_management), 1) AS avg_management,
                   ROUND(AVG(l.rt_value), 2) AS avg_rt,
                   ROUND(AVG(l.ch_value), 2) AS avg_ch
            FROM teachers t
            LEFT JOIN lessons l ON t.teacher_id = l.teacher_id
            WHERE t.teacher_id IN ({placeholders})
            GROUP BY t.teacher_id
        """, teacher_ids).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── 工具函数 ─────────────────────────────────────────


def _dig(data: dict, path: str):
    """按点号路径取嵌套值"""
    keys = path.split(".")
    obj = data
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            return None
    return obj


def print_warehouse_status():
    """打印数据仓库状态"""
    schools = list_schools()
    if not schools:
        print("\n  (数据仓库为空，尚无学校/教师/课次数据)")
        return

    print(f"\n  ┌─ 数据仓库状态 ─────────────────────────────────┐")
    for s in schools:
        print(f"  │ 学校: {s['name']}  (教师{s['teacher_count']}人, 课次{s['lesson_count']}节)")
        teachers = list_teachers(s["school_id"])
        for t in teachers:
            print(f"  │   ├─ {t['name']}  ({t.get('subject','') or '未设学科'}, {t['lesson_count']}节课)")
    print(f"  └──────────────────────────────────────────────┘")
