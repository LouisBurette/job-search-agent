// scripts/score-prompt.js
// Construction du prompt LLM pour le scoring d'offre

function buildPrompt(config, offer) {
  return `Tu es un assistant de recherche d'emploi. Évalue la pertinence de cette offre pour ce profil.

PROFIL :
- Postes recherchés : ${config.postes.join(', ')}
- Contrats : ${config.contrats.join(', ')}
- Salaire min : ${config.salaire_min}€
- Télétravail : ${config.teletravail}
- Secteurs appréciés : ${config.secteurs_ok.join(', ')}
- Secteurs à éviter : ${config.secteurs_nok.join(', ')}
- Expérience : ${config.experience_min}-${config.experience_max} ans
- Stack / outils : ${config.stack.join(', ')}
- Keywords d'intérêt : ${config.keywords.join(', ')}
- Langues : ${config.langues.join(', ')}

OFFRE :
Titre : ${offer.titre}
Entreprise : ${offer.entreprise}
Source : ${offer.source}
Localisation : ${offer.localisation}
Salaire : ${offer.salaire || 'non précisé'}
Description : ${offer.description.substring(0, 1500)}

Réponds UNIQUEMENT en JSON valide, sans markdown, sans commentaire :
{ "score": <entier 1-10>, "raison": "<2 phrases max en français>" }`;
}

module.exports = { buildPrompt };
