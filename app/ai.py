import json
import os
import re
from datetime import date, datetime
from urllib.parse import urlparse
from config import PROFILE

ALLOWED_STATUS = {"eligible", "likely_eligible", "not_eligible", "unclear", "conditional"}
CATEGORIES = {
    "research", "internship", "fellowship", "hackathon", "technical_competition",
    "paper_poster", "visit", "industrial_visit", "workshop", "bootcamp",
    "course", "conference", "seminar", "webinar", "technical_program", "competition"
}

def _clean(v, default=""):
    if v is None:
        return default
    return str(v).strip()

def _date_from_text(text):
    patterns = [
        r'\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b',
        r'\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b',
        r'\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*,?\s*(20\d{2})\b',
        r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),?\s+(20\d{2})\b',
    ]
    months = {m.lower(): i for i, m in enumerate(
        ["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}
    for p in patterns:
        m = re.search(p, text, re.I)
        if not m:
            continue
        try:
            if p.startswith(r'\b(20'):
                y, mo, d = map(int, m.groups())
            elif m.group(2).isalpha():
                d, mon, y = m.groups()
                mo = next(v for k,v in months.items() if k.startswith(mon.lower()[:3]))
                d, y = int(d), int(y)
            elif m.group(1).isalpha():
                mon, d, y = m.groups()
                mo = next(v for k,v in months.items() if k.startswith(mon.lower()[:3]))
                d, y = int(d), int(y)
            else:
                d, mo, y = map(int, m.groups())
            return date(y, mo, d).isoformat()
        except (ValueError, StopIteration):
            pass
    return None

def _deadline(text):
    labels = r"(?:deadline|last date|apply by|applications? close|registration closes?|closing date|due date)"
    m = re.search(labels + r".{0,100}", text, re.I)
    if m:
        d = _date_from_text(m.group(0))
        if d:
            return d
    return _date_from_text(text[:12000])

def _category(title, text, hints):
    t = (title + " " + text).lower()
    hint = " ".join(hints or []).lower()
    rules = [
        ("fellowship", ["fellowship", "summer research fellowship", "studentship"]),
        ("industrial_visit", ["plant visit", "industrial visit", "industry visit", "factory visit", "r&d visit"]),
        ("visit", ["lab visit", "laboratory visit", "open visit", "research facility visit", "open day"]),
        ("paper_poster", ["call for papers", "call for abstracts", "poster presentation", "paper presentation", "student symposium"]),
        ("hackathon", ["hackathon"]),
        ("technical_competition", ["technical competition", "engineering competition"]),
        ("workshop", ["workshop"]),
        ("bootcamp", ["bootcamp", "boot camp"]),
        ("conference", ["conference"]),
        ("seminar", ["seminar", "lecture series"]),
        ("webinar", ["webinar", "online talk"]),
        ("internship", ["internship", "intern"]),
        ("research", ["research opportunity", "research project", "project assistant", "research assistant", "lab opening"]),
        ("course", ["course", "training", "certification"]),
    ]
    for cat, terms in rules:
        if any(x in t for x in terms):
            return cat
    for cat in CATEGORIES:
        if cat in hint:
            return cat
    return "technical_program"

def _eligibility(text):
    t = text.lower()
    reasons = []
    # Explicit disqualifiers for the current profile.
    if re.search(r'\b(?:3rd|third|4th|fourth)\s*(?:year|yr)', t):
        if not re.search(r'\b(?:2nd|second)\s*(?:year|yr)', t):
            # If only final-year language is present, user is not eligible.
            if re.search(r'\b(?:3rd|third|4th|fourth)\s*(?:year|yr)\s*(?:and|or|only|required|students?)?', t):
                reasons.append("The listing appears restricted to 3rd/4th-year students; profile is 2nd year.")
                return "not_eligible", "; ".join(reasons)
    if re.search(r'\b(?:final|pre-?final)\s*year\b', t):
        reasons.append("The listing requires final/pre-final year; profile is 2nd year.")
        return "not_eligible", "; ".join(reasons)
    if re.search(r'\b(?:minimum|min\.?)\s*(?:cgpa|gpa).{0,20}(?:9(?:\.0+)?|9\.[0-9]+)', t):
        reasons.append("The stated minimum CGPA appears above the profile CGPA.")
        return "not_eligible", "; ".join(reasons)
    # Positive signals.
    if "chemical engineering" in t or "chemical" in t:
        reasons.append("Chemical Engineering is explicitly relevant.")
    if re.search(r'\b(?:engineering|b\.?tech|undergraduate|ug|students?)\b', t):
        reasons.append("Engineering/undergraduate participation is mentioned.")
    if any(x in t for x in ["any year", "all years", "1st year", "first year", "2nd year", "second year"]):
        reasons.append("No year restriction conflicting with the current profile is evident.")
    if reasons:
        return "likely_eligible", " ".join(reasons)
    return "unclear", "The public listing does not provide enough eligibility evidence."

def _rule_extract(item):
    raw = _clean(item.get("raw"))
    title = _clean(item.get("title")) or "Opportunity"
    combined = (title + " " + raw).strip()
    deadline = _deadline(combined)
    status, reasons = _eligibility(combined)
    if deadline and deadline < date.today().isoformat():
        return None
    category = _category(title, raw, item.get("categories_hint", []))
    low = combined.lower()
    fit = 35.0
    keywords = {
        "chemical engineering": 14, "research": 10, "internship": 10,
        "process": 6, "catalysis": 6, "sustainability": 5, "energy": 4,
        "materials": 4, "simulation": 4, "python": 3, "matlab": 3,
        "chennai": 5, "tamil nadu": 4, "iit": 3, "iisc": 3, "csir": 3,
        "iiche": 3, "plant": 4, "r&d": 4
    }
    for k, v in keywords.items():
        if k in low:
            fit += v
    if category in {"research", "internship", "fellowship", "industrial_visit", "technical_competition"}:
        fit += 8
    if deadline:
        fit += 2
    if status == "not_eligible":
        fit = min(fit, 20)
    elif status == "unclear":
        fit -= 5
    fit = max(0, min(100, round(fit, 1)))

    # Preserve source URL; never invent application links.
    source_url = _clean(item.get("source_url"))
    return {
        "title": title,
        "organization": _clean(item.get("source_name")) or "Not stated",
        "category": category,
        "source_name": _clean(item.get("source_name")),
        "source_url": source_url,
        "application_url": source_url,
        "official_url": source_url if float(item.get("trust") or 0) >= 0.9 else "",
        "description": re.sub(r"\s+", " ", raw[:1200]),
        "eligibility": reasons or "Not stated",
        "eligibility_status": status,
        "eligibility_reasons": reasons,
        "deadline": deadline,
        "event_date": None,
        "duration": "",
        "location_mode": "Online" if "online" in low or "virtual" in low else "",
        "cost": "",
        "stipend": "",
        "certificate": "Yes" if "certificate" in low or "certification" in low else "",
        "participation": "",
        "fit_score": fit,
        "confidence": "medium",
        "evidence": raw[:500],
    }

def _gemini_extract(items):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
    today = date.today().isoformat()
    payload = [{
        "title": x.get("title"), "url": x.get("source_url"),
        "text": x.get("raw", "")[:12000], "trust": x.get("trust", 0.5),
        "category_hints": x.get("categories_hint", [])
    } for x in items[:250]]
    prompt = f"""You are a conservative opportunity intelligence system.
TODAY: {today}
USER PROFILE: {json.dumps(PROFILE, ensure_ascii=False)}
INPUT: {json.dumps(payload, ensure_ascii=False)[:120000]}

Return ONLY JSON: {{"opportunities":[{{"title":"","organization":"","category":"","source_name":"","source_url":"","application_url":"","official_url":"","description":"","eligibility":"","eligibility_status":"eligible|likely_eligible|not_eligible|unclear|conditional","eligibility_reasons":"","deadline":"YYYY-MM-DD or null","event_date":"YYYY-MM-DD or null","duration":"","location_mode":"","cost":"","stipend":"","certificate":"","participation":"","fit_score":0,"confidence":"high|medium|low","evidence":""}}]}}
Rules: never invent facts or URLs; reject expired deadlines; use not_eligible only for a clear failed stated requirement; use likely_eligible when no disqualifier but confirmation is needed; use conditional for nomination/approval/CGPA/semester/citizenship conditions; use unclear when eligibility evidence is insufficient. Prefer first-party evidence. Score relevance to Chemical Engineering, research, internships, technical exposure, Tamil Nadu/Chennai, and the user's skills. Reject admissions-only open houses."""
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=30000,
        ),
    )
    data = json.loads(resp.text)
    return data.get("opportunities", [])

def extract(items):
    # Gemini is optional. Any missing key, SDK problem, quota error, or malformed
    # response falls back to deterministic extraction so the radar still runs.
    if os.getenv("GEMINI_API_KEY", "").strip():
        try:
            results = _gemini_extract(items)
            if results:
                clean = []
                today = date.today().isoformat()
                for r in results:
                    if _clean(r.get("deadline")) and _clean(r.get("deadline")) < today:
                        continue
                    status = _clean(r.get("eligibility_status"), "unclear")
                    if status not in ALLOWED_STATUS:
                        status = "unclear"
                    r["eligibility_status"] = status
                    clean.append(r)
                if clean:
                    return clean
        except Exception as exc:
            print(f"Gemini unavailable; using deterministic fallback: {exc}")
    return [r for x in items for r in [_rule_extract(x)] if r]
