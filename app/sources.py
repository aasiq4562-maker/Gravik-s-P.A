import hashlib, requests, feedparser, yaml, xml.etree.ElementTree as ET, urllib.robotparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config import SEARCH_QUERIES
from .db import record_source_run

UA = "GravikOpportunityAgent/2.0 (+personal research monitor)"

def text_hash(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

def allowed_by_robots(url):
    from urllib.parse import urlparse
    p = urlparse(url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        r = requests.get(robots_url, timeout=10, headers={"User-Agent": UA})
        if r.status_code == 404:
            return True
        r.raise_for_status()
        rp.parse(r.text.splitlines())
        return rp.can_fetch(UA, url)
    except requests.RequestException:
        # Fail closed for non-standard/blocked robots endpoints.
        return False


def fetch(url):
    if not allowed_by_robots(url):
        raise PermissionError(f"robots.txt disallows fetching: {url}")
    r = requests.get(url, timeout=25, headers={"User-Agent": UA})
    r.raise_for_status()
    return r.text, r.url

def parse_page(source):
    html, final_url = fetch(source["url"])
    soup = BeautifulSoup(html, "html.parser")

    # Keep structured page metadata so extraction can distinguish a program title
    # from a generic source/page name and can use explicit deadline fields safely.
    title_candidates = []
    h1 = soup.find("h1")
    if h1:
        title_candidates.append(h1.get_text(" ", strip=True))
    for h in soup.find_all(["h2", "h3"])[:8]:
        value = h.get_text(" ", strip=True)
        if value:
            title_candidates.append(value)

    meta_title = soup.find("meta", attrs={"property": "og:title"})
    if meta_title and meta_title.get("content"):
        title_candidates.insert(0, meta_title["content"].strip())
    html_title = soup.find("title")
    if html_title:
        title_candidates.append(html_title.get_text(" ", strip=True))

    structured = []
    for script in soup.find_all("script", type="application/ld+json"):
        value = script.string or script.get_text(" ", strip=True)
        if value:
            structured.append(value[:12000])

    for x in soup(["script","style","noscript"]):
        x.decompose()
    text = soup.get_text(" ", strip=True)

    # Add source-level organization metadata when configured, without inventing it.
    organization = source.get("organization") or source.get("name", "")
    return [{
        "source_id": source["id"],
        "source_name": source["name"],
        "source_url": final_url,
        "title": title_candidates[0] if title_candidates else source["name"],
        "title_candidates": title_candidates[:12],
        "organization_hint": organization,
        "structured_data": structured[:8],
        "raw": text[:40000],
        "trust": source.get("trust",0.5),
        "categories_hint": source.get("categories",[])
    }]

def parse_rss(source):
    # RSS/Atom endpoints are remote fetches too, so apply the same robots policy.
    xml, final_url = fetch(source["url"])
    d = feedparser.parse(xml)
    out=[]
    for e in d.entries[:100]:
        out.append({
            "source_id": source["id"],
            "source_name": source["name"],
            "source_url": e.get("link",final_url),
            "title": e.get("title",""),
            "raw": (e.get("summary","") + " " + e.get("description",""))[:15000],
            "published": e.get("published",""),
            "trust": source.get("trust",0.5),
            "categories_hint": source.get("categories",[])
        })
    return out

def parse_sitemap(source):
    xml, _ = fetch(source["url"])
    root = ET.fromstring(xml)
    ns = {"sm":"http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [x.text for x in root.findall(".//sm:loc", ns)]
    return [{
        "source_id": source["id"],
        "source_name": source["name"],
        "source_url": u,
        "title": "",
        "raw": "",
        "trust": source.get("trust",0.5),
        "categories_hint": source.get("categories",[])
    } for u in urls[:300]]

def search_api(source):
    # Optional permitted discovery via Brave Search API. If no key is configured,
    # the source is recorded as inactive rather than silently pretending to work.
    import os
    key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not key:
        return []

    queries = source.get("queries", [])
    out = []
    for q in queries:
        headers = {"Accept": "application/json", "X-Subscription-Token": key, "User-Agent": UA}
        r = requests.get("https://api.search.brave.com/res/v1/web/search", params={"q": q, "count": 20}, headers=headers, timeout=20)
        r.raise_for_status()
        for item in r.json().get("web", {}).get("results", []):
            url = item.get("url")
            if not url:
                continue
            raw = (item.get("description", "") or "")[:15000]
            # Search results are discovery signals. When the result page is publicly
            # fetchable, enrich the signal with the actual page text before AI extraction.
            try:
                html, final_url = fetch(url)
                soup = BeautifulSoup(html, "html.parser")
                for x in soup(["script", "style", "noscript"]):
                    x.decompose()
                page_text = soup.get_text(" ", strip=True)
                if page_text:
                    raw = page_text[:40000]
                url = final_url
            except Exception:
                # Keep the search snippet rather than failing the whole source.
                pass
            out.append({
                "source_id": source["id"],
                "source_name": source["name"],
                "source_url": url,
                "title": item.get("title", ""),
                "raw": raw,
                "trust": source.get("trust", 0.5),
                "categories_hint": source.get("categories", [])
            })
    return out

def collect_sources():
    with open("sources.yaml","r",encoding="utf-8") as f:
        sources = yaml.safe_load(f)["sources"]

    all_items=[]
    for s in sources:
        try:
            if s["kind"] == "rss":
                items = parse_rss(s)
            elif s["kind"] == "sitemap":
                items = parse_sitemap(s)
            elif s["kind"] == "page":
                items = parse_page(s)
            elif s["kind"] == "search":
                items = search_api(s)
            else:
                items=[]
            record_source_run(s["id"],"ok",len(items))
            all_items.extend(items)
        except Exception as e:
            record_source_run(s["id"],"error",0,str(e))

    return all_items

def fingerprints(item):
    key = (item.get("title","") + "|" + item.get("source_url","")).lower()
    return hashlib.sha256(key.encode()).hexdigest()[:32]
