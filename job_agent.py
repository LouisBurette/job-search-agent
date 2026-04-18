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
    "postes": ["Product Manager", "Data Product Manager"],
    "contrats": ["CDI"],
    "salaire_min": 45000,
    "teletravail": "full",
    "secteurs_ok": ["tech", "impact", "SaaS"],
    "secteurs_nok": ["défense", "defense", "gambling", "casino", "crypto", "jeux d'argent", "armement", "weapons"],
    "experience_min": 3,
    "experience_max": 5,
    "stack": ["n8n", "claude", "Notion", "Jira", "SQL", "Airtable"],
    "keywords": ["ai agents", "LLM", "automation", "no-code", "low-code", "impact", "ESS", "ONG"],
    "langues": ["fr", "en", "es"],
    "max_age_days": 7,
    "top_n": 15,
    "score_min": 5,
    # Apify scraping parameters — injected into requests, edit here to change the search
    "apify": {
        "query": "product manager",          # main search term
        "max_items_per_source": 25,          # limit per source (cost control)
        "indeed_es_location": "Donostia San Sebastian",
        "indeed_fr_location": "Bayonne",
        "linkedin_filters": "f_WT=2&f_JT=F&f_TPR=r604800",  # remote + full-time + last 7 days
        "wttj_contract": "CDI",
    },
}

# Accepted geographic areas (outside full remote)
GEO_LOCAL = [
    "donostia", "san sebastián", "san sebastian", "gipuzkoa", "pays basque", "país vasco", "euskadi",
    "bayonne", "biarritz", "anglet", "hendaye", "bidart", "saint-jean-de-luz",
    "saint jean de luz", "pyrénées-atlantiques", "côte basque",
]

REMOTE_KEYWORDS = [
    "remote", "full remote", "fully remote", "100% remote", "remote-first",
    "télétravail", "teletrabajo", "home office", "distributed",
]

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
    q = ap["query"]
    n = ap["max_items_per_source"]
    from urllib.parse import quote_plus
    return [
        {
            "name": "Indeed.es",
            "actor_id": "BIeK7ZcYUrdxDgOEQ",
            "input": {"position": q, "location": ap["indeed_es_location"], "country": "ES", "maxItems": n},
            "default_location": "Donostia / Espagne",
        },
        {
            "name": "Indeed.fr",
            "actor_id": "BIeK7ZcYUrdxDgOEQ",
            "input": {"position": q, "location": ap["indeed_fr_location"], "country": "FR", "maxItems": n},
            "default_location": "Pays Basque FR",
        },
        {
            "name": "LinkedIn",
            "actor_id": "JkfTWxtpgfvcRQn3p",
            "input": {
                "searchUrl": f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(q)}&{ap['linkedin_filters']}",
                "maxItems": n,
            },
            "default_location": "Remote",
        },
        {
            "name": "Welcome to the Jungle",
            "actor_id": "ip6ZC7cs8a1YUxBoC",
            "input": {
                "startUrls": [
                    {"url": f"https://www.welcometothejungle.com/fr/jobs?query={quote_plus(q)}&refinementList[contract_type][]={ap['wttj_contract']}&refinementList[remote][]=fulltime"},
                    {"url": f"https://www.welcometothejungle.com/fr/jobs?query={quote_plus(q)}&refinementList[contract_type][]={ap['wttj_contract']}&refinementList[offices.country_code][]=ES"},
                ],
                "maxItems": n,
            },
            "default_location": "Remote / Espagne",
        },
    ]

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

    if source_name.startswith("Indeed"):
        title = item.get("title", {})
        loc = item.get("location", {})
        salary = item.get("salary", {})
        company = item.get("company", {})
        return {
            "titre": title.get("text", "") if isinstance(title, dict) else str(title),
            "entreprise": company.get("name", "") if isinstance(company, dict) else "",
            "url": (item.get("urls") or {}).get("indeed") or (item.get("urls") or {}).get("external") or "",
            "description": item.get("description") or item.get("snippet", {}).get("text", "") if isinstance(item.get("snippet"), dict) else item.get("description", ""),
            "date": item.get("datePosted") or item.get("date") or "",
            "source": source_name,
            "localisation": f"{loc.get('city', '')} {loc.get('countryCode', '')}".strip() if isinstance(loc, dict) else default_location,
            "salaire": salary.get("text", "") if isinstance(salary, dict) else "",
        }

    if source_name == "LinkedIn":
        return {
            "titre": item.get("job_title", ""),
            "entreprise": item.get("company_name", ""),
            "url": item.get("job_url", ""),
            "description": item.get("job_description", ""),
            "date": item.get("time_posted", ""),
            "source": source_name,
            "localisation": item.get("location", default_location),
            "salaire": item.get("salary_range", ""),
        }

    if source_name == "Welcome to the Jungle":
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
        return {
            "titre": item.get("title", ""),
            "entreprise": item.get("companyName", ""),
            "url": item.get("url", ""),
            "description": item.get("description") or item.get("companyDescription", ""),
            "date": item.get("publishedAt", ""),
            "source": source_name,
            "localisation": loc,
            "salaire": salaire,
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

def matches_poste(offer: dict) -> bool:
    text = f"{offer['titre']} {offer['description']}".lower()
    return any(p.lower() in text for p in CONFIG["postes"])


def matches_geo(offer: dict) -> bool:
    loc = offer.get("localisation", "").lower()
    desc = offer.get("description", "").lower()

    # 1. Location explicitly remote
    if any(k in loc for k in REMOTE_KEYWORDS):
        return True
    # 2. Description mentions full remote
    if any(k in desc for k in REMOTE_KEYWORDS):
        return True
    # 3. Location in accepted area
    if any(g in loc for g in GEO_LOCAL):
        return True
    return False


def avoids_secteur(offer: dict) -> bool:
    text = f"{offer['titre']} {offer['description']}".lower()
    return not any(s.lower() in text for s in CONFIG["secteurs_nok"])


def apply_filters(offers: list) -> list:
    return [
        o for o in offers
        if o.get("url") and matches_poste(o) and matches_geo(o) and avoids_secteur(o)
    ]

# ── Scoring LLM ──────────────────────────────────────────────────────────────

def build_prompt(offer: dict) -> str:
    return f"""Tu es un expert en recrutement. Évalue cette offre pour ce profil de Product Manager.

PROFIL RECHERCHÉ :
- Postes : Product Manager, Data Product Manager
- Contrat : CDI uniquement
- Salaire minimum : 45 000€/an
- Localisation : full remote (partout dans le monde) OU Donostia/San Sebastián OU Pays Basque français (Bayonne, Biarritz, Anglet...)
- Expérience : 3 à 5 ans en Product Management
- Stack appréciée : {', '.join(CONFIG['stack'])}
- Mots-clés d'intérêt : {', '.join(CONFIG['keywords'])}
- Langues : français, anglais, espagnol

GRILLE DE NOTATION (sois précis, utilise toute l'échelle) :

10/10 — Offre idéale : TOUS ces critères réunis :
  ✓ Secteur à impact positif (social, environnement, ESS, ONG, philanthropie, éducation, santé publique, civic tech)
  ✓ Full remote ou localisation Donostia / Pays Basque
  ✓ Salaire ≥ 45 000€ mentionné
  ✓ Expérience 3-5 ans requise
  ✓ Titre = Product Manager ou Data Product Manager
  ✓ Au moins un mot-clé de la stack présent (n8n, automation, LLM, AI agents, no-code...)

8-9/10 — Très bonne offre : Impact positif + remote/Donosti + PM confirmé, mais 1-2 manques mineurs (salaire non précisé, stack peu alignée, expérience légèrement hors range).

6-7/10 — Bonne opportunité : Remote/Donosti + PM + secteur tech/SaaS correct, mais impact sociétal faible ou salaire incertain ou stack éloignée.

5/10 — Acceptable : Localisation ok + titre PM, mais secteur neutre, peu d'alignement stack, critères secondaires faibles.

1-4/10 — Mauvaise adéquation : Localisation contraignante non remote, secteur à éviter, titre éloigné de PM, profil très senior (VP, Director) ou très junior (Associate, intern), ou CDD/freelance.

RÈGLES IMPORTANTES :
- "Crypto", "gambling", "casino", "défense", "armement" → score ≤ 2 obligatoirement
- "Director of Product", "VP Product", "CPO" → score ≤ 5 (trop senior)
- "Junior PM", "Associate PM", "Intern" → score ≤ 4 (trop junior)
- Si le salaire est clairement < 45k€ → pénalise de 2 points

OFFRE À ÉVALUER :
Titre : {offer['titre']}
Entreprise : {offer['entreprise']}
Source : {offer['source']}
Localisation : {offer['localisation']}
Salaire : {offer['salaire'] or 'non précisé'}
Description : {offer['description'][:2000]}

Réponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant ou après :
{{"score": <entier 1-10>, "raison": "<2 phrases max en français, justifie le score avec les points forts et faiblesses>", "tags_detectes": {{"remote": <bool>, "impact": <bool>, "salaire_ok": <bool>, "experience_ok": <bool>, "stack_match": [<liste des mots-clés matchés>]}}}}"""


def score_offers(offers: list) -> list:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    scored = []
    for i, offer in enumerate(offers):
        print(f"  Scoring {i+1}/{len(offers)}: {offer['titre'][:55]}")
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                messages=[{"role": "user", "content": build_prompt(offer)}],
            )
            raw = response.content[0].text.strip()
            parsed = json.loads(raw)
            offer["score"] = int(parsed.get("score", 0))
            offer["raison"] = parsed.get("raison", "")
            offer["tags_detectes"] = parsed.get("tags_detectes", {})
        except Exception as e:
            print(f"    ⚠ Score error: {e}")
            offer["score"] = None
            offer["raison"] = "Score unavailable"
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

    # Location
    is_local = any(g in loc for g in GEO_LOCAL)
    is_remote = td.get("remote") or any(k in loc for k in REMOTE_KEYWORDS)

    if any(g in loc for g in ["donostia", "san sebasti"]):
        tags.append(("📍", "Donostia", "#7c3aed", "#f3e8ff"))
    elif any(g in loc for g in ["bayonne", "biarritz", "anglet", "hendaye", "bidart"]):
        tags.append(("📍", "Pays Basque FR", "#7c3aed", "#f3e8ff"))
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

    # Stack match
    stack_match = td.get("stack_match", [])
    for kw in stack_match[:3]:
        tags.append(("⚙️", kw, "#1d4ed8", "#eff6ff"))

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
    <p style="color:#64748b;font-size:13px;margin:0;">{len(offers)} offre{"s" if len(offers) > 1 else ""} sélectionnée{"s" if len(offers) > 1 else ""} (score ≥ 5/10) · Sources : {sources_list}</p>
  </div>
  {cards}
  {warning}
  <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:16px;">Job Agent — {datetime.now().strftime("%Y")}</p>
</div>
</body></html>"""

# ── Email send ───────────────────────────────────────────────────────────────

def send_email(html: str, offer_count: int) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"].strip()
    from_addr = os.environ["EMAIL_FROM"]
    to_addr = os.environ["EMAIL_TO"]

    date_str = datetime.now().strftime("%d/%m/%Y")
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
        offers, error = fetch_source(source, CONFIG["max_age_days"])
        if error:
            failed_sources.append(source["name"])
            print(f"     ⚠ {error}")
        else:
            print(f"     {len(offers)} offers")
            all_offers.extend(offers)

    for source in apify_sources:
        print(f"   → {source['name']} (Apify)")
        offers, error = fetch_apify_source(source, CONFIG["max_age_days"])
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
        print("\n✗ No offers after filtering — email not sent.")
        save_state(state)
        return

    # 5. LLM scoring
    print(f"\n3. LLM scoring ({len(filtered)} offers)...")
    scored = score_offers(filtered)

    # 6. Filter below score_min
    qualified = [o for o in scored if o["score"] is not None and o["score"] >= CONFIG["score_min"]]
    print(f"   {len(qualified)} offers with score ≥ {CONFIG['score_min']}/10")

    if not qualified:
        print("\n✗ No offers above threshold — email not sent.")
        save_state(state)
        return

    # 7. Sort + top N
    qualified.sort(key=lambda o: -(o["score"] or 0))
    top = qualified[: CONFIG["top_n"]]
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
