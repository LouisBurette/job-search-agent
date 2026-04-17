# Code des nœuds n8n — Job Agent

Copier-coller le code de chaque nœud directement dans n8n.

---

## Normalize Remotive

```js
const config = $('Config').first().json;
const maxAge = config.max_age_days;
const cutoff = new Date(Date.now() - maxAge * 24 * 60 * 60 * 1000);

return $input.all()
  .filter(item => new Date(item.json.pubDate) >= cutoff)
  .map(item => ({
    json: {
      titre: item.json.title || '',
      entreprise: item.json.creator || '',
      url: item.json.link || '',
      description: item.json.content || item.json.contentSnippet || '',
      date: item.json.pubDate || '',
      source: 'Remotive',
      localisation: 'Remote',
      salaire: '',
    }
  }));
```

---

## Normalize WWDR

```js
const config = $('Config').first().json;
const maxAge = config.max_age_days;
const cutoff = new Date(Date.now() - maxAge * 24 * 60 * 60 * 1000);

return $input.all()
  .filter(item => new Date(item.json.pubDate) >= cutoff)
  .map(item => {
    const titleParts = (item.json.title || '').split(' at ');
    return {
      json: {
        titre: titleParts[0]?.trim() || item.json.title || '',
        entreprise: titleParts[1]?.trim() || '',
        url: item.json.link || '',
        description: item.json.content || item.json.contentSnippet || '',
        date: item.json.pubDate || '',
        source: 'We Work Remotely',
        localisation: 'Remote',
        salaire: '',
      }
    };
  });
```

---

## Normalize JTMS

```js
const config = $('Config').first().json;
const maxAge = config.max_age_days;
const cutoff = new Date(Date.now() - maxAge * 24 * 60 * 60 * 1000);

const jobs = $input.first().json.jobs || $input.all().map(i => i.json);

return jobs
  .filter(job => new Date(job.published_at || job.pubDate) >= cutoff)
  .map(job => ({
    json: {
      titre: job.title || job.titre || '',
      entreprise: job.company || job.entreprise || '',
      url: job.url || job.link || '',
      description: job.description || job.content || '',
      date: job.published_at || job.pubDate || '',
      source: 'Jobs That Make Sense',
      localisation: job.location || 'Remote',
      salaire: job.salary || '',
    }
  }));
```

---

## Normalize Indeed

```js
const config = $('Config').first().json;
const maxAge = config.max_age_days;
const cutoff = new Date(Date.now() - maxAge * 24 * 60 * 60 * 1000);

const items1 = $input.all();

return items1
  .filter(item => new Date(item.json.pubDate) >= cutoff)
  .map(item => ({
    json: {
      titre: item.json.title || '',
      entreprise: item.json.source || '',
      url: item.json.link || '',
      description: item.json.contentSnippet || item.json.content || '',
      date: item.json.pubDate || '',
      source: 'Indeed.es',
      localisation: 'Donostia / Remote',
      salaire: '',
    }
  }));
```

---

## Normalize WTTJ

```js
const config = $('Config').first().json;
const maxAge = config.max_age_days;
const cutoff = new Date(Date.now() - maxAge * 24 * 60 * 60 * 1000);

return $input.all()
  .filter(item => new Date(item.json.pubDate) >= cutoff)
  .map(item => ({
    json: {
      titre: item.json.title || '',
      entreprise: item.json.creator || '',
      url: item.json.link || '',
      description: item.json.contentSnippet || item.json.content || '',
      date: item.json.pubDate || '',
      source: 'Welcome to the Jungle',
      localisation: item.json.category || 'Espagne',
      salaire: '',
    }
  }));
```

---

## Normalize InfoJobs

```js
const config = $('Config').first().json;
const maxAge = config.max_age_days;
const cutoff = new Date(Date.now() - maxAge * 24 * 60 * 60 * 1000);

const offers = $input.first().json.items || [];

return offers
  .filter(offer => new Date(offer.updated) >= cutoff)
  .map(offer => ({
    json: {
      titre: offer.title || '',
      entreprise: offer.author?.name || '',
      url: offer.link || '',
      description: offer.requirementMin || offer.description || '',
      date: offer.updated || '',
      source: 'InfoJobs',
      localisation: offer.city?.value || offer.province?.value || '',
      salaire: offer.salaryDescription || '',
    }
  }));
```

---

## Normalize Tecnoempleo

```js
const config = $('Config').first().json;
const maxAge = config.max_age_days;
const cutoff = new Date(Date.now() - maxAge * 24 * 60 * 60 * 1000);

return $input.all()
  .filter(item => new Date(item.json.pubDate) >= cutoff)
  .map(item => ({
    json: {
      titre: item.json.title || '',
      entreprise: item.json.creator || '',
      url: item.json.link || '',
      description: item.json.contentSnippet || '',
      date: item.json.pubDate || '',
      source: 'Tecnoempleo',
      localisation: item.json.category || 'Espagne',
      salaire: '',
    }
  }));
```

---

## Normalize Computrabajo

```js
const config = $('Config').first().json;
const maxAge = config.max_age_days;
const cutoff = new Date(Date.now() - maxAge * 24 * 60 * 60 * 1000);

return $input.all()
  .filter(item => new Date(item.json.pubDate) >= cutoff)
  .map(item => ({
    json: {
      titre: item.json.title || '',
      entreprise: item.json.creator || item.json.source || '',
      url: item.json.link || '',
      description: item.json.contentSnippet || '',
      date: item.json.pubDate || '',
      source: 'Computrabajo',
      localisation: item.json.category || 'Espagne',
      salaire: '',
    }
  }));
```

---

## Normalize LinkedIn

```js
const config = $('Config').first().json;
const maxAge = config.max_age_days;
const cutoff = new Date(Date.now() - maxAge * 24 * 60 * 60 * 1000);

return $input.all()
  .filter(item => {
    try { return new Date(item.json.pubDate) >= cutoff; }
    catch { return true; }
  })
  .map(item => ({
    json: {
      titre: item.json.title || '',
      entreprise: item.json.creator || '',
      url: item.json.link || '',
      description: item.json.contentSnippet || '',
      date: item.json.pubDate || '',
      source: 'LinkedIn',
      localisation: 'Donostia / Remote',
      salaire: '',
    }
  }));
```

---

## Dedup Same Week

```js
const seen = new Set();
return $input.all().filter(item => {
  const url = item.json.url;
  if (!url || seen.has(url)) return false;
  seen.add(url);
  return true;
});
```

---

## Dedup Historical

```js
const staticData = $getWorkflowStaticData('global');
if (!staticData.sentUrls) staticData.sentUrls = [];

const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
staticData.sentUrls = staticData.sentUrls.filter(entry => entry.ts > thirtyDaysAgo);

const sentSet = new Set(staticData.sentUrls.map(e => e.url));

const newOffers = $input.all().filter(item => !sentSet.has(item.json.url));

return newOffers;
```

---

## Rule Filter

```js
const config = $('Config').first().json;

function matchesGeo(localisation, geo) {
  if (!localisation) return true;
  const loc = localisation.toLowerCase();
  return geo.some(g => loc.includes(g.toLowerCase()));
}

function matchesPoste(titre, description, postes) {
  const text = `${titre} ${description}`.toLowerCase();
  return postes.some(p => text.includes(p.toLowerCase()));
}

function matchesTeletravail(description, localisation) {
  const text = `${description} ${localisation}`.toLowerCase();
  return (
    text.includes('remote') ||
    text.includes('télétravail') ||
    text.includes('teletrabajo') ||
    text.includes('full remote') ||
    text.includes('100%')
  );
}

function avoidsSecteur(description, titre, secteurs_nok) {
  const text = `${titre} ${description}`.toLowerCase();
  return !secteurs_nok.some(s => text.includes(s.toLowerCase()));
}

function isRecent(dateStr, max_age_days) {
  try {
    const date = new Date(dateStr);
    const cutoff = new Date(Date.now() - max_age_days * 24 * 60 * 60 * 1000);
    return date >= cutoff;
  } catch { return true; }
}

return $input.all().filter(item => {
  const { titre, description, localisation, date } = item.json;

  const geoOk = matchesGeo(localisation, config.geo) || matchesTeletravail(description, localisation);
  if (!geoOk) return false;

  if (!matchesPoste(titre, description, config.postes)) return false;

  if (!avoidsSecteur(description, titre, config.secteurs_nok)) return false;

  if (!isRecent(date, config.max_age_days)) return false;

  return true;
});
```

---

## Build Prompt

```js
const config = $('Config').first().json;
const offer = $input.first().json;

const prompt = `Tu es un assistant de recherche d'emploi. Évalue la pertinence de cette offre pour ce profil.

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
Description : ${(offer.description || '').substring(0, 1500)}

Réponds UNIQUEMENT en JSON valide, sans markdown, sans commentaire :
{ "score": <entier 1-10>, "raison": "<2 phrases max en français>" }`;

return [{ json: { ...offer, prompt } }];
```

---

## Parse Score

```js
const offer = $input.first().json;
const rawResponse = $input.first().json.content?.[0]?.text || '{}';

let score = null;
let raison = '';

try {
  const parsed = JSON.parse(rawResponse);
  score = parsed.score || null;
  raison = parsed.raison || '';
} catch (e) {
  score = null;
  raison = 'Score non disponible';
}

return [{ json: { ...offer, score, raison } }];
```

---

## Sort & Top N

```js
const config = $('Config').first().json;
const offers = $input.all().map(i => i.json);

offers.sort((a, b) => {
  if (a.score === null) return 1;
  if (b.score === null) return -1;
  return b.score - a.score;
});

return offers.slice(0, config.top_n).map(o => ({ json: o }));
```

---

## Build Email HTML

```js
const offers = $input.all().map(i => i.json);
const failedSources = [];

function scoreColor(score) {
  if (score >= 8) return '#22c55e';
  if (score >= 5) return '#f59e0b';
  return '#ef4444';
}

function buildCard(offer) {
  const score = offer.score !== null ? offer.score : '?';
  const color = offer.score !== null ? scoreColor(offer.score) : '#94a3b8';
  return `<div style="border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:16px;font-family:sans-serif;"><div style="display:flex;justify-content:space-between;align-items:flex-start;"><div><h3 style="margin:0 0 4px;font-size:16px;color:#1e293b;">${offer.titre}</h3><p style="margin:0;color:#64748b;font-size:14px;">${offer.entreprise} · ${offer.source} · ${offer.localisation}</p>${offer.salaire ? `<p style="margin:4px 0 0;color:#64748b;font-size:13px;">💰 ${offer.salaire}</p>` : ''}</div><div style="background:${color};color:white;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;flex-shrink:0;text-align:center;line-height:36px;">${score}</div></div><p style="margin:10px 0 8px;font-size:13px;color:#475569;font-style:italic;">${offer.raison}</p><a href="${offer.url}" style="display:inline-block;background:#3b82f6;color:white;padding:6px 14px;border-radius:4px;font-size:13px;text-decoration:none;">Voir l'offre →</a></div>`;
}

const cards = offers.map(buildCard).join('');
const warning = failedSources.length > 0
  ? `<p style="color:#ef4444;font-size:13px;margin-top:24px;">⚠️ Sources indisponibles cette semaine : ${failedSources.join(', ')}</p>`
  : '';

const dateStr = new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
const html = `<html><body style="background:#f8fafc;padding:24px;"><div style="max-width:600px;margin:0 auto;"><h1 style="font-size:20px;color:#1e293b;margin-bottom:4px;">🎯 Job Digest — ${dateStr}</h1><p style="color:#64748b;font-size:14px;margin-bottom:24px;">${offers.length} offre${offers.length > 1 ? 's' : ''} sélectionnée${offers.length > 1 ? 's' : ''}</p>${cards}${warning}</div></body></html>`;

return [{ json: { html, offerCount: offers.length, offers } }];
```

---

## Mark As Sent

```js
const staticData = $getWorkflowStaticData('global');
if (!staticData.sentUrls) staticData.sentUrls = [];

const now = Date.now();
const offers = $('Build Email HTML').first().json.offers || [];

offers.forEach(offer => {
  if (offer.url) {
    staticData.sentUrls.push({ url: offer.url, ts: now });
  }
});

return [{ json: { markedCount: offers.length } }];
```

