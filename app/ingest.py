import hashlib
from datetime import date
from .db import init, upsert
from .sources import collect_sources
from .ai import extract
from .scoring import score


def _s(value):
    return "" if value is None else str(value)


def _is_expired(deadline):
    if not deadline:
        return False
    try:
        return date.fromisoformat(str(deadline)[:10]) < date.today()
    except ValueError:
        return False


def run():
    init()
    raw = collect_sources()
    usable = [x for x in raw if x.get("raw")]
    results = extract(usable)

    counts = {"new": 0, "updated": 0, "seen": 0, "expired_skipped": 0}
    for x in results:
        if _is_expired(x.get("deadline")):
            counts["expired_skipped"] += 1
            continue

        source_url = x.get("source_url") or ""
        official_url = x.get("official_url") or ""
        title = x.get("title") or ""
        description = x.get("description") or ""
        eligibility = x.get("eligibility") or ""

        x["fingerprint"] = hashlib.sha256(
            f"{title}|{official_url or source_url}".lower().encode("utf-8")
        ).hexdigest()[:32]
        x["content_hash"] = hashlib.sha256(
            f"{description}|{eligibility}".encode("utf-8")
        ).hexdigest()
        x["deadline_hash"] = hashlib.sha256(
            _s(x.get("deadline")).encode("utf-8")
        ).hexdigest()
        x["fit_score"] = score(x)
        x["trust_score"] = 1.0 if official_url else 0.7

        _, status = upsert(x)
        counts[status] = counts.get(status, 0) + 1

    print("Ingest:", counts)


if __name__ == "__main__":
    run()
