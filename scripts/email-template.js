// scripts/email-template.js
// Template du digest email — le code est copié dans les Function nodes n8n

function scoreColor(score) {
  if (score >= 8) return '#22c55e';  // vert
  if (score >= 5) return '#f59e0b';  // orange
  return '#ef4444';                   // rouge
}

function buildCard(offer) {
  const score = offer.score !== null ? offer.score : '?';
  const color = offer.score !== null ? scoreColor(offer.score) : '#94a3b8';

  return `
  <div style="border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:16px;font-family:sans-serif;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <h3 style="margin:0 0 4px;font-size:16px;color:#1e293b;">${offer.titre}</h3>
        <p style="margin:0;color:#64748b;font-size:14px;">${offer.entreprise} · ${offer.source} · ${offer.localisation}</p>
        ${offer.salaire ? `<p style="margin:4px 0 0;color:#64748b;font-size:13px;">💰 ${offer.salaire}</p>` : ''}
      </div>
      <div style="background:${color};color:white;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;flex-shrink:0;text-align:center;line-height:36px;">
        ${score}
      </div>
    </div>
    <p style="margin:10px 0 8px;font-size:13px;color:#475569;font-style:italic;">${offer.raison}</p>
    <a href="${offer.url}" style="display:inline-block;background:#3b82f6;color:white;padding:6px 14px;border-radius:4px;font-size:13px;text-decoration:none;">Voir l'offre →</a>
  </div>`;
}

function buildEmail(offers, failedSources) {
  const cards = offers.map(buildCard).join('');
  const warning = failedSources.length > 0
    ? `<p style="color:#ef4444;font-size:13px;margin-top:24px;">⚠️ Sources indisponibles cette semaine : ${failedSources.join(', ')}</p>`
    : '';

  return `
  <html>
  <body style="background:#f8fafc;padding:24px;">
    <div style="max-width:600px;margin:0 auto;">
      <h1 style="font-size:20px;color:#1e293b;margin-bottom:4px;">🎯 Job Digest — ${new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}</h1>
      <p style="color:#64748b;font-size:14px;margin-bottom:24px;">${offers.length} offre${offers.length > 1 ? 's' : ''} sélectionnée${offers.length > 1 ? 's' : ''}, classée${offers.length > 1 ? 's' : ''} par pertinence</p>
      ${cards}
      ${warning}
    </div>
  </body>
  </html>`;
}

module.exports = { buildEmail, buildCard, scoreColor };
