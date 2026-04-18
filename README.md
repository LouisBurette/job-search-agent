# Job Search Agent

An automated job digest delivered to your inbox every Monday morning.

The agent scans 8 job platforms, filters offers by your criteria (role, location, sector), scores each one from 1 to 10 using Claude AI, and sends you a clean HTML email with only the most relevant opportunities.

**Example digest:**

![digest screenshot — coming soon]()

---

## How it works

1. Every Monday at 9am, a GitHub Action triggers the script
2. The agent collects offers from 8 sources (Indeed, LinkedIn, Welcome to the Jungle, RemoteOK, Jobicy, Jobspresso, We Work Remotely)
3. It filters by role, location, and excluded sectors
4. Claude AI scores each offer from 1 to 10 based on your profile
5. Only offers scoring ≥ 5/10 appear in the email, sorted best first
6. Offers you've already seen are never shown again (30-day memory)

---

## Setup (step by step)

### Step 1 — Get your API keys

You need three credentials. Each has a free tier that covers personal use.

**Anthropic (Claude AI) — for scoring offers**
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account
3. Go to **API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-...`)
5. Add a small credit ($5 is enough for months of use at ~$0.01/run)

**Apify — for scraping Indeed, LinkedIn, WTTJ**
1. Go to [apify.com](https://apify.com)
2. Create an account (free tier includes $5/month)
3. Go to **Settings** → **Integrations** → **API tokens**
4. Copy your token (starts with `apify_api_...`)

**Gmail App Password — for sending the email**
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. You need 2-step verification enabled on your Google account first
3. Create a new App Password (name it "Job Agent")
4. Copy the 16-character password shown (e.g. `abcd efgh ijkl mnop`)

---

### Step 2 — Fork this repository

1. Click **Fork** at the top right of this page
2. This creates a copy of the project under your GitHub account

---

### Step 3 — Add your credentials as secrets

In your forked repo, go to **Settings → Secrets and variables → Actions → New repository secret**

Add each of these one by one:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic key (`sk-ant-...`) |
| `APIFY_API_TOKEN` | Your Apify token (`apify_api_...`) |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASS` | Your 16-character App Password |
| `EMAIL_FROM` | Your Gmail address |
| `EMAIL_TO` | The email address to receive the digest |

> `EMAIL_FROM` and `EMAIL_TO` can be the same address (send to yourself).

---

### Step 4 — Configure your search criteria

Open `job_agent.py` in your fork (click the file, then the pencil icon to edit).

Find the `CONFIG` block at the top of the file (~line 29) and edit it to match your profile:

```python
CONFIG = {
    # Job titles to look for — add as many as you want
    "postes": ["Product Manager", "Data Product Manager"],

    # Minimum salary (used by the AI scorer, not a hard filter)
    "salaire_min": 45000,

    # Sectors to EXCLUDE — offers mentioning these words score ≤ 2/10
    "secteurs_nok": ["defense", "gambling", "casino", "crypto", "weapons"],

    # Years of experience expected
    "experience_min": 3,
    "experience_max": 5,

    # Tools and keywords that boost the score if mentioned
    "stack": ["n8n", "claude", "Notion", "Jira", "SQL", "Airtable"],
    "keywords": ["ai agents", "LLM", "automation", "no-code", "impact"],

    # Only show offers from the last N days
    "max_age_days": 7,

    # Maximum number of offers in the email
    "top_n": 15,

    # Minimum score to appear in the email (1–10)
    "score_min": 5,

    # Search parameters sent to scraping sources
    "apify": {
        "query": "product manager",           # Main search term
        "max_items_per_source": 25,           # Offers fetched per source
        "indeed_es_location": "Donostia San Sebastian",
        "indeed_fr_location": "Bayonne",
        "wttj_contract": "CDI",
    },
}
```

**Geographic filter:** The agent keeps only offers that are full remote, or located in the Basque Country (Donostia, Bayonne, Biarritz, etc.). To change this, edit the `GEO_LOCAL` list further down in the file.

Commit your changes (click **Commit changes** in GitHub's editor).

---

### Step 5 — Run it

Go to **Actions → Weekly Job Digest → Run workflow → Run workflow**

You'll receive your first digest within a few minutes.

After that, it runs automatically every Monday at 9am (French time).

---

## Costs

| Service | Cost per run | Monthly (4 runs) |
|---|---|---|
| Anthropic (Claude) | ~$0.01 | ~$0.04 |
| Apify (scraping) | ~$0.40 | ~$1.60 |
| GitHub Actions | Free | Free |
| **Total** | **~$0.41** | **~$1.64** |

Both Anthropic and Apify offer free credits that cover several months of personal use.

---

## Sources

| Platform | Type | Coverage |
|---|---|---|
| Indeed.es | Apify scraper | Donostia / Spain |
| Indeed.fr | Apify scraper | Basque Country FR |
| LinkedIn | Apify scraper | Remote worldwide |
| Welcome to the Jungle | Apify scraper | Remote + Spain |
| RemoteOK | RSS | Remote worldwide |
| Jobicy | RSS | Remote worldwide |
| Jobspresso | RSS | Remote worldwide |
| We Work Remotely | RSS | Remote worldwide |

---

## Built with

- Python 3.9+
- [Anthropic Claude API](https://console.anthropic.com) — offer scoring
- [Apify](https://apify.com) — web scraping (Indeed, LinkedIn, WTTJ)
- GitHub Actions — weekly scheduling
- feedparser — RSS parsing
- Gmail SMTP — email delivery
