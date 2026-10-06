from datetime import date
from .db import init, connect, mark_notification
from .telegram import send, callback_button_row
from config import DEADLINE_DAYS

def run():
    init()
    today=date.today()
    with connect() as con:
        rows=con.execute("""
          SELECT * FROM opportunities
          WHERE deadline IS NOT NULL
          AND status NOT IN ('ignored','applied')
          ORDER BY deadline
        """).fetchall()

    for r in rows:
        try:
            d=date.fromisoformat(r["deadline"])
        except:
            continue
        days=(d-today).days
        if days in DEADLINE_DAYS and not r["status"] in ("ignored","applied"):
            kind=f"deadline_{days}"
            if mark_notification(r["id"],kind):
                send(
                    f"⏰ DEADLINE ALERT — {days} DAY(S) LEFT\n\n"
                    f"{r['title']}\n"
                    f"{r['organization'] or ''}\n"
                    f"Deadline: {r['deadline']}\n"
                    f"Fit: {r['fit_score']}/100\n"
                    f"{r['official_url'] or r['source_url']}",
                    callback_button_row(r["id"], r["application_url"] or r["official_url"] or r["source_url"])
                )

if __name__ == "__main__":
    run()
