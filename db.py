import sqlite3
from datetime import datetime, date, timedelta
from config import DB_PATH


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                app           TEXT    NOT NULL,
                project       TEXT,
                started_at    TEXT    NOT NULL,
                ended_at      TEXT    NOT NULL,
                duration_secs INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_started ON sessions(started_at)")
        conn.commit()


def save_session(app: str, project: str | None, started_at: datetime, ended_at: datetime):
    duration = int((ended_at - started_at).total_seconds())
    if duration < 10:
        return
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sessions (app, project, started_at, ended_at, duration_secs) VALUES (?, ?, ?, ?, ?)",
            (app, project, started_at.isoformat(), ended_at.isoformat(), duration),
        )
        conn.commit()


def get_daily_totals(days: int = 14) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT date(started_at) AS day, SUM(duration_secs) AS total
            FROM sessions
            WHERE date(started_at) >= ?
            GROUP BY day
            ORDER BY day
            """,
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_today_by_app() -> list[dict]:
    today = date.today().isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT app, SUM(duration_secs) AS total
            FROM sessions
            WHERE date(started_at) = ?
            GROUP BY app
            ORDER BY total DESC
            """,
            (today,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_project_totals(days: int = 30) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(project, 'Unknown') AS project, SUM(duration_secs) AS total
            FROM sessions
            WHERE date(started_at) >= ? AND project IS NOT NULL AND project != ''
            GROUP BY project
            ORDER BY total DESC
            LIMIT 20
            """,
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats_summary(days: int = 7) -> dict:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with _conn() as conn:
        total = (
            conn.execute(
                "SELECT SUM(duration_secs) FROM sessions WHERE date(started_at) >= ?",
                (since,),
            ).fetchone()[0]
            or 0
        )
        top_project_row = conn.execute(
            """
            SELECT project FROM sessions
            WHERE date(started_at) >= ? AND project IS NOT NULL AND project != ''
            GROUP BY project
            ORDER BY SUM(duration_secs) DESC
            LIMIT 1
            """,
            (since,),
        ).fetchone()
        days_active = (
            conn.execute(
                "SELECT COUNT(DISTINCT date(started_at)) FROM sessions WHERE date(started_at) >= ?",
                (since,),
            ).fetchone()[0]
            or 0
        )
        streak = _calc_streak(conn)

    return {
        "total_secs": total,
        "top_project": top_project_row[0] if top_project_row else None,
        "days_active": days_active,
        "streak": streak,
    }


def get_projects_timeline(days: int = 30) -> list[dict]:
    """Returns projects with per-day breakdown, sorted by total time desc."""
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT
                project,
                date(started_at) AS day,
                SUM(duration_secs) AS total
            FROM sessions
            WHERE date(started_at) >= ?
              AND project IS NOT NULL AND project != ''
            GROUP BY project, day
            ORDER BY project, day
            """,
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_app_totals(days: int = 30) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT app, SUM(duration_secs) AS total
            FROM sessions
            WHERE date(started_at) >= ?
            GROUP BY app
            ORDER BY total DESC
            """,
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def _calc_streak(conn) -> int:
    rows = conn.execute(
        "SELECT DISTINCT date(started_at) AS day FROM sessions ORDER BY day DESC"
    ).fetchall()
    if not rows:
        return 0
    streak = 0
    expected = date.today()
    for row in rows:
        d = date.fromisoformat(row[0])
        # Allow today OR yesterday as streak start
        if d == expected or (streak == 0 and d == expected - timedelta(days=1)):
            streak += 1
            expected = d - timedelta(days=1)
        else:
            break
    return streak
