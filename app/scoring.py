from datetime import date
from .db import recent_actions
from config import PROFILE

def preference_boost():
    rows = recent_actions()
    category, source = {}, {}
    for r in rows:
        sign = {"save": 3, "applied": 6, "ignore": -4}.get(r["action"], 0)
        category[r["category"]] = category.get(r["category"], 0) + sign
        source[r["source_name"]] = source.get(r["source_name"], 0) + sign
    return category, source

def _days_to_deadline(value):
    try:
        return (date.fromisoformat(str(value)[:10]) - date.today()).days
    except Exception:
        return None

def score(item):
    # Start from extraction relevance, then apply explicit user-profile signals.
    s = float(item.get("fit_score") or 0)
    cat, src = preference_boost()
    s += min(10, max(-10, cat.get(item.get("category"), 0)))
    s += min(6, max(-6, src.get(item.get("source_name"), 0)))

    text = " ".join(str(item.get(k, "")) for k in
                    ["title", "description", "eligibility", "category", "organization"]).lower()

    # Strongest personalization: exact degree/research fit.
    if "chemical engineering" in text:
        s += 7
    if any(x in text for x in ["research", "r&d", "research assistant", "research project"]):
        s += 5
    if any(x in text for x in ["internship", "intern", "fellowship"]):
        s += 4
    if any(x in text for x in ["process engineering", "reaction engineering", "catalysis", "process simulation"]):
        s += 3

    # Location preference.
    loc = str(item.get("location_mode", "")).lower()
    org = str(item.get("organization", "")).lower()
    source = str(item.get("source_name", "")).lower()
    if any(x in text + " " + loc for x in ["chennai", "tamil nadu", "coimbatore"]):
        s += 7
    elif "india" in text + " " + loc:
        s += 2

    # High-signal institutions are useful, but not enough by themselves.
    if any(x in org + " " + source for x in ["iisc", "iit", "csir", "iiche", "central university"]):
        s += 3

    # User's current stage: reward clear undergraduate fit, penalize uncertainty.
    status = str(item.get("eligibility_status") or "unclear").lower()
    if status == "eligible":
        s += 5
    elif status == "likely_eligible":
        s += 3
    elif status == "conditional":
        s += 1
    elif status == "unclear":
        s -= 4
    elif status == "not_eligible":
        s -= 40

    # Deadline urgency is useful for prioritization, but absence of a deadline is
    # not treated as a negative eligibility signal.
    days = _days_to_deadline(item.get("deadline"))
    if days is not None:
        if 0 <= days <= 3:
            s += 7
        elif 4 <= days <= 7:
            s += 5
        elif 8 <= days <= 14:
            s += 3
        elif days > 14:
            s += 1

    # Trust bonus for first-party sources.
    try:
        s += min(3, max(0, float(item.get("trust_score") or 0) * 3))
    except Exception:
        pass

    return max(0, min(100, round(s, 1)))
