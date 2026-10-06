import json
import os
import re
from datetime import date
from urllib.parse import urlparse
from config import PROFILE

ALLOWED_STATUS = {"eligible", "likely_eligible", "not_eligible", "unclear", "conditional"}
CATEGORIES = {
    "research", "internship", "fellowship", "hackathon", "technical_competition",
    "paper_poster", "visit", "industrial_visit", "workshop", "bootcamp",
    "course", "conference", "seminar", "webinar", "technical_program", "competition"
}

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
}

def _clean(v, default=""):
    if v is None:
        return default
    return re.sub(r"\s+", " ", str(v)).strip()

def _parse_date_match(m):
    try:
        groups = m.groups()
        if len(groups) != 3:
            return None
        a, b, c = groups
        if str(a).isdigit() and len(str(a)) == 4:
            y, mo, d = int(a), int(b), int(c)
        elif str(b).isalpha():
            d, mo, y = int(a), MONTHS[str(b).lower()], int(c)
        elif str(a).isalpha():
            mo, d, y = MONTHS[str(a).lower()], int(b), int(c)
        else:
            # Indian listings commonly use DD/MM/YYYY.
            d, mo, y = int(a), int(b), int(c)
        return date(y, mo, d).isoformat()
    except (ValueError, KeyError):
        return None

def _date_from_text(text):
    patterns = [
        r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b",
        r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b",
        r"\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*,?\s*(20\d{2})\b",
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),?\s+(20\d{2})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            d = _parse_date_match(m)
            if d:
                return d
    return None

def _deadline(text, structured_data=None):
    # Only accept dates attached to an explicit closing/deadline phrase.
    candidates = []
    patterns = [
        r"(?:application|applications|registration|registrations|entries|submissions?)\s+(?:close|closes|closed|end|ends)\s*(?:on|:|-)?\s*([^.;|]{1,60})",
        r"(?:application|applications|registration|registrations|submissions?)\s+(?:deadline|last\s+date)\s*(?:is|:|-)?\s*([^.;|]{1,60})",
        r"(?:apply|register|submit)\s+(?:by|before|on)\s*([^.;|]{1,60})",
        r"(?:last\s+date|deadline|closing\s+date|closing\s+deadline)\s*(?:is|:|-)?\s*([^.;|]{1,60})",
        r"(?:application|registration)\s+(?:deadline|closing\s+date)\s*(?:is|:|-)?\s*([^.;|]{1,60})",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            d = _date_from_text(m.group(1))
            if d:
                candidates.append(d)

    # JSON-LD applicationDeadline is high-confidence structured evidence.
    for blob in structured_data or []:
        for key in ("applicationDeadline", "deadline", "registrationDeadline"):
            for m in re.finditer(rf'"{key}"\s*:\s*"([^"]+)"', blob, re.I):
                raw = m.group(1)
                d = _date_from_text(raw)
                if not d:
                    iso = re.match(r"20\d{2}-\d{1,2}-\d{1,2}", raw)
                    d = iso.group(0) if iso else None
                if d:
                    candidates.append(d)

    valid = []
    for d in candidates:
        try:
            date.fromisoformat(d)
            valid.append(d)
        except ValueError:
            pass
    return min(valid) if valid else None

def _clean_title(item):
    source = _clean(item.get("source_name"))
    raw_title = _clean(item.get("title"))
    candidates = [_clean(x) for x in item.get("title_candidates", []) if _clean(x)]
    candidates = [raw_title] + candidates

    generic = {
        "", "opportunity", "home", "homepage", "welcome", "internship information",
        "internships", "opportunities", "student opportunities", "career",
        "careers", "iiisc", "iisc", "iit madras"
    }
    def score_title(t):
        low = t.lower()
        s = 0
        if low in generic or low == source.lower():
            s -= 10
        if any(k in low for k in ["internship", "fellowship", "research", "workshop",
                                  "hackathon", "competition", "conference", "summer",
                                  "program", "opportunity", "training"]):
            s += 5
        if 8 <= len(t) <= 160:
            s += 2
        if t.count("|") or t.count(" - "):
            s -= 1
        return s
    best = max(candidates, key=score_title, default=raw_title or "Opportunity")
    # Remove common website suffixes without changing the substantive title.
    best = re.sub(r"\s*[|–—-]\s*(?:IISc|IISc Bangalore|IIT Madras|CIT|Coimbatore Institute of Technology)\s*$", "", best, flags=re.I)
    best = _clean(best)
    return best or source or "Opportunity"

def _category(title, text, hints):
    t = (title + " " + text).lower()
    hint = " ".join(hints or []).lower()
    rules = [
        ("fellowship", ["fellowship", "studentship"]),
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
    # Profile: 3rd semester = 2nd academic year.
    if re.search(r"\b(?:3rd|third|4th|fourth)\s*(?:/|or|and)?\s*(?:3rd|third|4th|fourth)?\s*(?:year|yr)\b", t) and not re.search(
        r"\b(?:2nd|second)\s*(?:year|yr)\b", t
    ):
        if re.search(r"\b(?:only|required|must|minimum|students?)\b", t):
            reasons.append("The listing appears restricted to 3rd/4th-year students; profile is 2nd year.")
            return "not_eligible", " ".join(reasons)
    if re.search(r"\b(?:final|pre-?final)\s*year\b", t):
        reasons.append("The listing requires final/pre-final year; profile is 2nd year.")
        return "not_eligible", " ".join(reasons)
    # Only reject a CGPA requirement when it is clearly numeric and above 8.70.
    for m in re.finditer(r"(?:minimum|min\.?)\s*(?:cgpa|gpa)\s*(?:of|:)?\s*(\d(?:\.\d+)?)", t):
        try:
            if float(m.group(1)) > float(PROFILE["cgpa"]):
                return "not_eligible", "The stated minimum CGPA appears above the profile CGPA."
        except ValueError:
            pass

    if "chemical engineering" in t:
        reasons.append("Chemical Engineering is explicitly relevant.")
    elif re.search(r"\bchemical\b", t):
        reasons.append("Chemical/engineering relevance is mentioned.")
    if re.search(r"\b(?:engineering|b\.?tech|undergraduate|ug|students?)\b", t):
        reasons.append("Engineering/undergraduate participation is mentioned.")
    if any(x in t for x in ["any year", "all years", "1st year", "first year", "2nd year", "second year"]):
        reasons.append("No year restriction conflicting with the current profile is evident.")
    if reasons:
        return "likely_eligible", " ".join(dict.fromkeys(reasons))
    return "unclear", "The public listing does not provide enough eligibility evidence."

def _rule_extract(item):
    raw = _clean(item.get("raw"))
    title = _clean_title(item)
    combined = (title + " " + raw).strip()
    deadline = _deadline(combined, item.get("structured_data"))
    status, reasons = _eligibility(combined)
    if deadline and deadline < date.today().isoformat():
        return None

    category = _category(title, raw, item.get("categories_hint", []))
    low = combined.lower()
    fit = 30.0
    keywords = {
        "chemical engineering": 16, "research": 9, "internship": 9,
        "process engineering": 7, "process": 4, "reaction engineering": 5,
        "catalysis": 5, "sustainability": 4, "energy": 4, "materials": 3,
        "simulation": 4, "python": 2, "matlab": 2, "chennai": 5,
        "tamil nadu": 4, "iit": 3, "iisc": 3, "csir": 3, "iiche": 3,
        "plant": 3, "r&d": 4
    }
    for k, v in keywords.items():
        if k in low:
            fit += v
    if category in {"research", "internship", "fellowship", "industrial_visit", "technical_competition"}:
        fit += 6
    if status == "not_eligible":
        fit = min(fit, 15)
    elif status == "unclear":
        fit -= 4
    return {
        "title": title,
        "organization": _clean(item.get("organization_hint")) or _clean(item.get("source_name")) or "Not stated",
        "category": category,
        "source_name": _clean(item.get("source_name")),
        "source_url": _clean(item.get("source_url")),
        "application_url": _clean(item.get("source_url")),
        "official_url": _clean(item.get("source_url")) if float(item.get("trust") or 0) >= 0.9 else "",
        "description": re.sub(r"\s+", " ", raw[:1600]),
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
        "fit_score": max(0, min(100, round(fit, 1))),
        "confidence": "medium",
        "evidence": raw[:700],
    }

def _gemini_extract(items):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
    today = date.today().isoformat()
    payload = [{
        "title": x.get("title"), "title_candidates": x.get("title_candidates", []),
        "url": x.get("source_url"), "text": x.get("raw", "")[:12000],
        "structured_data": x.get("structured_data", [])[:4],
        "trust": x.get("trust", 0.5), "category_hints": x.get("categories_hint", [])
    } for x in items[:250]]
    prompt = f"""You are a conservative opportunity intelligence system.
TODAY: {today}
USER PROFILE: {json.dumps(PROFILE, ensure_ascii=False)}
INPUT: {json.dumps(payload, ensure_ascii=False)[:120000]}

Return ONLY JSON with an opportunities array.
Rules:
- Never invent facts or URLs.
- Deadline must be the application/registration/submission deadline, not an event/start date.
- Use YYYY-MM-DD only when the source clearly supports it; otherwise null.
- Prefer an explicit applicationDeadline JSON-LD field or labelled deadline text.
- Do not infer a deadline from an unrelated date.
- Use a specific program title rather than a generic website/page title.
- Use not_eligible only for a clear failed stated requirement.
- Use likely_eligible when no disqualifier is present but confirmation is needed.
- Use conditional for nomination/approval/CGPA/semester/citizenship conditions.
- Reject expired opportunities.
- Score relevance to Chemical Engineering, research/internships, technical exposure, Tamil Nadu/Chennai and the user's skills.
- Reject admissions-only open houses.
Schema:
{{"opportunities":[{{"title":"","organization":"","category":"","source_name":"","source_url":"","application_url":"","official_url":"","description":"","eligibility":"","eligibility_status":"eligible|likely_eligible|not_eligible|unclear|conditional","eligibility_reasons":"","deadline":"YYYY-MM-DD or null","event_date":"YYYY-MM-DD or null","duration":"","location_mode":"","cost":"","stipend":"","certificate":"","participation":"","fit_score":0,"confidence":"high|medium|low","evidence":""}}]}}"""
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", temperature=0.1, max_output_tokens=30000
        ),
    )
    return json.loads(resp.text).get("opportunities", [])

def _normalize_ai_result(r):
    r = dict(r)
    r["title"] = _clean(r.get("title")) or "Opportunity"
    r["organization"] = _clean(r.get("organization")) or "Not stated"
    r["category"] = _clean(r.get("category"), "technical_program")
    if r["category"] not in CATEGORIES:
        r["category"] = "technical_program"
    r["deadline"] = _date_from_text(_clean(r.get("deadline"))) if _clean(r.get("deadline")) else None
    if r["deadline"] and r["deadline"] < date.today().isoformat():
        return None
    status = _clean(r.get("eligibility_status"), "unclear")
    r["eligibility_status"] = status if status in ALLOWED_STATUS else "unclear"
    return r

def extract(items):
    if os.getenv("GEMINI_API_KEY", "").strip():
        try:
            results = _gemini_extract(items)
            clean = [x for x in (_normalize_ai_result(r) for r in results) if x]
            if clean:
                return clean
        except Exception as exc:
            print(f"Gemini unavailable; using deterministic fallback: {exc}")
    return [r for x in items for r in [_rule_extract(x)] if r]
