// Composant "tunnel de reservation" reutilisable.
// Utilise par la web app (index.html) et par le widget embarquable (book.html).
import { api, toast, esc, fmtDate, todayISO } from './api.js';

export async function mountBooking(el, slug, opts = {}) {
  let R;
  try { R = await api.get(`/api/r/${slug}`); }
  catch { el.innerHTML = `<div class="card">Restaurant introuvable.</div>`; return; }

  const state = { step: 1, party: 2, date: todayISO(), time: null, service: null };
  const maxDate = (() => { const d = new Date(); d.setDate(d.getDate() + R.horizonDays); return d.toISOString().slice(0, 10); })();

  function render() {
    el.innerHTML = `
      <div class="stepper">${[1, 2, 3].map((i) => `<div class="st ${state.step >= i ? 'on' : ''}"></div>`).join('')}</div>
      <div id="bk-body"></div>`;
    ({ 1: stepWhen, 2: stepSlot, 3: stepDone }[state.step] || stepWhen)();
  }

  // --- Etape 1 : couverts + date + creneaux -------------------------------
  function stepWhen() {
    const body = el.querySelector('#bk-body');
    const parties = Array.from({ length: R.maxPartyOnline }, (_, i) => i + 1);
    body.innerHTML = `
      <div class="fields-2">
        <div class="field">
          <label>Nombre de personnes</label>
          <select id="party">${parties.map((n) => `<option value="${n}" ${n === state.party ? 'selected' : ''}>${n} personne${n > 1 ? 's' : ''}</option>`).join('')}</select>
        </div>
        <div class="field">
          <label>Date</label>
          <input type="date" id="date" value="${state.date}" min="${todayISO()}" max="${maxDate}">
        </div>
      </div>
      <div id="avail" class="muted small">Recherche des disponibilites...</div>
      <p class="small muted" style="margin-top:14px">Groupe de plus de ${R.maxPartyOnline} personnes ?
        ${R.options.group_request ? `<a href="#" id="grp-link">Faire une demande de groupe</a>` : 'Merci d\'appeler le restaurant.'}</p>`;

    const load = () => loadAvailability(body.querySelector('#avail'));
    body.querySelector('#party').onchange = (e) => { state.party = +e.target.value; state.time = null; load(); };
    body.querySelector('#date').onchange = (e) => { state.date = e.target.value; state.time = null; load(); };
    const gl = body.querySelector('#grp-link');
    if (gl) gl.onclick = (e) => { e.preventDefault(); (opts.onGroupRequest || (() => toast('Demande de groupe disponible sur la page du restaurant')))(); };
    load();
  }

  async function loadAvailability(box) {
    box.innerHTML = `<span class="muted small">Recherche...</span>`;
    let data;
    try { data = await api.get(`/api/r/${slug}/availability?date=${state.date}&party=${state.party}`); }
    catch { box.innerHTML = `<span class="badge red">Erreur de chargement</span>`; return; }
    if (data.closed) { box.innerHTML = `<div class="badge grey">Restaurant ferme le ${fmtDate(state.date)}</div>`; return; }
    const services = data.services || [];
    if (!services.length) { box.innerHTML = `<div class="badge grey">Aucun service ce jour-la</div>`; return; }
    box.innerHTML = services.map((svc) => `
      <div class="svc-title">${esc(svc.service)}</div>
      <div class="slots">${svc.slots.map((s) =>
        `<div class="slot ${s.available ? '' : 'off'} ${state.time === s.time ? 'sel' : ''}"
           data-t="${s.time}" data-svc="${esc(svc.service)}" ${s.available ? '' : 'aria-disabled=true'}>${s.time}</div>`).join('')}</div>`).join('');
    box.querySelectorAll('.slot:not(.off)').forEach((n) => n.onclick = () => {
      state.time = n.dataset.t; state.service = n.dataset.svc; state.step = 2; render();
    });
    if (!services.some((s) => s.slots.some((x) => x.available))) {
      box.innerHTML += `<p class="small muted" style="margin-top:10px">Complet ce jour-la. Essayez une autre date.</p>`;
    }
  }

  // --- Etape 2 : coordonnees ----------------------------------------------
  function stepSlot() {
    const body = el.querySelector('#bk-body');
    body.innerHTML = `
      <div class="card" style="background:#faf8f4;margin-bottom:16px">
        <strong>${state.party} pers.</strong> &middot; ${fmtDate(state.date)} &middot; <strong>${state.time}</strong>
        <span class="muted small"> (${esc(state.service || '')})</span>
        <a href="#" id="back" class="small" style="float:right">Modifier</a>
      </div>
      <div class="field"><label>Nom complet *</label><input id="name" placeholder="Prenom Nom"></div>
      <div class="fields-2">
        <div class="field"><label>Telephone *</label><input id="phone" placeholder="06 12 34 56 78"></div>
        <div class="field"><label>Email</label><input id="email" type="email" placeholder="vous@email.fr"></div>
      </div>
      <div class="field"><label>Message / demande particuliere</label><textarea id="msg" rows="2" placeholder="Allergies, occasion, table en terrasse..."></textarea></div>
      <button class="btn" id="confirm" style="width:100%">Confirmer la reservation</button>`;
    body.querySelector('#back').onclick = (e) => { e.preventDefault(); state.step = 1; render(); };
    body.querySelector('#confirm').onclick = submit;
  }

  async function submit(ev) {
    const b = ev.target;
    const name = el.querySelector('#name').value.trim();
    const phone = el.querySelector('#phone').value.trim();
    if (!name || !phone) return toast('Nom et telephone requis', true);
    b.disabled = true; b.textContent = 'Envoi...';
    try {
      state.result = await api.post(`/api/r/${slug}/reservations`, {
        customer_name: name, phone, email: el.querySelector('#email').value.trim(),
        message: el.querySelector('#msg').value.trim(),
        date: state.date, time: state.time, party_size: state.party, source: opts.source || 'web',
      });
      state.step = 3; render();
    } catch (e) {
      b.disabled = false; b.textContent = 'Confirmer la reservation';
      toast(e.message || 'Creneau indisponible', true);
      if (e.data?.error === 'no_table' || e.data?.error === 'slot_full') { state.step = 1; render(); }
    }
  }

  // --- Etape 3 : confirmation ---------------------------------------------
  function stepDone() {
    const r = state.result || {};
    const pending = r.status === 'pending';
    el.querySelector('#bk-body').innerHTML = `
      <div class="center" style="padding:10px 0 4px">
        <div style="font-size:2.6rem">${pending ? '⏳' : '✔️'}</div>
        <h2>${pending ? 'Demande enregistree' : 'Reservation confirmee'}</h2>
        <p class="muted">${pending
          ? 'Votre groupe depasse le seuil : le restaurant validera votre demande sous peu.'
          : 'Un email de confirmation vient de vous etre envoye (simule en demo).'}</p>
        <div class="card" style="display:inline-block;text-align:left;margin-top:8px">
          <div class="small muted">Reference</div><div style="font-size:1.4rem;font-weight:800">${esc(r.ref || '')}</div>
          <div class="small" style="margin-top:6px">${state.party} pers. &middot; ${fmtDate(state.date)} &middot; ${state.time}</div>
        </div>
        <div style="margin-top:18px"><button class="btn subtle" id="again">Nouvelle reservation</button></div>
      </div>`;
    el.querySelector('#again').onclick = () => { state.step = 1; state.time = null; state.result = null; render(); };
  }

  render();
  return { reload: render };
}
