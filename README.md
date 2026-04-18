# Job Agent

Agent de veille emploi automatisé — reçois chaque lundi matin un digest email des offres pertinentes, scorées par IA.

**Sources :** Indeed (ES + FR), LinkedIn, Welcome to the Jungle, RemoteOK, Jobicy, Jobspresso, We Work Remotely
**Scoring :** Claude (Anthropic) note chaque offre de 1 à 10 selon tes critères
**Déduplication :** les offres déjà vues ne remontent pas (fenêtre 30 jours)

---

## Prérequis

- Compte [Anthropic](https://console.anthropic.com) — clé API (~0.01€/run)
- Compte [Apify](https://apify.com) — token API (~0.40€/run, offre gratuite disponible)
- Compte Gmail avec un [App Password](https://myaccount.google.com/apppasswords) activé

## Installation

```bash
git clone https://github.com/TON_USERNAME/job-agent.git
cd job-agent
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` en `.env` et renseigne tes credentials :

```bash
cp .env.example .env
```

## Configuration

Modifie le bloc `CONFIG` en haut de `job_agent.py` :

```python
CONFIG = {
    "postes": ["Product Manager", "Data Product Manager"],
    "score_min": 5,
    "apify": {
        "query": "product manager",
        "max_items_per_source": 25,
        "indeed_es_location": "Donostia San Sebastian",
        "indeed_fr_location": "Bayonne",
    }
}
```

## Lancer manuellement

```bash
.venv/bin/python job_agent.py
```

## Automatiser avec GitHub Actions

Pour recevoir le digest chaque lundi à 9h sans laisser ton ordinateur allumé :

1. Fork ce repo sur GitHub
2. Va dans **Settings → Secrets and variables → Actions**
3. Ajoute chaque variable de ton `.env` comme secret
4. Le workflow `.github/workflows/weekly-digest.yml` se déclenche automatiquement

Tu peux aussi lancer manuellement depuis **Actions → Weekly Job Digest → Run workflow**.
