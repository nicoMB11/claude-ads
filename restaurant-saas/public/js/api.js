// Petit client HTTP + utilitaires partages (client & admin).
export const SLUG = new URLSearchParams(location.search).get('r') || 'petit-comptoir';

async function req(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.message || 'Erreur'), { data, status: res.status });
  return data;
}
export const api = {
  get: (p) => req('GET', p),
  post: (p, b) => req('POST', p, b),
  patch: (p, b) => req('PATCH', p, b),
  del: (p) => req('DELETE', p),
};

export function toast(msg, isErr = false) {
  let el = document.querySelector('.toast');
  if (!el) { el = document.createElement('div'); el.className = 'toast'; document.body.appendChild(el); }
  el.textContent = msg;
  el.className = 'toast show' + (isErr ? ' err' : '');
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.className = 'toast'), 2600);
}

export const WD = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];
export const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export const todayISO = () => new Date().toISOString().slice(0, 10);
export function fmtDate(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
}
// --- Charte graphique -------------------------------------------------------
export function shade(hex, pct) {
  // pct<0 assombrit, pct>0 eclaircit
  const h = hex.replace('#', '');
  if (h.length !== 6) return hex;
  const n = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  const adj = n.map((v) => Math.max(0, Math.min(255, Math.round(v + (pct < 0 ? v : 255 - v) * pct))));
  return '#' + adj.map((v) => v.toString(16).padStart(2, '0')).join('');
}
export function applyBranding(branding) {
  if (!branding) return;
  const root = document.documentElement.style;
  if (branding.primary) {
    root.setProperty('--brand', branding.primary);
    root.setProperty('--brand-dark', shade(branding.primary, -0.25));
  }
  if (branding.accent) root.setProperty('--gold', branding.accent);
}

export function statusBadge(s) {
  const map = {
    confirmed: ['green', 'Confirmee'], pending: ['amber', 'A valider'],
    seated: ['green', 'Installee'], cancelled: ['grey', 'Annulee'], no_show: ['red', 'No-show'],
  };
  const [cls, label] = map[s] || ['grey', s];
  return `<span class="badge ${cls}">${label}</span>`;
}
