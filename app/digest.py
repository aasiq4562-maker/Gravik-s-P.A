from .db import init, candidates, mark_notification
from .telegram import send, callback_button_row
from config import DAILY_LIMIT, MIN_FIT_SCORE
from datetime import date, datetime

def digest():
    init()
    rows=[r for r in candidates(100) if r["fit_score"] >= MIN_FIT_SCORE and (r["eligibility_status"] or "unclear") != "not_eligible"]
    rows=rows[:DAILY_LIMIT]

    if not rows:
        send("GRAVIK RADAR\n\nNo new high-signal opportunities today.")
        return

    send(f"GRAVIK OPPORTUNITY RADAR\n{date.today():%d %b %Y}\n\n"
         f"{len(rows)} high-signal opportunities.")

    for r in rows:
        text = (
            f"{r['category'].upper()} — {r['title']}\n"
            f"Organization: {r['organization'] or 'Not stated'}\n"
            f"Fit: {r['fit_score']}/100\n"
            f"Deadline: {r['deadline'] or 'Not stated'}\n"
            f"Mode: {r['location_mode'] or 'Not stated'}\n"
            f"Cost: {r['cost'] or 'Not stated'}\n"
            f"Stipend: {r['stipend'] or 'Not stated'}\n"
            f"Certificate: {r['certificate'] or 'Not stated'}\n"
            f"Eligibility: {r['eligibility'] or 'Not stated'}\n"
            f"Eligibility status: {(r['eligibility_status'] or 'unclear').replace('_', ' ').title()}\n"
            f"Why: {r['eligibility_reasons'] or 'Not stated'}\n"
            f"Source: {r['official_url'] or r['source_url']}"
        )
        send(text, callback_button_row(r["id"], r["application_url"] or r["official_url"] or r["source_url"]))
        mark_notification(r["id"],"daily")

if __name__ == "__main__":
    digest()
