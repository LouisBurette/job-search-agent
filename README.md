# Job Agent

Workflow n8n self-hosted — digest email hebdomadaire d'offres d'emploi.

## Setup

1. Importer `workflows/job-agent.json` dans n8n (Settings → Import Workflow)
2. Configurer les credentials dans n8n :
   - **Anthropic API** : clé API depuis console.anthropic.com
   - **SMTP** : paramètres de ton serveur email
   - **InfoJobs** : clé API depuis developer.infojobs.net
3. Configurer les variables n8n (Settings → Variables) :
   - `ANTHROPIC_API_KEY` : ta clé Anthropic
   - `EMAIL_FROM` : adresse d'envoi
   - `EMAIL_TO` : adresse de réception
4. Activer le workflow

## Sources

| Source | Type | Zone |
|---|---|---|
| Remotive | RSS | Remote international |
| We Work Remotely | RSS | Remote international |
| Jobs That Make Sense | RSS/API | Remote international |
| Indeed.es | RSS | Donostia + Remote |
| Welcome to the Jungle | RSS | Espagne + Remote |
| InfoJobs | API | Espagne |
| Tecnoempleo | RSS | Espagne tech |
| Computrabajo | RSS | Espagne |
| LinkedIn | RSS | Donostia + Remote |

## Modifier les critères

Ouvrir le nœud **Config** dans n8n et modifier le JSON.
