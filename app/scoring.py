from .db import recent_actions

def preference_boost():
    rows = recent_actions()
    category = {}
    source = {}
    for r in rows:
        sign = {"save":3,"applied":6,"ignore":-4}.get(r["action"],0)
        category[r["category"]] = category.get(r["category"],0) + sign
        source[r["source_name"]] = source.get(r["source_name"],0) + sign
    return category, source

def score(item):
    s = float(item.get("fit_score") or 0)
    cat, src = preference_boost()
    s += min(12,max(-12,cat.get(item.get("category"),0)))
    s += min(8,max(-8,src.get(item.get("source_name"),0)))

    text = " ".join(str(item.get(k,"")) for k in
                    ["title","description","eligibility","category"]).lower()

    for term in ["chemical engineering","research","sustainability","process",
                 "catalysis","energy","materials","ai","machine learning"]:
        if term in text:
            s += 2

    loc = str(item.get("location_mode","")).lower()
    if "chennai" in loc or "tamil nadu" in loc:
        s += 4

    if item.get("deadline"):
        s += 2

    return max(0,min(100,round(s,1)))
