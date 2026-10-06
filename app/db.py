import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB = Path("gravik.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    organization TEXT,
    category TEXT,
    source_name TEXT,
    source_url TEXT,
    application_url TEXT,
    official_url TEXT,
    description TEXT,
    eligibility TEXT,
    eligibility_status TEXT DEFAULT 'unclear',
    eligibility_reasons TEXT,
    deadline TEXT,
    event_date TEXT,
    duration TEXT,
    location_mode TEXT,
    cost TEXT,
    stipend TEXT,
    certificate TEXT,
    participation TEXT,
    fit_score REAL DEFAULT 0,
    trust_score REAL DEFAULT 0,
    status TEXT DEFAULT 'new',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_changed TEXT,
    content_hash TEXT,
    deadline_hash TEXT
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    UNIQUE(opportunity_id, kind)
);

CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,
    status TEXT,
    items_found INTEGER DEFAULT 0,
    error TEXT,
    ran_at TEXT NOT NULL
);
"""

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init():
    with connect() as con:
        con.executescript(SCHEMA)
        # Safe migrations for databases created by older V2 builds.
        for sql in (
            "ALTER TABLE opportunities ADD COLUMN eligibility_status TEXT DEFAULT 'unclear'",
            "ALTER TABLE opportunities ADD COLUMN eligibility_reasons TEXT",
        ):
            try:
                con.execute(sql)
            except sqlite3.OperationalError:
                pass

def now():
    return datetime.now(timezone.utc).isoformat()

def record_source_run(source_id, status, items_found=0, error=None):
    with connect() as con:
        con.execute(
            "INSERT INTO source_runs(source_id,status,items_found,error,ran_at) VALUES(?,?,?,?,?)",
            (source_id,status,items_found,error,now())
        )

def upsert(item):
    with connect() as con:
        existing = con.execute(
            "SELECT id,content_hash,deadline_hash FROM opportunities WHERE fingerprint=?",
            (item["fingerprint"],)
        ).fetchone()

        if existing:
            changed = (
                existing["content_hash"] != item.get("content_hash")
                or existing["deadline_hash"] != item.get("deadline_hash")
            )
            con.execute("""
              UPDATE opportunities SET
              title=?,organization=?,category=?,source_name=?,source_url=?,
              application_url=?,official_url=?,description=?,eligibility=?,eligibility_status=?,eligibility_reasons=?,
              deadline=?,event_date=?,duration=?,location_mode=?,cost=?,stipend=?,
              certificate=?,participation=?,fit_score=?,trust_score=?,
              last_seen=?,last_changed=?,content_hash=?,deadline_hash=?
              WHERE fingerprint=?
            """, (
                item["title"],item.get("organization"),item.get("category"),
                item.get("source_name"),item.get("source_url"),
                item.get("application_url"),item.get("official_url"),
                item.get("description"),item.get("eligibility"),item.get("eligibility_status","unclear"),item.get("eligibility_reasons"),
                item.get("deadline"),item.get("event_date"),item.get("duration"),
                item.get("location_mode"),item.get("cost"),item.get("stipend"),
                item.get("certificate"),item.get("participation"),
                item.get("fit_score",0),item.get("trust_score",0),
                now(), now() if changed else None,
                item.get("content_hash"),item.get("deadline_hash"),
                item["fingerprint"]
            ))
            return existing["id"], "updated" if changed else "seen"

        cur = con.execute("""
          INSERT INTO opportunities(
            fingerprint,title,organization,category,source_name,source_url,
            application_url,official_url,description,eligibility,eligibility_status,eligibility_reasons,deadline,
            event_date,duration,location_mode,cost,stipend,certificate,
            participation,fit_score,trust_score,first_seen,last_seen,
            last_changed,content_hash,deadline_hash
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            item["fingerprint"],item["title"],item.get("organization"),
            item.get("category"),item.get("source_name"),item.get("source_url"),
            item.get("application_url"),item.get("official_url"),
            item.get("description"),item.get("eligibility"),item.get("eligibility_status","unclear"),item.get("eligibility_reasons"),item.get("deadline"),
            item.get("event_date"),item.get("duration"),item.get("location_mode"),
            item.get("cost"),item.get("stipend"),item.get("certificate"),
            item.get("participation"),item.get("fit_score",0),
            item.get("trust_score",0),now(),now(),now(),
            item.get("content_hash"),item.get("deadline_hash")
        ))
        return cur.lastrowid, "new"

def action(opportunity_id, action_name):
    with connect() as con:
        con.execute(
            "INSERT INTO actions(opportunity_id,action,created_at) VALUES(?,?,?)",
            (opportunity_id,action_name,now())
        )
        if action_name == "applied":
            con.execute(
                "UPDATE opportunities SET status='applied' WHERE id=?",
                (opportunity_id,)
            )
        elif action_name == "ignore":
            con.execute(
                "UPDATE opportunities SET status='ignored' WHERE id=?",
                (opportunity_id,)
            )
        elif action_name == "save":
            con.execute(
                "UPDATE opportunities SET status='saved' WHERE id=?",
                (opportunity_id,)
            )


def get_opportunity(opportunity_id):
    with connect() as con:
        return con.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()

def recent_actions(limit=500):
    with connect() as con:
        return con.execute(
            "SELECT o.*, a.action, a.created_at FROM actions a "
            "JOIN opportunities o ON o.id=a.opportunity_id "
            "ORDER BY a.created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()

def candidates(limit=100):
    with connect() as con:
        return con.execute(
            "SELECT * FROM opportunities "
            "WHERE status NOT IN ('ignored','applied') "
            "AND (deadline IS NULL OR deadline = '' OR deadline >= date('now')) "
            "AND NOT EXISTS (SELECT 1 FROM notifications n WHERE n.opportunity_id=opportunities.id AND n.kind='daily') "
            "ORDER BY fit_score DESC, first_seen DESC LIMIT ?",
            (limit,)
        ).fetchall()

def mark_notification(opportunity_id, kind):
    with connect() as con:
        try:
            con.execute(
                "INSERT INTO notifications(opportunity_id,kind,sent_at) VALUES(?,?,?)",
                (opportunity_id,kind,now())
            )
            return True
        except sqlite3.IntegrityError:
            return False

def notified(opportunity_id, kind):
    with connect() as con:
        return con.execute(
            "SELECT 1 FROM notifications WHERE opportunity_id=? AND kind=?",
            (opportunity_id,kind)
        ).fetchone() is not None


def get_state(key, default=None):
    with connect() as con:
        row = con.execute("SELECT value FROM bot_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_state(key, value):
    with connect() as con:
        con.execute("INSERT INTO bot_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
