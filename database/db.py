import uuid
import json
from datetime import date, timedelta
from typing import Optional
import mysql.connector
from mysql.connector import connection
from config import MYSQL_CONFIG

CREATE_DB_SQL = "CREATE DATABASE IF NOT EXISTS ai_fitness_coach CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR(36) PRIMARY KEY,
    height_cm FLOAT,
    weight_kg FLOAT,
    birth_date DATE,
    training_start_date DATE,
    squat_1rm FLOAT,
    bench_1rm FLOAT,
    deadlift_1rm FLOAT,
    days_per_week INT,
    current_goal VARCHAR(20) DEFAULT 'hypertrophy',
    macro_phase VARCHAR(20) DEFAULT 'accumulation',
    macro_week INT DEFAULT 1,
    macro_start_date DATE,
    macro_plan_json TEXT,
    plan_stale BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS workout_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    log_date DATE,
    sleep_score INT,
    stress_score INT,
    fatigue_score INT,
    pain_areas TEXT,
    planned_json TEXT,
    actual_json TEXT,
    completion_rate FLOAT,
    is_override BOOLEAN DEFAULT FALSE,
    replan_count INT DEFAULT 0,
    note TEXT DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS prs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    exercise_name VARCHAR(100),
    weight_kg FLOAT,
    reps INT,
    pr_date DATE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS nutrition_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    log_date DATE,
    protein_g FLOAT,
    note VARCHAR(500),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

def get_connection(use_database: bool = False) -> connection.MySQLConnection:
    config = {
        "host": MYSQL_CONFIG["host"],
        "port": MYSQL_CONFIG["port"],
        "user": MYSQL_CONFIG["user"],
        "password": MYSQL_CONFIG["password"],
    }
    if use_database:
        config["database"] = MYSQL_CONFIG["database"]
    conn = mysql.connector.connect(**config)
    return conn

def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(CREATE_DB_SQL)
    except Exception as e:
        # Managed MySQL providers often require creating the database in the
        # dashboard and do not grant CREATE DATABASE permission to app users.
        print(f"[db.init_db] CREATE DATABASE skipped or failed: {e}")
    cursor.close()
    conn.database = MYSQL_CONFIG["database"]
    for statement in CREATE_TABLES_SQL.split(";"):
        stmt = statement.strip()
        if stmt:
            cursor = conn.cursor()
            cursor.execute(stmt)
            cursor.close()
    # 确保所有新增字段存在（给已有数据库打补丁）
    # 注：不使用 IF NOT EXISTS 语法（部分 MySQL 版本不支持），改用 SHOW COLUMNS 检测
    patch_columns = [
        ("workout_logs", "note", "ALTER TABLE workout_logs ADD COLUMN note TEXT DEFAULT NULL"),
        ("workout_logs", "pain_areas", "ALTER TABLE workout_logs ADD COLUMN pain_areas TEXT"),
        ("workout_logs", "replan_count", "ALTER TABLE workout_logs ADD COLUMN replan_count INT DEFAULT 0"),
        ("user_profiles", "birth_date", "ALTER TABLE user_profiles ADD COLUMN birth_date DATE"),
        ("user_profiles", "training_start_date", "ALTER TABLE user_profiles ADD COLUMN training_start_date DATE"),
        ("user_profiles", "macro_plan_json", "ALTER TABLE user_profiles ADD COLUMN macro_plan_json TEXT"),
        ("user_profiles", "macro_phase", "ALTER TABLE user_profiles ADD COLUMN macro_phase VARCHAR(20) DEFAULT 'accumulation'"),
        ("user_profiles", "macro_week", "ALTER TABLE user_profiles ADD COLUMN macro_week INT DEFAULT 1"),
        ("user_profiles", "macro_start_date", "ALTER TABLE user_profiles ADD COLUMN macro_start_date DATE"),
        ("user_profiles", "plan_stale", "ALTER TABLE user_profiles ADD COLUMN plan_stale BOOLEAN DEFAULT FALSE"),
    ]
    for table, column, sql in patch_columns:
        try:
            cursor = conn.cursor()
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (column,))
            if not cursor.fetchone():
                cursor.execute(sql)
            cursor.close()
        except Exception:
            pass
    conn.close()

# ─── 推算函数 ──────────────────────────────────────────

def calculate_age(birth_date_str: str) -> int:
    """根据出生日期推算当前年龄"""
    birth = date.fromisoformat(birth_date_str)
    today = date.today()
    age = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        age -= 1
    return age

def calculate_training_years(start_date_str: str) -> float:
    """根据开始训练时间推算训练年限，保留一位小数"""
    start = date.fromisoformat(start_date_str)
    today = date.today()
    days = (today - start).days
    return round(days / 365.25, 1)

# ─── 用户 ────────────────────────────────────────────────

def get_user(user_id: str) -> Optional[dict]:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

def save_user(user_id: str, name: str) -> None:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (id, name) VALUES (%s, %s) ON DUPLICATE KEY UPDATE name = %s",
        (user_id, name, name),
    )
    conn.commit()
    cursor.close()
    conn.close()

# ─── 档案 ────────────────────────────────────────────────

def get_user_profile(user_id: str) -> Optional[dict]:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM user_profiles WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

def save_user_profile(user_id: str, profile: dict) -> None:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO user_profiles
           (user_id, height_cm, weight_kg, birth_date, training_start_date,
            squat_1rm, bench_1rm, deadlift_1rm, days_per_week, current_goal)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
           height_cm = VALUES(height_cm), weight_kg = VALUES(weight_kg),
           birth_date = VALUES(birth_date),
           training_start_date = VALUES(training_start_date),
           squat_1rm = VALUES(squat_1rm), bench_1rm = VALUES(bench_1rm),
           deadlift_1rm = VALUES(deadlift_1rm),
           days_per_week = VALUES(days_per_week), current_goal = VALUES(current_goal)""",
        (
            user_id,
            profile.get("height_cm"),
            profile.get("weight_kg"),
            profile.get("birth_date"),
            profile.get("training_start_date"),
            profile.get("squat_1rm"),
            profile.get("bench_1rm"),
            profile.get("deadlift_1rm"),
            profile.get("days_per_week"),
            profile.get("current_goal", "hypertrophy"),
        ),
    )
    conn.commit()
    cursor.close()
    conn.close()

def update_weight(user_id: str, weight_kg: float) -> None:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE user_profiles SET weight_kg = %s WHERE user_id = %s",
        (weight_kg, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

def update_profile_field(user_id: str, field: str, value: float) -> None:
    """
    更新 user_profiles 表的指定字段。
    field 只允许白名单内的字段名，防止 SQL 注入。
    """
    ALLOWED_FIELDS = {
        "squat_1rm", "bench_1rm", "deadlift_1rm",
        "weight_kg", "height_cm",
    }
    if field not in ALLOWED_FIELDS:
        raise ValueError(f"不允许的字段名：{field}")
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE user_profiles SET {field} = %s WHERE user_id = %s",
        (value, user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

def get_macro_plan_raw(user_id: str) -> str | None:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT macro_plan_json FROM user_profiles WHERE user_id = %s",
        (user_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row["macro_plan_json"] if row else None


def get_cycle_length(user_id: str) -> int:
    """
    从 macro_plan_json 里读取 days 列表长度，
    作为循环周期总天数。
    """
    profile = get_user_profile(user_id)
    if not profile:
        return 7
    macro_json = profile.get("macro_plan_json")
    if not macro_json:
        return 7
    try:
        macro = json.loads(macro_json)
        days = macro.get("days", [])
        return len(days) if days else 7
    except Exception:
        return 7


def get_today_cycle_index(user_id: str) -> int:
    """
    根据 macro_start_date 和今天的日期，
    计算今天是循环周期的第几天（从0开始）。
    """
    from datetime import date
    profile = get_user_profile(user_id)
    if not profile:
        return 0
    start_date_str = profile.get("macro_start_date")
    if not start_date_str:
        return 0
    try:
        if isinstance(start_date_str, str):
            start_date = date.fromisoformat(start_date_str)
        else:
            start_date = start_date_str
        today = date.today()
        days_elapsed = (today - start_date).days
        cycle_length = get_cycle_length(user_id)
        return days_elapsed % cycle_length
    except Exception:
        return 0


def is_rest_day(user_id: str) -> bool:
    """
    根据今日循环索引，判断今天是训练日还是休息日。
    休息日的 day_name 是「休息」且 exercises 为空。
    """
    profile = get_user_profile(user_id)
    if not profile:
        return False
    macro_json = profile.get("macro_plan_json")
    if not macro_json:
        return False
    try:
        macro = json.loads(macro_json)
        days = macro.get("days", [])
        if not days:
            return False
        idx = get_today_cycle_index(user_id)
        today_day = days[idx]
        day_name = today_day.get("day_name", "")
        exercises = today_day.get("exercises", [])
        return day_name == "休息" or len(exercises) == 0
    except Exception:
        return False


def update_macro_plan(user_id: str, phase: str, week: int, plan_json: str, start_date: str) -> None:
    print(f"[db.update_macro_plan] 开始执行: user_id={user_id}, phase={phase}, week={week}")
    print(f"[db.update_macro_plan] plan_json 长度={len(plan_json) if plan_json else 0}")
    try:
        conn = get_connection()
        conn.database = MYSQL_CONFIG["database"]
        print(f"[db.update_macro_plan] 数据库连接成功, database={MYSQL_CONFIG['database']}")
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE user_profiles
               SET macro_phase = %s, macro_week = %s, macro_plan_json = %s,
                   macro_start_date = %s, plan_stale = FALSE
               WHERE user_id = %s""",
            (phase, week, plan_json, start_date, user_id),
        )
        print(f"[db.update_macro_plan] SQL 执行完毕, affected_rows={cursor.rowcount}")
        conn.commit()
        print(f"[db.update_macro_plan] commit 成功")
        cursor.close()
        conn.close()
        print(f"[db.update_macro_plan] 连接已关闭")
    except Exception as e:
        print(f"[db.update_macro_plan] 异常: {e}")
        raise

def mark_plan_stale(user_id: str) -> None:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute("UPDATE user_profiles SET plan_stale = TRUE WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def clear_plan_stale(user_id: str) -> None:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute("UPDATE user_profiles SET plan_stale = FALSE WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

# ─── 日志 ────────────────────────────────────────────────

def get_recent_logs(user_id: str, days: int = 28) -> list[dict]:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor(dictionary=True)
    cutoff = date.today() - timedelta(days=days)
    cursor.execute(
        "SELECT * FROM workout_logs WHERE user_id = %s AND log_date >= %s ORDER BY log_date DESC",
        (user_id, cutoff),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    for row in rows:
        if row.get("log_date"):
            row["log_date"] = str(row["log_date"])
        if row.get("pr_date"):
            row["pr_date"] = str(row["pr_date"])
    if rows:
        print(f"[DEBUG] completion_rate 原始值: {rows[0].get('completion_rate')}")
    return rows


def has_trained_today(user_id: str) -> bool:
    today = str(date.today())
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        """SELECT COUNT(*) FROM workout_logs
           WHERE user_id = %s AND log_date = %s""",
        (user_id, today)
    )
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count > 0


def reset_today_logs(user_id: str) -> None:
    """删除今日训练记录，用于测试重置"""
    today = str(date.today())
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM workout_logs WHERE user_id = %s AND log_date = %s",
        (user_id, today)
    )
    conn.commit()
    cursor.close()
    conn.close()


def save_workout_log(log: dict) -> None:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO workout_logs
           (id, user_id, log_date, sleep_score, stress_score, fatigue_score,
            pain_areas, planned_json, actual_json, completion_rate,
            is_override, replan_count, note)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            log["id"],
            log["user_id"],
            log["log_date"],
            log["sleep_score"],
            log["stress_score"],
            log["fatigue_score"],
            log["pain_areas"],
            log["planned_json"],
            log["actual_json"],
            log["completion_rate"],
            log["is_override"],
            log["replan_count"],
            log.get("note"),
        ),
    )
    conn.commit()
    cursor.close()
    conn.close()

def save_workout_note(log_id: str, note: str) -> None:
    """更新指定日志的备注（按 log_id 精确匹配）"""
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE workout_logs SET note = %s WHERE id = %s",
        (note, log_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

# ─── PR ──────────────────────────────────────────────────

def get_prs(user_id: str) -> list[dict]:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM prs WHERE user_id = %s ORDER BY pr_date DESC",
        (user_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def save_pr(user_id: str, exercise: str, weight: float, reps: int) -> None:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO prs (id, user_id, exercise_name, weight_kg, reps, pr_date) VALUES (%s, %s, %s, %s, %s, %s)",
        (str(uuid.uuid4()), user_id, exercise, weight, reps, str(date.today())),
    )
    conn.commit()
    cursor.close()
    conn.close()

def upsert_pr(user_id: str, exercise: str, weight_kg: float, reps: int) -> None:
    """
    手动录入或更新 PR。
    同一动作只保留最新一条手动录入记录（pr_date = today）。
    如果今天已有记录则更新，没有则插入。
    """
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    today = str(date.today())
    cursor.execute(
        """SELECT id FROM prs
           WHERE user_id = %s
           AND exercise_name = %s
           AND pr_date = %s""",
        (user_id, exercise, today)
    )
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            """UPDATE prs SET weight_kg = %s, reps = %s
               WHERE id = %s""",
            (weight_kg, reps, existing[0])
        )
    else:
        cursor.execute(
            """INSERT INTO prs
               (id, user_id, exercise_name, weight_kg, reps, pr_date)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (str(uuid.uuid4()), user_id, exercise,
             weight_kg, reps, today)
        )
    conn.commit()
    cursor.close()
    conn.close()

def get_pr_trend(user_id: str, exercise: str, weeks: int = 6) -> list[dict]:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor(dictionary=True)
    cutoff = date.today() - timedelta(weeks=weeks)
    cursor.execute(
        "SELECT * FROM prs WHERE user_id = %s AND exercise_name = %s AND pr_date >= %s ORDER BY pr_date ASC",
        (user_id, exercise, cutoff),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_pr_stagnation_weeks(user_id: str, exercise: str) -> int:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT weight_kg, pr_date FROM prs WHERE user_id = %s AND exercise_name = %s ORDER BY pr_date DESC LIMIT 2",
        (user_id, exercise),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    if len(rows) < 2:
        return 0
    if rows[0]["weight_kg"] <= rows[1]["weight_kg"]:
        diff = date.today() - rows[0]["pr_date"]
        return diff.days // 7
    return 0

# ─── 营养 ────────────────────────────────────────────────

def get_today_nutrition(user_id: str) -> Optional[dict]:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM nutrition_logs WHERE user_id = %s AND log_date = %s",
        (user_id, str(date.today())),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

def save_nutrition_log(user_id: str, protein_g: float, note: str) -> None:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO nutrition_logs (id, user_id, log_date, protein_g, note)
           VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE protein_g = VALUES(protein_g), note = VALUES(note)""",
        (str(uuid.uuid4()), user_id, str(date.today()), protein_g, note),
    )
    conn.commit()
    cursor.close()
    conn.close()

# ─── 分析 ────────────────────────────────────────────────

def get_avg_completion_rate(user_id: str, weeks: int = 4) -> float:
    conn = get_connection()
    conn.database = MYSQL_CONFIG["database"]
    cursor = conn.cursor(dictionary=True)
    cutoff = date.today() - timedelta(weeks=weeks)
    cursor.execute(
        "SELECT AVG(completion_rate) as avg_rate FROM workout_logs WHERE user_id = %s AND log_date >= %s",
        (user_id, cutoff),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row["avg_rate"] if row and row["avg_rate"] else 1.0
