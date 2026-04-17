// scripts/filter.js
// Logique de filtrage copiée dans le Function node n8n

function matchesGeo(localisation, geo) {
  if (!localisation) return false;
  const loc = localisation.toLowerCase();
  return geo.some(g => loc.includes(g.toLowerCase()));
}

function matchesPoste(titre, description, postes) {
  const text = `${titre} ${description}`.toLowerCase();
  return postes.some(p => text.includes(p.toLowerCase()));
}

function matchesLangue(description, langues) {
  const frWords = ['expérience', 'poste', 'entreprise', 'recherchons'];
  const enWords = ['experience', 'position', 'company', 'looking'];
  const esWords = ['experiencia', 'puesto', 'empresa', 'buscamos'];

  const desc = description.toLowerCase();
  const hasFr = frWords.some(w => desc.includes(w));
  const hasEn = enWords.some(w => desc.includes(w));
  const hasEs = esWords.some(w => desc.includes(w));

  if (langues.includes('fr') && hasFr) return true;
  if (langues.includes('en') && hasEn) return true;
  if (langues.includes('es') && hasEs) return true;
  if (!hasFr && !hasEn && !hasEs) return true;
  return false;
}

function matchesTeletravail(description, localisation) {
  const text = `${description} ${localisation}`.toLowerCase();
  return (
    text.includes('remote') ||
    text.includes('télétravail') ||
    text.includes('teletrabajo') ||
    text.includes('full remote') ||
    text.includes('100% remote') ||
    localisation.toLowerCase().includes('remote')
  );
}

function avoidsSecteur(description, titre, secteurs_nok) {
  const text = `${titre} ${description}`.toLowerCase();
  return !secteurs_nok.some(s => text.includes(s.toLowerCase()));
}

module.exports = { matchesGeo, matchesPoste, matchesLangue, matchesTeletravail, avoidsSecteur };
