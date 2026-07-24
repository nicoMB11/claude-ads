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
export function statusBadge(s) {
  const map = {
    confirmed: ['green', 'Confirmee'], pending: ['amber', 'A valider'],
    seated: ['green', 'Installee'], cancelled: ['grey', 'Annulee'], no_show: ['red', 'No-show'],
  };
  const [cls, label] = map[s] || ['grey', s];
  return `<span class="badge ${cls}">${label}</span>`;
}
