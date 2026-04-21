# Design — Notion Playbook : Agent de recherche de mission

**Date :** 2026-04-21
**Destination :** Page Notion `3490e9cc66ec809382c4fe88d072b009`
**Audience :** Utilisateurs non-techniques ayant commenté un post LinkedIn
**Langue :** Français, tutoiement
**Format :** Cookbook avec checkboxes (option B)

---

## Structure générale

### Section 1 — Pourquoi cet agent va changer ta façon de chercher

- Callout orange "Le problème" : scanner 8 plateformes manuellement, se noyer dans les offres hors-sujet, rater les bonnes parce qu'elles ont été publiées un mercredi
- Callout vert "La solution" : agent automatique, 8 sources, filtre par critères, score IA 1-10, email digest chaque lundi
- Ligne de résumé : "Tu ouvres ton lundi avec une liste prête à l'emploi."

### Section 2 — Ce dont tu as besoin avant de commencer

Checklist de départ (5 éléments) :
- Compte GitHub (gratuit)
- Compte Gmail
- Compte Anthropic (gratuit + configurer une clé API)
- Compte Apify (plan gratuit $5/mois largement suffisant)
- ~30 minutes la première fois

- Callout bleu : "Aucun terminal, aucune ligne de code à écrire. Tout se fait dans le navigateur."
- Callout jaune budget : "Coût après les crédits gratuits : ~1,64€/mois. GitHub Actions est gratuit."

---

### Section 3 — Les étapes

#### Étape 1 — Crée tes comptes et récupère tes clés

**1a — Clé Anthropic (Claude AI)**
- Aller sur console.anthropic.com → créer un compte
- Menu gauche → "API Keys" → bouton "Create Key"
- Nommer la clé (ex: "Job Agent"), copier la valeur (`sk-ant-...`)
- Aller dans "Billing" → ajouter $5 de crédit (suffisant pour plusieurs mois)
- Callout rouge : "Copie cette clé maintenant et garde-la quelque part — elle ne sera plus visible après."

**1b — Token Apify**
- Aller sur apify.com → créer un compte
- Cliquer sur l'icône de profil (haut droite) → "Settings"
- Onglet "Integrations" → section "API tokens"
- Copier le token existant ou en créer un nouveau (`apify_api_...`)
- Callout vert : "Le plan gratuit offre $5/mois de crédit — largement suffisant pour un usage personnel."

**1c — Mot de passe Gmail App**
- Aller sur myaccount.google.com → "Sécurité"
- S'assurer que la "Validation en 2 étapes" est activée (obligatoire)
- Chercher "Mots de passe des applications" → créer un nouveau (nom : "Job Agent")
- Copier le mot de passe à 16 caractères affiché (ex : `abcd efgh ijkl mnop`)
- Callout rouge : "Ce n'est pas ton mot de passe Gmail habituel. C'est un mot de passe spécial généré par Google uniquement pour cette application."
- Callout jaune : "Si tu ne vois pas 'Mots de passe des applications', c'est que la validation en 2 étapes n'est pas encore activée."

---

#### Étape 2 — Fork le projet sur GitHub

- Créer un compte sur github.com si ce n'est pas déjà fait
- Aller sur `https://github.com/LouisBurette/job-search-agent`
- Cliquer sur le bouton "Fork" (haut droite de la page)
- Laisser les options par défaut → cliquer "Create fork"
- Callout bleu : "Forker = faire une copie personnelle du projet sous ton compte. Tu pourras le modifier sans toucher à l'original."

---

#### Étape 3 — Ajoute tes clés en secrets GitHub

Dans ton fork, aller dans **Settings → Secrets and variables → Actions → New repository secret**

Ajouter ces 8 secrets un par un :

| Nom du secret | Valeur |
|---|---|
| `ANTHROPIC_API_KEY` | Ta clé Anthropic (`sk-ant-...`) |
| `APIFY_API_TOKEN` | Ton token Apify (`apify_api_...`) |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | Ton adresse Gmail |
| `SMTP_PASS` | Ton mot de passe App à 16 caractères |
| `EMAIL_FROM` | Ton adresse Gmail |
| `EMAIL_TO` | L'adresse qui recevra le digest |

- Callout bleu : "EMAIL_FROM et EMAIL_TO peuvent être la même adresse (tu t'envoies le digest à toi-même)."
- Callout rouge sécurité : "Ces secrets sont stockés de façon chiffrée par GitHub. Ils ne sont jamais visibles dans le code. Ne les mets JAMAIS directement dans un fichier."

---

#### Étape 4 — Configure ta recherche

Dans ton fork, cliquer sur le fichier `job_agent.py` → icône crayon (haut droite) pour l'éditer.

Aller à la ligne ~29 — c'est le bloc `CONFIG`. C'est **le seul endroit à modifier**.

Explication champ par champ :
- `postes` : les titres de postes recherchés (ex: `["Product Manager", "Chef de projet"]`)
- `secteurs_nok` : secteurs à exclure (ex: `["defense", "casino"]`)
- `stack` : outils que tu maîtrises et qui boostent le score (ex: `["Notion", "SQL"]`)
- `keywords` : mots-clés importants pour toi (ex: `["impact", "startup"]`)
- `salaire_min` : salaire minimum indicatif (utilisé par l'IA pour scorer)
- `experience_min` / `experience_max` : années d'expérience attendues
- `apify.query` : terme de recherche principal envoyé aux plateformes (ex: `"product manager"`)
- `apify.indeed_fr_location` : ville pour Indeed France (ex: `"Paris"`)
- `apify.indeed_es_location` : ville pour Indeed Espagne
- `apify.wttj_contract` : type de contrat sur WTTJ (`"CDI"`, `"Freelance"`, etc.)

Callout rouge : "Ne mets jamais tes clés API dans ce fichier. Elles restent dans GitHub Secrets (étape 3)."
Callout bleu : "Pour la localisation, l'agent garde les offres full remote ET les offres dans ta zone géographique."

Une fois modifié → cliquer "Commit changes" (bouton vert) → "Commit directly to the main branch".

---

#### Étape 5 — Lance l'agent

**Option A — Sur GitHub Actions** *(recommandé)*

Dans ton fork → onglet "Actions" → "Weekly Job Digest" → bouton "Run workflow" → "Run workflow"

Tu recevras le digest dans quelques minutes. Ensuite, il tourne automatiquement **chaque lundi à 9h**.

Callout orange : "C'est l'option recommandée — tu configures une fois, ça tourne tout seul, même si ton ordinateur est éteint."

**Option B — En local** *(pour tester uniquement)*

Nécessite Python installé sur ta machine. Tu dois être connecté et allumé au moment du lancement.

Callout jaune : "En local, l'agent ne se lance pas automatiquement. Il faut le démarrer manuellement à chaque fois. Pour un usage régulier, préfère l'option GitHub Actions."

---

### Section 4 — Ce que tu vas recevoir

Description du digest email : liste des X meilleures offres scorées, avec titre, entreprise, localisation, score IA, lien direct. Les offres déjà vues ne reviennent jamais (mémoire 30 jours).

---

### Section 5 — Coûts

Tableau récapitulatif :
- Anthropic Claude : ~$0.01/run → ~$0.04/mois
- Apify : ~$0.40/run → ~$1.60/mois
- GitHub Actions : gratuit
- **Total : ~1,64€/mois**

Callout vert : "Les crédits gratuits d'Anthropic et Apify couvrent les premiers mois."

---

## Notes de mise en forme Notion

- Encadrés colorés : rouge (danger/attention), orange (recommandation), vert (info positive), bleu (info neutre), jaune (avertissement doux)
- Checkboxes pour chaque action concrète de l'utilisateur
- Tableaux pour les secrets et les coûts
- Séparateurs entre chaque étape
- Icônes d'étape : 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣
