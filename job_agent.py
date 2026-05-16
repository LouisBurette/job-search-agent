#!/usr/bin/env python3
"""
Job Agent — weekly email digest of relevant job offers.
Recommended cron: 0 7 * * 1  /path/to/.venv/bin/python /path/to/job_agent.py
"""

import json
import os
import re
import smtplib
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import anthropic
import feedparser
import requests as req
from dotenv import load_dotenv

load_dotenv()

feedparser.USER_AGENT = "Mozilla/5.0 (compatible; JobAgent/1.0)"

# ── Configuration ────────────────────────────────────────────────────────────

CONFIG = {
    "mandatory": {
        "postes": ["Product Manager", "COO", "Operational Director"],
        # Multilingual aliases — add translations when postes change
        "postes_aliases": [
            # Product Manager
            "chef de produit", "responsable produit", "responsable de produit",
            # COO / Operational Director
            "directeur des opérations", "directeur des operations",
            "directeur opérationnel", "responsable des opérations",
            "director de operaciones", "responsable operativo",
            "head of operations", "operations director", "director of operations",
            "chief operating officer",
        ],
        "contrats": ["CDI"],
        "remote": "full",
        "company_location": ["France", "Spain"],
        "salaire_min": 45000,
        "secteurs_nok": [
            "defense", "crypto", "fossil energy", "gambling",
            "adult industry", "drugs", "alcohol", "tobacco", "weapons",
        ],
    },
    "wished": {
        "secteurs_ok": [
            "tech for good", "ecology", "social", "b-corp",
            "association", "ngo", "green tech", "sustainability",
            "mobility", "sport",
        ],
        "stack": ["n8n", "claude code"],
        "keywords": ["ai agents", "automation", "ai systems", "artificial intelligence"],
    },
    "settings": {
        "score_min": 7,
        "top_n": 15,
        "max_age_days": 10,
        # Local geo areas accepted as alternatives to full remote.
        # Format: { "Display Label": ["keyword1", "keyword2", ...] }
        # The label is used directly in the email tag — edit here to rename or add zones.
        "geo_local": {
            "Donostia": ["donostia", "san sebastián", "san sebastian", "gipuzkoa"],
            "Pays Basque FR": ["bayonne", "biarritz", "anglet", "hendaye", "bidart", "saint-jean-de-luz", "saint jean de luz"],
            "Pays Basque": ["pays basque", "país vasco", "euskadi", "pyrénées-atlantiques", "côte basque"],
        },
        # Job title substrings that immediately disqualify an offer before LLM scoring
        "titres_exclus": [
            "cuisinier", "chef de cuisine", "chef de partie", "commis", "serveur", "plongeur",
            "albañil", "peón", "limpieza", "ayudante de cocina",
            "developer", "engineer", "designer", "editor", "teacher", "historian", "artist",
            "clerk", "scheduler", "assistant", "representative", "recruiter", "marketing coordinator",
            "social media", "paralegal", "nurse", "technician", "physician", "accountant",
            "analyst", "specialist", "coordinator", "associate", "intern", "junior",
            "sales operations", "marketing operations", "hr operations",
            "customer operations", "it operations", "revenue operations",
        ],
    },
    # Apify scraping parameters — injected into requests, edit here to change the search
    "apify": {
        "query": '"Product Manager" OR "COO" OR "Director of Operations"',
        "max_items_per_source": 50,
        "linkedin_filters": "f_WT=2&f_JT=F",  # remote + full-time (time range injected from settings.max_age_days)
        "wttj_contract": "CDI",
        # ISO 3166-1 alpha-2 codes for each country in mandatory.company_location
        "country_iso": {
            "France": "FR",
            "Spain": "ES",
        },
    },
}

REMOTE_KEYWORDS = [
    "remote", "full remote", "fully remote", "100% remote", "remote-first",
    "télétravail", "teletrabajo", "home office", "distributed",
]


def get_role_keywords(config: dict) -> list[str]:
    """Derive title-matching keywords from CONFIG — no manual update needed when postes change."""
    keywords = [p.lower() for p in config["mandatory"]["postes"]]
    keywords += [a.lower() for a in config["mandatory"].get("postes_aliases", [])]
    return keywords

# Country name aliases — knowledge base used to detect explicit non-target locations in RSS feeds.
# Add entries here if a new country needs to be recognisable (either as a target or as an exclusion).
COUNTRY_ALIASES: dict[str, list[str]] = {
    "france":         ["france", "français", "francais"],
    "spain":          ["spain", "españa", "espagne", "espana"],
    "united states":  ["united states", "usa", "u.s.a", "us-only", "us only"],
    "united kingdom": ["united kingdom", "uk", "england", "britain"],
    "canada":         ["canada"],
    "australia":      ["australia"],
    "germany":        ["germany", "deutschland"],
    "netherlands":    ["netherlands", "holland"],
    "sweden":         ["sweden"],
    "switzerland":    ["switzerland"],
    "india":          ["india"],
    "singapore":      ["singapore"],
    "brazil":         ["brazil"],
    "mexico":         ["mexico"],
    "japan":          ["japan"],
    "china":          ["china"],
}

SOURCES = [
    {
        "name": "We Work Remotely",
        "url": "https://weworkremotely.com/categories/remote-product-jobs.rss",
        "default_location": "Remote",
    },
    {
        "name": "RemoteOK",
        "url": "https://remoteok.com/remote-jobs.rss",
        "default_location": "Remote",
    },
    {
        "name": "Jobicy",
        "url": "https://jobicy.com/?feed=job_feed",
        "default_location": "Remote",
    },
    {
        "name": "Jobspresso",
        "url": "https://jobspresso.co/?feed=job_feed",
        "default_location": "Remote",
    },
]

def build_apify_sources(config: dict) -> list:
    ap = config["apify"]
    countries = config["mandatory"]["company_location"]
    q = ap["query"]
    n = ap["max_items_per_source"]
    iso = ap["country_iso"]
    max_age_days = config["settings"]["max_age_days"]
    linkedin_filters = f"{ap['linkedin_filters']}&f_TPR=r{max_age_days * 86400}"
    from urllib.parse import quote_plus

    sources = []
    for country in countries:
        code = iso.get(country, country[:2].upper())

        # Indeed excluded: no CDI/remote filter available at platform level — too much noise

        wttj_urls = [
            {"url": f"https://www.welcometothejungle.com/fr/jobs?query={quote_plus(q)}&refinementList[contract_type][]={ap['wttj_contract']}&refinementList[offices.country_code][]={code}"},
        ]
        if country == countries[0]:
            # include full-remote URL once (WTTJ is a French platform — results are mostly FR companies)
            wttj_urls.insert(0, {"url": f"https://www.welcometothejungle.com/fr/jobs?query={quote_plus(q)}&refinementList[contract_type][]={ap['wttj_contract']}&refinementList[remote][]=fulltime"})
        sources.append({
            "name": f"Welcome to the Jungle ({country})",
            "actor_id": "ip6ZC7cs8a1YUxBoC",
            "input": {"startUrls": wttj_urls, "maxItems": n},
            "default_location": country,
        })

        sources.append({
            "name": f"LinkedIn ({country})",
            "actor_id": "JkfTWxtpgfvcRQn3p",
            "input": {
                "searchUrl": f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(q)}&location={quote_plus(country)}&{linkedin_filters}",
                "maxItems": n,
            },
            "default_location": country,
        })

    return sources

STATE_FILE = Path(__file__).parent / "state.json"

# ── State (deduplication) ────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"sent_urls": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def clean_old_entries(state: dict, days: int = 30) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    state["sent_urls"] = [e for e in state["sent_urls"] if e["ts"] >= cutoff]
    return state


def already_sent(url: str, state: dict) -> bool:
    return url in {e["url"] for e in state["sent_urls"]}


def mark_sent(urls: list, state: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    for url in urls:
        state["sent_urls"].append({"url": url, "ts": now})
    return state

# ── Fetch & Normalize ────────────────────────────────────────────────────────

def parse_date(entry) -> Optional[datetime]:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def fetch_source(source: dict, max_age_days: int) -> tuple:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    try:
        feed = feedparser.parse(source["url"])
        if not feed.entries:
            return [], f"{source['name']} (no entries)"

        offers = []
        for entry in feed.entries:
            pub = parse_date(entry)
            if pub and pub < cutoff:
                continue

            title = entry.get("title", "")
            company = ""
            if " at " in title:
                parts = title.split(" at ", 1)
                title, company = parts[0].strip(), parts[1].strip()

            offers.append({
                "titre": title,
                "entreprise": company or entry.get("author", "") or "",
                "url": entry.get("link", ""),
                "description": entry.get("summary", "") or (entry.get("content") or [{}])[0].get("value", ""),
                "date": pub.isoformat() if pub else "",
                "source": source["name"],
                "localisation": (entry.get("tags") or [{}])[0].get("term", "") or source["default_location"],
                "salaire": "",
            })
        return offers, None

    except Exception as e:
        return [], f"{source['name']} ({e})"

def normalize_apify_item(item: dict, source_name: str, default_location: str) -> Optional[dict]:
    """Normalize an Apify item based on the source."""

    if source_name.startswith("LinkedIn"):
        return {
            "titre": item.get("job_title", ""),
            "entreprise": item.get("company_name", ""),
            "url": item.get("job_url", ""),
            "description": item.get("job_description", ""),
            "date": item.get("time_posted", ""),
            "source": source_name,
            "localisation": item.get("location", default_location),
            "salaire": item.get("salary_range", ""),
            "contrat": item.get("employment_type", "") or item.get("contract_type", ""),
        }

    if source_name.startswith("Welcome to the Jungle"):
        offices = item.get("offices", [])
        loc = offices[0].get("city", default_location) if offices else default_location
        sal_min = item.get("salaryYearlyMin")
        sal_max = item.get("salaryYearlyMax")
        currency = item.get("salaryCurrency", "€")
        salaire = ""
        if sal_min and sal_max:
            salaire = f"{sal_min:,}–{sal_max:,} {currency}/an"
        elif sal_min:
            salaire = f"≥ {sal_min:,} {currency}/an"
        contract_raw = item.get("contractType") or item.get("contract_type") or ""
        if isinstance(contract_raw, list):
            contract_raw = contract_raw[0] if contract_raw else ""
        return {
            "titre": item.get("title", ""),
            "entreprise": item.get("companyName", ""),
            "url": item.get("url", ""),
            "description": item.get("description") or item.get("companyDescription", ""),
            "date": item.get("publishedAt", ""),
            "source": source_name,
            "localisation": loc,
            "salaire": salaire,
            "contrat": str(contract_raw),
        }

    return None


def fetch_apify_source(source: dict, max_age_days: int) -> tuple:
    token = os.environ.get("APIFY_API_TOKEN", "")
    if not token:
        return [], f"{source['name']} (APIFY_API_TOKEN missing)"

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    try:
        r = req.post(
            f"https://api.apify.com/v2/acts/{source['actor_id']}/run-sync-get-dataset-items?timeout=120",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=source["input"],
            timeout=130,
        )
        if r.status_code not in (200, 201):
            return [], f"{source['name']} (HTTP {r.status_code})"

        items = r.json()
        if not isinstance(items, list):
            return [], f"{source['name']} (unexpected response)"

        offers = []
        for item in items:
            offer = normalize_apify_item(item, source["name"], source["default_location"])
            if not offer or not offer.get("url"):
                continue
            # Filter by date if available
            if offer["date"]:
                try:
                    pub = datetime.fromisoformat(offer["date"].replace("Z", "+00:00"))
                    if pub < cutoff:
                        continue
                except Exception:
                    pass
            offers.append(offer)
        return offers, None

    except Exception as e:
        return [], f"{source['name']} ({e})"


# ── Filtering ────────────────────────────────────────────────────────────────

def avoids_secteur(offer: dict) -> bool:
    text = f"{offer.get('titre') or ''} {offer.get('description') or ''}".lower()
    return not any(s.lower() in text for s in CONFIG["mandatory"]["secteurs_nok"])


def rss_location_ok(offer: dict) -> bool:
    """For RSS feeds only: reject if location explicitly names a country not in company_location.
    Vague values ("Remote", "Worldwide", "") are passed through — Claude handles them."""
    loc = (offer.get("localisation") or "").lower().strip()
    vague = {"", "remote", "worldwide", "anywhere", "global", "international"}
    if loc in vague or any(k in loc for k in REMOTE_KEYWORDS):
        return True

    targets = [c.lower() for c in CONFIG["mandatory"]["company_location"]]

    # Location matches a target country → keep
    for country in targets:
        if any(alias in loc for alias in COUNTRY_ALIASES.get(country, [country])):
            return True

    # Location explicitly names a known non-target country → reject
    for country, aliases in COUNTRY_ALIASES.items():
        if country in targets:
            continue
        if any(alias in loc for alias in aliases):
            return False

    return True  # unknown location → let Claude decide


def apply_filters(offers: list) -> list:
    rss_source_names = {s["name"] for s in SOURCES}
    result = []
    for o in offers:
        if not o.get("url"):
            continue
        
        title_lower = (o.get("titre") or "").lower()
        
        # 1. Strict Title Exclusion — list managed in CONFIG["settings"]["titres_exclus"]
        if any(exc in title_lower for exc in CONFIG["settings"]["titres_exclus"]):
            continue
            
        # 2. Strict Role Inclusion (must have at least one keyword)
        # Derived from CONFIG — no manual update needed when postes/aliases change
        if not any(kw in title_lower for kw in get_role_keywords(CONFIG)):
            continue
            
        # 3. Sector Exclusion
        if not avoids_secteur(o):
            continue
            
        # 4. Location Filter (RSS only)
        if o.get("source") in rss_source_names and not rss_location_ok(o):
            continue
            
        result.append(o)
    return result

# ── Scoring LLM ──────────────────────────────────────────────────────────────

def build_prompt(offer: dict) -> str:
    m = CONFIG["mandatory"]
    w = CONFIG["wished"]
    return f"""You are an expert recruiter. Evaluate the job offer below against a candidate's search criteria and return a JSON score.

## Mandatory criteria — if ANY fails, score must be ≤ 2

- **Roles**: {', '.join(m['postes'])}
  Apply semantic matching: equivalent or specialised titles count as valid (e.g. "Data Product Manager", "Technical PM" for "Product Manager"; "Chief Operating Officer", "Director of Operations" for "COO" — these are examples, not an exhaustive list).
  Apply multilingual matching: map equivalent titles across languages (e.g. "Responsable Produit", "Chef de Produit" for "Product Manager"; "Directeur des Opérations", "Responsable Operativo" for "Operational Director" — these are examples, not an exhaustive list).
- **Contract**: {', '.join(m['contrats'])} only — reject fixed-term, freelance, and internship contracts
- **Full remote**: the position must allow working 100% remotely
- **Company location**: the company must be based in {' or '.join(m['company_location'])}; if the company's country is unclear but the offer comes from a job board operating in one of these countries, assume it qualifies
- **Minimum salary**: €{m['salaire_min']:,}/year — if salary is explicitly mentioned and below this, deduct 2 points
- **Excluded sectors**: {', '.join(m['secteurs_nok'])} — any match → score ≤ 2 automatically

## Wished criteria — each one increases the score

- **Preferred sectors** (strong bonus): {', '.join(w['secteurs_ok'])}
- **Tech stack** (bonus): {', '.join(w['stack'])}
- **Keywords of interest** (bonus): {', '.join(w['keywords'])}

## Scoring scale

| Score | Meaning |
|-------|---------|
| 10    | All mandatory met + 3 or more wished criteria present |
| 8–9   | All mandatory met + 2 wished criteria |
| 7     | All mandatory met + 1 wished criterion |
| 5–6   | All mandatory met, no wished criteria matched |
| 3–4   | 1 mandatory criterion missing or unclear |
| 1–2   | Multiple mandatory missing, excluded sector, or clearly wrong role/seniority |

Additional rules:
- Titles clearly too senior (e.g. VP, CPO, CHRO, C-suite other than COO) or too junior (e.g. Junior, Associate, Intern) → score ≤ 4
- Analyze the offer in whatever language it is written (EN/FR/ES) and map its content to the English criteria above

## Offer to evaluate

Title: {offer['titre']}
Company: {offer['entreprise']}
Source: {offer['source']}
Location: {offer['localisation']}
Salary: {offer['salaire'] or 'not specified'}
Description: {offer['description'][:2000]}

Respond ONLY with valid JSON, no markdown, no text before or after:
{{"score": <integer 1-10>, "raison": "<2 sentences max in French, justify the score with key strengths and weaknesses>", "tags_detectes": {{"remote": <bool>, "impact": <bool>, "salaire_ok": <bool>, "experience_ok": <bool>, "stack_match": [<list of matched keywords>]}}}}"""


def score_offers(offers: list) -> list:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    scored = []
    for i, offer in enumerate(offers):
        print(f"  Scoring {i+1}/{len(offers)}: {offer['titre'][:55]}")
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": build_prompt(offer)}],
            )
            raw = response.content[0].text.strip()
            # Clean possible markdown block if Claude ignores instructions
            if raw.startswith("```json"):
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif raw.startswith("```"):
                raw = raw.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw)
            offer["score"] = int(parsed.get("score", 0))
            offer["raison"] = parsed.get("raison", "")
            offer["tags_detectes"] = parsed.get("tags_detectes", {})
            scored.append(offer)
        except Exception as e:
            print(f"    ⚠ Score error for '{offer['titre'][:30]}': {e}")
            offer["score"] = 0
            offer["raison"] = f"Error during scoring: {e}"
            offer["tags_detectes"] = {}
            scored.append(offer)
        
        if i < len(offers) - 1:
            time.sleep(0.3)
    return scored

# ── Email HTML ───────────────────────────────────────────────────────────────

def score_color(score: Optional[int]) -> str:
    if score is None:
        return "#94a3b8"
    if score >= 8:
        return "#16a34a"
    if score >= 5:
        return "#d97706"
    return "#dc2626"


def extract_tags(offer: dict) -> str:
    tags = []
    td = offer.get("tags_detectes", {})
    loc = offer.get("localisation", "").lower()
    desc = offer.get("description", "").lower()
    titre = offer.get("titre", "").lower()

    # Location — labels come from CONFIG["settings"]["geo_local"] keys
    geo_local = CONFIG["settings"]["geo_local"]
    matched_geo = next(
        (label for label, keywords in geo_local.items() if any(k in loc for k in keywords)),
        None,
    )
    is_remote = td.get("remote") or any(k in loc for k in REMOTE_KEYWORDS)

    if matched_geo:
        tags.append(("📍", matched_geo, "#7c3aed", "#f3e8ff"))
    elif is_remote:
        tags.append(("🌍", "Full Remote", "#0369a1", "#e0f2fe"))

    # Impact
    if td.get("impact"):
        tags.append(("🌱", "Impact +", "#15803d", "#dcfce7"))

    # Salary
    salaire = offer.get("salaire", "")
    if salaire:
        tags.append(("💰", salaire[:30], "#15803d", "#dcfce7"))
    else:
        # Try to extract from description
        m = re.search(r'(\d{2,3})[,.]?(\d{3})?\s*[€$£k]', desc)
        if m:
            val = m.group(0).strip()
            tags.append(("💰", val, "#15803d", "#dcfce7"))

    # Contract type
    contrat = offer.get("contrat", "").strip()
    if contrat:
        tags.append(("📄", contrat, "#475569", "#f1f5f9"))

    # Stack match from LLM
    stack_match = td.get("stack_match", [])
    for kw in stack_match[:3]:
        tags.append(("⚙️", kw, "#1d4ed8", "#eff6ff"))

    # Keywords from CONFIG matched in offer text
    text = f"{offer.get('titre', '')} {desc}"
    matched_keywords = [kw for kw in CONFIG["wished"]["keywords"] if kw.lower() in text]
    for kw in matched_keywords[:3]:
        if kw not in [t[1].lower() for t in tags]:
            tags.append(("🔑", kw, "#6d28d9", "#ede9fe"))

    # Experience mentioned in title/description
    exp_m = re.search(r'(\d+)\+?\s*(?:years?|ans?|yrs?)\s*(?:of\s*)?(?:experience|expérience)?', desc[:500])
    if exp_m:
        tags.append(("🗓", f"{exp_m.group(1)} ans exp.", "#92400e", "#fef3c7"))

    # Source
    tags.append(("📡", offer.get("source", ""), "#475569", "#f1f5f9"))

    if not tags:
        return ""

    html_tags = "".join(
        f'<span style="display:inline-block;background:{bg};color:{fg};border-radius:4px;'
        f'padding:2px 8px;font-size:11px;font-weight:600;margin:2px 4px 2px 0;white-space:nowrap;">'
        f'{icon} {label}</span>'
        for icon, label, fg, bg in tags
    )
    return f'<div style="margin:8px 0 4px;line-height:1.8;">{html_tags}</div>'


def build_card(offer: dict) -> str:
    score = offer["score"] if offer["score"] is not None else "?"
    score_display = f"{score}/10"
    color = score_color(offer["score"])
    tags_html = extract_tags(offer)

    return f"""
<div style="border:1px solid #e2e8f0;border-radius:10px;padding:16px 18px;margin-bottom:16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:white;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0;">
    <tr>
      <td valign="top" align="left">
        <h3 style="margin:0 0 3px;font-size:15px;font-weight:700;color:#0f172a;line-height:1.3;">{offer['titre']}</h3>
        <p style="margin:0;color:#64748b;font-size:13px;">{offer['entreprise'] or '—'}</p>
      </td>
      <td valign="top" align="right" style="padding-left:12px;width:1%;white-space:nowrap;">
        <div style="color:{color};font-weight:700;font-size:14px;line-height:1.3;">{score_display}</div>
      </td>
    </tr>
  </table>
  {tags_html}
  <p style="margin:8px 0 10px;font-size:13px;color:#475569;font-style:italic;line-height:1.5;">{offer['raison']}</p>
  <a href="{offer['url']}" style="display:inline-block;background:#1d4ed8;color:white;padding:6px 16px;border-radius:6px;font-size:13px;font-weight:500;text-decoration:none;">Voir l'offre →</a>
</div>"""


def build_email(offers: list, failed_sources: list) -> str:
    date_str = datetime.now().strftime("%A %d %B %Y")
    cards = "\n".join(build_card(o) for o in offers)
    warning = ""
    if failed_sources:
        names = ", ".join(failed_sources)
        warning = f'<p style="color:#b45309;font-size:12px;margin-top:20px;padding:10px;background:#fef3c7;border-radius:6px;">⚠️ Sources indisponibles : {names}</p>'

    sources_list = ", ".join(s["name"] for s in SOURCES + build_apify_sources(CONFIG))
    return f"""<!DOCTYPE html>
<html><body style="background:#f1f5f9;padding:24px;margin:0;">
<div style="max-width:620px;margin:0 auto;">
  <div style="background:white;border-radius:12px;padding:24px;margin-bottom:16px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:800;color:#0f172a;margin:0 0 6px;">🎯 Job Digest</h1>
    <p style="color:#64748b;font-size:13px;margin:0 0 4px;">{date_str}</p>
    <p style="color:#64748b;font-size:13px;margin:0;">{len(offers)} offre{"s" if len(offers) > 1 else ""} sélectionnée{"s" if len(offers) > 1 else ""} (score ≥ {CONFIG["settings"]["score_min"]}/10) · Sources : {sources_list}</p>
  </div>
  {cards}
  {warning}
  <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:16px;">Job Agent — {datetime.now().strftime("%Y")}</p>
</div>
</body></html>"""

def build_fallback_email(reason: str) -> str:
    date_str = datetime.now().strftime("%A %d %B %Y")
    postes = ", ".join(CONFIG["mandatory"]["postes"])
    sources_list = ", ".join(s["name"] for s in SOURCES + build_apify_sources(CONFIG))
    return f"""<!DOCTYPE html>
<html><body style="background:#f1f5f9;padding:24px;margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:620px;margin:0 auto;">

  <div style="background:white;border-radius:12px;padding:28px 28px 24px;margin-bottom:12px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:800;color:#0f172a;margin:0 0 4px;">🎯 Job Digest</h1>
    <p style="color:#94a3b8;font-size:13px;margin:0;">{date_str}</p>
  </div>

  <div style="background:white;border-radius:12px;padding:32px 28px;margin-bottom:12px;border:1px solid #e2e8f0;text-align:center;">
    <div style="font-size:40px;margin-bottom:16px;">🔍</div>
    <h2 style="font-size:18px;font-weight:700;color:#0f172a;margin:0 0 10px;">Nothing this week</h2>
    <p style="color:#64748b;font-size:14px;line-height:1.6;margin:0 0 6px;">
      The agent scanned <strong style="color:#0f172a;">{len(SOURCES) + len(build_apify_sources(CONFIG))} sources</strong> but no offer scored above <strong style="color:#0f172a;">{CONFIG["settings"]["score_min"]}/10</strong> this week.
    </p>
    <p style="color:#94a3b8;font-size:13px;margin:0;">Back next Monday with a fresh scan.</p>
  </div>

  <div style="background:white;border-radius:12px;padding:20px 28px;margin-bottom:12px;border:1px solid #e2e8f0;">
    <p style="color:#94a3b8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 12px;">Your criteria</p>
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="padding:4px 0;font-size:13px;color:#64748b;width:40%;">Roles</td>
        <td style="padding:4px 0;font-size:13px;color:#0f172a;font-weight:500;">{postes}</td>
      </tr>
      <tr>
        <td style="padding:4px 0;font-size:13px;color:#64748b;">Min. score</td>
        <td style="padding:4px 0;font-size:13px;color:#0f172a;font-weight:500;">{CONFIG["settings"]["score_min"]}/10</td>
      </tr>
      <tr>
        <td style="padding:4px 0;font-size:13px;color:#64748b;">Sources scanned</td>
        <td style="padding:4px 0;font-size:13px;color:#0f172a;font-weight:500;">{sources_list}</td>
      </tr>
    </table>
  </div>

  <p style="color:#cbd5e1;font-size:11px;text-align:center;margin-top:8px;">Job Agent — {datetime.now().strftime("%Y")}</p>
</div>
</body></html>"""


# ── Email send ───────────────────────────────────────────────────────────────

def send_email(html: str, offer_count: int, fallback: bool = False) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"].strip()
    from_addr = os.environ["EMAIL_FROM"]
    to_addr = os.environ["EMAIL_TO"]

    date_str = datetime.now().strftime("%d/%m/%Y")
    if fallback:
        subject = f"🎯 Job Digest — {date_str} (no results this week)"
    else:
        subject = f"🎯 Job Digest — {date_str} ({offer_count} offre{'s' if offer_count > 1 else ''})"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
    print(f"  ✓ Email sent to {to_addr}")

# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{'='*55}")
    print(f"Job Agent — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}\n")

    state = load_state()
    state = clean_old_entries(state)

    # 1. Collect
    all_offers = []
    failed_sources = []

    apify_sources = build_apify_sources(CONFIG)
    total_sources = len(SOURCES) + len(apify_sources)
    print(f"1. Collecting ({total_sources} sources)...")
    for source in SOURCES:
        print(f"   → {source['name']} (RSS)")
        offers, error = fetch_source(source, CONFIG["settings"]["max_age_days"])
        if error:
            failed_sources.append(source["name"])
            print(f"     ⚠ {error}")
        else:
            print(f"     {len(offers)} offers")
            all_offers.extend(offers)

    for source in apify_sources:
        print(f"   → {source['name']} (Apify)")
        offers, error = fetch_apify_source(source, CONFIG["settings"]["max_age_days"])
        if error:
            failed_sources.append(source["name"])
            print(f"     ⚠ {error}")
        else:
            print(f"     {len(offers)} offers")
            all_offers.extend(offers)

    print(f"\n   Raw total: {len(all_offers)}")

    # 2. Batch deduplication
    seen = set()
    unique = []
    for o in all_offers:
        if o["url"] and o["url"] not in seen:
            seen.add(o["url"])
            unique.append(o)
    print(f"   After batch dedup: {len(unique)}")

    # 3. History deduplication
    new_offers = [o for o in unique if not already_sent(o["url"], state)]
    print(f"   After history dedup: {len(new_offers)}")

    # 4. Filtering
    print("\n2. Filtering (role + geo + sector)...")
    filtered = apply_filters(new_offers)
    print(f"   {len(filtered)} offers retained")

    if not filtered:
        print("\n✗ No offers after filtering — sending fallback email.")
        send_email(build_fallback_email("no offers matched your criteria"), 0, fallback=True)
        save_state(state)
        return

    # 5. LLM scoring
    print(f"\n3. LLM scoring ({len(filtered)} offers)...")
    scored = score_offers(filtered)

    # 6. Filter below score_min
    qualified = [o for o in scored if o["score"] is not None and o["score"] >= CONFIG["settings"]["score_min"]]
    print(f"   {len(qualified)} offers with score ≥ {CONFIG['settings']['score_min']}/10")

    if not qualified:
        print("\n✗ No offers above threshold — sending fallback email.")
        send_email(build_fallback_email("all offers scored below threshold"), 0, fallback=True)
        save_state(state)
        return

    # 7. Sort + top N
    qualified.sort(key=lambda o: -(o["score"] or 0))
    top = qualified[: CONFIG["settings"]["top_n"]]
    print(f"\n4. Top {len(top)} offers selected")
    for o in top:
        print(f"   {o['score']}/10 — {o['titre'][:50]}")

    # 8. Send email
    print("\n5. Sending email...")
    html = build_email(top, failed_sources)
    send_email(html, len(top))

    # 9. Mark as sent (all scored offers, not just top N)
    state = mark_sent([o["url"] for o in scored if o.get("url")], state)
    save_state(state)

    print(f"\n✓ Done — {len(top)} offers sent.\n")


if __name__ == "__main__":
    main()
