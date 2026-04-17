// Normalise une offre brute vers le format unifié
// Input: rawItem (objet avec des champs variables selon la source)
// Output: { titre, entreprise, url, description, date, source, localisation, salaire }
function normalize(rawItem, source) {
  return {
    titre: rawItem.titre || rawItem.title || rawItem.positionName || '',
    entreprise: rawItem.entreprise || rawItem.company || rawItem.companyName || '',
    url: rawItem.url || rawItem.link || rawItem.jobUrl || '',
    description: rawItem.description || rawItem.content || rawItem.snippet || '',
    date: rawItem.date || rawItem.pubDate || rawItem.publishedAt || new Date().toISOString(),
    source: source,
    localisation: rawItem.localisation || rawItem.location || rawItem.region || '',
    salaire: rawItem.salaire || rawItem.salary || rawItem.compensation || '',
  };
}

module.exports = { normalize };
