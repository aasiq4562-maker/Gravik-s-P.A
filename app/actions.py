from .telegram import poll_once, acknowledge
from .db import init, action, get_opportunity
from .telegram import send
from urllib.parse import urlparse

def run():
    init()
    updates=poll_once()
    for u in updates:
        cq=u.get("callback_query")
        if not cq:
            continue
        data=cq.get("data","")
        if ":" not in data:
            continue
        name, oid=data.split(":",1)
        try:
            oid=int(oid)
        except:
            continue
        action(oid,name)
        labels={
            "save":"Saved. The scorer will learn this preference.",
            "ignore":"Ignored. Similar low-priority items will be down-ranked.",
            "applied":"Marked as applied. It will be suppressed from future alerts."
        }
        if name == "apply":
            row = get_opportunity(oid)
            url = (row["application_url"] or row["official_url"] or row["source_url"]) if row else ""
            try:
                parsed = urlparse((url or "").strip())
                valid = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
            except Exception:
                valid = False
            if valid:
                send(f"🔗 Application link\n{url}")
                acknowledge(cq["id"],"Application link sent.")
            else:
                acknowledge(cq["id"],"No valid application link was available for this item.")
        else:
            acknowledge(cq["id"],labels.get(name,"Recorded."))

if __name__ == "__main__":
    run()
