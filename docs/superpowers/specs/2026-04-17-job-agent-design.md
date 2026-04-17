# Job Agent — Design Spec

**Date :** 2026-04-17
**Plateforme :** n8n self-hosted
**Delivery :** Email digest hebdomadaire (lundi matin)

---

## Objectif

Agent automatisé qui collecte les offres d'emploi pertinentes depuis plusieurs plateformes, les filtre par règles puis les score via LLM (Claude API), et envoie un digest email hebdomadaire classé du plus au moins pertinent.

---

## Sources

| Source | Méthode | Zone géo |
|---|---|---|
| Remotive | RSS natif | Remote international |
| We Work Remotely | RSS natif | Remote international |
| Jobs That Make Sense | RSS / API | Remote international |
| Indeed.es | RSS de recherche | Espagne + Remote |
| Welcome to the Jungle | RSS de recherche | Espagne + Remote |
| InfoJobs | API officielle | Espagne |
| Tecnoempleo | RSS | Espagne (tech) |
| Computrabajo | RSS / scrape | Espagne |
| LinkedIn | RSS de recherche (limité) | Espagne + Remote |

Toutes les requêtes incluent un filtre géographique : **Donostia / Espagne / Full Remote**.

---

## Configuration des critères

Nœud JSON unique en tête de workflow, modifiable sans toucher la logique :

```json
{
  "postes": ["Product Manager", "Data Product Manager"],
  "contrats": ["CDI"],
  "salaire_min": 45000,
  "teletravail": "full",
  "secteurs_ok": ["tech", "impact", "SaaS"],
  "secteurs_nok": ["défense", "gambling", "crypto"],
  "experience_min": 3,
  "experience_max": 5,
  "stack": ["n8n", "claude code", "Notion", "Jira", "SQL"],
  "keywords": ["n8n", "claude code", "ai agents", "LLM", "automation"],
  "langues": ["fr", "en", "es"],
  "max_age_days": 7,
  "top_n": 15
}
```

---

## Architecture du workflow n8n

```
[Cron — lundi 08h00]
        │
        ▼
[Collecte parallèle — 9 sources]
  ├── Remotive RSS
  ├── We Work Remotely RSS
  ├── Jobs That Make Sense RSS/API
  ├── Indeed.es RSS
  ├── Welcome to the Jungle RSS
  ├── InfoJobs API
  ├── Tecnoempleo RSS
  ├── Computrabajo RSS/scrape
  └── LinkedIn RSS
        │
        ▼
[Merge + Normalisation]
  → Format unifié : { titre, entreprise, url, description, date, source, localisation }
        │
        ▼
[Déduplication]
  → Comparaison par URL via Static Data (persistant entre exécutions)
  → Les offres déjà envoyées sont exclues
        │
        ▼
[Filtrage par règles — critères durs]
  → Contrat ∈ contrats
  → Télétravail = full
  → Date publication ≤ max_age_days
  → Langue ∈ langues
  → Secteur ∉ secteurs_nok
  → Poste contient un des termes de postes (titre ou description)
        │
        ▼
[Scoring LLM — Claude API]
  → Batch des offres survivantes
  → Prompt : profil complet + critères + offre → score 1-10 + justification 2 lignes
  → Réponse : { score: 8, raison: "PM senior SaaS, full remote, stack alignée" }
        │
        ▼
[Tri par score décroissant — garde top_n]
        │
        ▼
[Génération email HTML]
  → Une carte par offre, classées du plus au moins pertinent
  → Si aucune offre : pas d'email envoyé
  → Si sources en erreur : avertissement en bas du mail
        │
        ▼
[Envoi email via SMTP]
```

---

## Format du digest email

Email HTML avec une carte par offre, triées par score décroissant.

**Structure d'une carte :**
- Titre du poste + nom de l'entreprise
- Source + localisation
- Score de pertinence (1-10)
- Justification LLM (2 lignes)
- Lien direct vers l'offre

**Cas limites :**
- Aucune offre après filtrage → email non envoyé
- Sources indisponibles → ligne d'avertissement en bas : `⚠️ Sources indisponibles cette semaine : [liste]`

---

## Déduplication

- Stockage des URLs envoyées dans le **Static Data** n8n (persistant entre exécutions)
- Une offre ne peut apparaître qu'une seule fois dans l'historique des digests
- Nettoyage automatique des URLs de plus de 30 jours pour éviter la croissance infinie

---

## Prompt LLM

```
Tu es un assistant de recherche d'emploi. Évalue la pertinence de cette offre pour ce profil.

PROFIL :
- Postes recherchés : {postes}
- Contrats : {contrats}
- Salaire min : {salaire_min}€
- Télétravail : {teletravail}
- Secteurs appréciés : {secteurs_ok}
- Secteurs à éviter : {secteurs_nok}
- Expérience : {experience_min}-{experience_max} ans
- Stack / outils : {stack}
- Keywords d'intérêt : {keywords}
- Langues : {langues}

OFFRE :
Titre : {titre}
Entreprise : {entreprise}
Localisation : {localisation}
Description : {description}

Réponds uniquement en JSON : { "score": <1-10>, "raison": "<2 phrases max>" }
```

---

## Gestion des erreurs

| Situation | Comportement |
|---|---|
| Source RSS / API indisponible | Workflow continue, source listée dans l'avertissement email |
| Aucune offre après filtrage | Email non envoyé |
| Erreur LLM | Offre conservée avec score null, placée en fin de digest |
| Erreur SMTP | Log d'erreur n8n, pas de retry automatique |

---

## Hors scope

- Interface web de configuration (les critères se modifient directement dans le nœud Config)
- Historique consultable des offres passées
- Désabonnement / multi-utilisateurs
- Scraping avancé via Apify (peut être ajouté si RSS insuffisants)
