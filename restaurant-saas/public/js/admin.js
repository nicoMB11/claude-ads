// Tableau de bord restaurant. Chaque onglet se charge a la demande.
import { api, SLUG, toast, esc, WD, fmtDate, todayISO, statusBadge } from './api.js';

const $ = (s, r = document) => r.querySelector(s);
const A = `/api/admin/${SLUG}`;
let R = null; // overview cache

// --- Navigation onglets ------------------------------------------------------
const renderers = {
  dash: renderDash, floor: renderFloor, resa: renderResa,
  config: renderConfig, options: renderOptions, groups: renderGroups, outbox: renderOutbox,
};
document.querySelectorAll('.tab').forEach((t) => t.onclick = () => activate(t.dataset.tab));
function activate(name) {
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tabpane').forEach((p) => p.classList.add('hidden'));
  const pane = $(`#tab-${name}`);
  pane.classList.remove('hidden');
  renderers[name](pane);
}

(async function init() {
  try {
    R = await api.get(`${A}/overview`);
    $('#rname').innerHTML = `${esc(R.restaurant.name)}<span class="dot">.</span>`;
  } catch { $('#rname').textContent = 'Restaurant introuvable'; }
  activate('dash');
})();

// ============================ TABLEAU DE BORD ================================
async function renderDash(pane) {
  pane.innerHTML = `<p class="muted">Chargement...</p>`;
  const date = todayISO();
  const ov = await api.get(`${A}/overview?date=${date}`);
  R = ov;
  const { capacity, today, groupRequests } = ov;
  pane.innerHTML = `
    <div class="tiles" style="margin-bottom:22px">
      <div class="tile"><div class="n">${today.reservations}</div><div class="l">Reservations aujourd'hui</div></div>
      <div class="tile"><div class="n">${today.covers}</div><div class="l">Couverts attendus</div></div>
      <div class="tile"><div class="n">${capacity.seats}</div><div class="l">Capacite (couverts)</div></div>
      <div class="tile"><div class="n">${capacity.tables}</div><div class="l">Tables</div></div>
      <div class="tile"><div class="n">${today.pending}</div><div class="l">A valider</div></div>
      <div class="tile"><div class="n">${groupRequests}</div><div class="l">Demandes de groupe</div></div>
    </div>
    <div class="grid" style="grid-template-columns:1.4fr 1fr;align-items:start">
      <div class="card">
        <div class="spread"><h2>Reservations du jour</h2><span class="muted small">${fmtDate(date)}</span></div>
        <div id="dash-list"><p class="muted">...</p></div>
      </div>
      <div class="card">
        <h2>Reservation telephone</h2>
        <p class="muted small">Prise de reservation rapide (avec anti-surbooking).</p>
        <div id="quick"></div>
      </div>
    </div>`;
  loadDayList($('#dash-list'), date);
  quickBooking($('#quick'), date);
}

async function loadDayList(box, date) {
  const { reservations } = await api.get(`${A}/reservations?date=${date}`);
  if (!reservations.length) { box.innerHTML = `<p class="muted small">Aucune reservation.</p>`; return; }
  box.innerHTML = `<table class="data"><thead><tr><th>Heure</th><th>Client</th><th>Pers.</th><th>Table</th><th>Statut</th></tr></thead>
    <tbody>${reservations.map((r) => `<tr>
      <td><strong>${r.time}</strong></td><td>${esc(r.customer_name)}<div class="small muted">${esc(r.phone || '')}</div></td>
      <td>${r.party_size}</td><td>${esc((r.table_names || []).join('+'))}</td><td>${statusBadge(r.status)}</td>
    </tr>`).join('')}</tbody></table>`;
}

function quickBooking(box, date) {
  box.innerHTML = `
    <div class="field"><label>Nom</label><input id="q-name" placeholder="Client"></div>
    <div class="fields-2">
      <div class="field"><label>Date</label><input id="q-date" type="date" value="${date}"></div>
      <div class="field"><label>Personnes</label><input id="q-party" type="number" min="1" value="2"></div>
    </div>
    <div class="field"><label>Creneaux</label><div id="q-slots" class="slots"><span class="muted small">Choisir date + personnes</span></div></div>
    <div class="field"><label>Telephone</label><input id="q-phone"></div>
    <button class="btn" id="q-book" disabled style="width:100%">Reserver</button>`;
  let picked = null;
  const refresh = async () => {
    picked = null; $('#q-book').disabled = true;
    const d = $('#q-date').value, p = $('#q-party').value;
    const data = await api.get(`/api/r/${SLUG}/availability?date=${d}&party=${p}`).catch(() => null);
    const sb = $('#q-slots');
    if (!data || data.closed) { sb.innerHTML = `<span class="badge grey">Ferme</span>`; return; }
    const slots = data.services.flatMap((s) => s.slots).filter((x) => x.available);
    if (!slots.length) { sb.innerHTML = `<span class="badge grey">Complet</span>`; return; }
    sb.innerHTML = slots.map((s) => `<div class="slot" data-t="${s.time}">${s.time}</div>`).join('');
    sb.querySelectorAll('.slot').forEach((n) => n.onclick = () => {
      sb.querySelectorAll('.slot').forEach((x) => x.classList.remove('sel'));
      n.classList.add('sel'); picked = n.dataset.t; $('#q-book').disabled = false;
    });
  };
  $('#q-date').onchange = refresh; $('#q-party').onchange = refresh;
  $('#q-book').onclick = async (ev) => {
    if (!picked) return;
    ev.target.disabled = true;
    try {
      const res = await api.post(`${A}/reservations`, {
        customer_name: $('#q-name').value.trim() || 'Client', phone: $('#q-phone').value.trim(),
        date: $('#q-date').value, time: picked, party_size: $('#q-party').value,
      });
      toast(`Reservation ${res.ref} enregistree`);
      renderDash($('#tab-dash'));
    } catch (e) { ev.target.disabled = false; toast(e.message, true); }
  };
  refresh();
}

// ============================ PLAN DE SALLE ==================================
async function renderFloor(pane) {
  const date = todayISO();
  pane.innerHTML = `
    <div class="card">
      <div class="row" style="margin-bottom:16px">
        <div><label>Date</label><input type="date" id="f-date" value="${date}"></div>
        <div><label>Heure</label><input type="time" id="f-time" value="20:00" step="900"></div>
        <div style="align-self:end"><span id="f-summary" class="muted small"></span></div>
      </div>
      <div id="f-plan"><p class="muted">...</p></div>
    </div>`;
  const load = async () => {
    const d = $('#f-date').value, t = $('#f-time').value;
    const data = await api.get(`${A}/floorplan?date=${d}&time=${t}`);
    $('#f-summary').innerHTML = data.open
      ? `${esc(data.service)} &middot; <strong>${data.seatsOccupied}/${data.seatsTotal}</strong> couverts occupes`
      : `<span class="badge grey">Ferme a cette heure</span>`;
    const zones = [...new Set(data.tables.map((t) => t.zone))];
    $('#f-plan').innerHTML = zones.map((z) => `
      <div class="svc-title">${esc(z)}</div>
      <div class="floor">${data.tables.filter((t) => t.zone === z).map((t) => `
        <div class="tbl ${!t.active ? '' : t.occupiedBy ? 'busy' : 'free'}">
          <div class="name">${esc(t.name)}</div>
          <div class="seats">${t.min}-${t.max} pers.</div>
          ${t.occupiedBy ? `<div class="who">${esc(t.occupiedBy.name)}<br>${t.occupiedBy.party}p &middot; ${t.occupiedBy.time}</div>`
            : `<div class="who" style="color:var(--green)">Libre</div>`}
        </div>`).join('')}</div>`).join('');
  };
  $('#f-date').onchange = load; $('#f-time').onchange = load;
  load();
}

// ============================ RESERVATIONS ==================================
async function renderResa(pane) {
  const date = todayISO();
  pane.innerHTML = `
    <div class="card">
      <div class="spread" style="margin-bottom:14px">
        <div class="row">
          <div><label>Date</label><input type="date" id="r-date" value="${date}"></div>
        </div>
        <div class="muted small" id="r-count"></div>
      </div>
      <div id="r-list"></div>
    </div>`;
  const load = async () => {
    const d = $('#r-date').value;
    const { reservations } = await api.get(`${A}/reservations?date=${d}`);
    $('#r-count').textContent = `${reservations.length} reservation(s)`;
    const box = $('#r-list');
    if (!reservations.length) { box.innerHTML = `<p class="muted small">Aucune reservation ce jour.</p>`; return; }
    box.innerHTML = `<table class="data"><thead><tr><th>Heure</th><th>Ref</th><th>Client</th><th>Pers.</th><th>Table</th><th>Source</th><th>Statut</th><th>Actions</th></tr></thead>
      <tbody>${reservations.map((r) => `<tr>
        <td><strong>${r.time}</strong></td><td class="small">${esc(r.ref)}</td>
        <td>${esc(r.customer_name)}<div class="small muted">${esc(r.phone || '')} ${esc(r.email || '')}</div>${r.message ? `<div class="small">💬 ${esc(r.message)}</div>` : ''}</td>
        <td>${r.party_size}</td><td>${esc((r.table_names || []).join('+'))}</td><td class="small muted">${esc(r.source)}</td>
        <td>${statusBadge(r.status)}</td>
        <td><div class="row" style="gap:4px">
          ${r.status === 'pending' ? `<button class="btn sm" data-act="confirmed" data-id="${r.id}">Valider</button>` : ''}
          ${r.status !== 'seated' && r.status !== 'cancelled' ? `<button class="btn sm subtle" data-act="seated" data-id="${r.id}">Installee</button>` : ''}
          ${r.status !== 'cancelled' ? `<button class="btn sm danger" data-act="cancelled" data-id="${r.id}">Annuler</button>` : ''}
        </div></td>
      </tr>`).join('')}</tbody></table>`;
    box.querySelectorAll('button[data-act]').forEach((b) => b.onclick = async () => {
      await api.patch(`${A}/reservations/${b.dataset.id}`, { status: b.dataset.act });
      toast('Statut mis a jour'); load();
    });
  };
  $('#r-date').onchange = load;
  load();
}

// ============================ CONFIGURATION =================================
async function renderConfig(pane) {
  pane.innerHTML = `<p class="muted">Chargement...</p>`;
  const [{ tables }, { services }, { closures }, cfg] = await Promise.all([
    api.get(`${A}/tables`), api.get(`${A}/services`), api.get(`${A}/closures`), api.get(`${A}/settings`),
  ]);
  const g = cfg.general;
  pane.innerHTML = `
    <div class="grid" style="grid-template-columns:1fr 1fr;align-items:start">
      <!-- Parametres generaux + anti-surbooking -->
      <div class="card">
        <h2>Parametres du restaurant</h2>
        <div class="fields-2">
          <div class="field"><label>Nom</label><input id="g-name" value="${esc(g.name)}"></div>
          <div class="field"><label>Telephone</label><input id="g-phone" value="${esc(g.phone)}"></div>
        </div>
        <div class="field"><label>Adresse</label><input id="g-address" value="${esc(g.address)}"></div>
        <div class="fields-2">
          <div class="field"><label>Duree repas (min)</label><input id="g-turn" type="number" value="${g.turn_time_min}"></div>
          <div class="field"><label>Buffer entre services (min)</label><input id="g-buffer" type="number" value="${g.buffer_min}"></div>
        </div>
        <div class="fields-2">
          <div class="field"><label>Pas des creneaux (min)</label><input id="g-slot" type="number" value="${g.slot_interval_min}"></div>
          <div class="field"><label>Max pers. en ligne</label><input id="g-max" type="number" value="${g.max_party_online}"></div>
        </div>
        <div class="field"><label>Horizon de reservation (jours)</label><input id="g-horizon" type="number" value="${g.horizon_days}"></div>
        <button class="btn" id="g-save">Enregistrer</button>
      </div>

      <!-- Plan de salle : tables / chaises -->
      <div class="card">
        <div class="spread"><h2>Tables & couverts</h2><span class="badge grey" id="cap-badge"></span></div>
        <p class="muted small">La capacite physique = limite anti-surbooking.</p>
        <div id="tbl-list" style="max-height:280px;overflow:auto"></div>
        <hr style="border:none;border-top:1px solid var(--line);margin:14px 0">
        <details><summary style="cursor:pointer;font-weight:600">Ajouter une table</summary>
          <div class="fields-2" style="margin-top:10px">
            <div class="field"><label>Nom</label><input id="nt-name" placeholder="T13"></div>
            <div class="field"><label>Zone</label><input id="nt-zone" value="Salle"></div>
          </div>
          <div class="fields-2">
            <div class="field"><label>Sieges min</label><input id="nt-min" type="number" value="1"></div>
            <div class="field"><label>Sieges max</label><input id="nt-max" type="number" value="2"></div>
          </div>
          <button class="btn sm" id="nt-add">Ajouter</button>
        </details>
        <details style="margin-top:10px"><summary style="cursor:pointer;font-weight:600">Config express (generer le plan)</summary>
          <p class="small muted">Indiquez combien de tables de chaque taille. Remplace le plan actuel.</p>
          <div id="bulk-rows"></div>
          <button class="btn sm subtle" id="bulk-add-row">+ ligne</button>
          <button class="btn sm" id="bulk-gen">Generer</button>
        </details>
      </div>

      <!-- Services -->
      <div class="card">
        <h2>Services & horaires</h2>
        <div id="svc-list"></div>
        <hr style="border:none;border-top:1px solid var(--line);margin:14px 0">
        <details><summary style="cursor:pointer;font-weight:600">Ajouter un service</summary>
          <div class="fields-2" style="margin-top:10px">
            <div class="field"><label>Nom</label><input id="ns-name" value="Diner"></div>
            <div class="field"><label>Jour</label><select id="ns-wd">${WD.map((d, i) => `<option value="${i}">${d}</option>`).join('')}</select></div>
          </div>
          <div class="fields-2">
            <div class="field"><label>Premier creneau</label><input id="ns-start" type="time" value="19:00" step="900"></div>
            <div class="field"><label>Dernier creneau</label><input id="ns-last" type="time" value="21:30" step="900"></div>
          </div>
          <div class="fields-2">
            <div class="field"><label>Couverts max / creneau</label><input id="ns-slotcap" type="number" placeholder="illimite"></div>
            <div class="field"><label>Couverts max / service</label><input id="ns-svccap" type="number" placeholder="illimite"></div>
          </div>
          <button class="btn sm" id="ns-add">Ajouter</button>
        </details>
      </div>

      <!-- Fermetures -->
      <div class="card">
        <h2>Fermetures exceptionnelles</h2>
        <div id="clo-list"></div>
        <div class="row" style="margin-top:10px">
          <input type="date" id="nc-date" style="max-width:180px">
          <input id="nc-reason" placeholder="Motif (optionnel)">
          <button class="btn sm" id="nc-add">Ajouter</button>
        </div>
      </div>
    </div>`;

  // Generaux
  $('#g-save').onclick = async () => {
    await api.patch(`${A}/settings`, { general: {
      name: $('#g-name').value, phone: $('#g-phone').value, address: $('#g-address').value,
      turn_time_min: $('#g-turn').value, buffer_min: $('#g-buffer').value, slot_interval_min: $('#g-slot').value,
      max_party_online: $('#g-max').value, horizon_days: $('#g-horizon').value,
    }});
    toast('Parametres enregistres'); $('#rname').innerHTML = `${esc($('#g-name').value)}<span class="dot">.</span>`;
  };

  // Tables
  const paintTables = (list) => {
    const seats = list.filter((t) => t.active).reduce((s, t) => s + t.max_seats, 0);
    $('#cap-badge').textContent = `${list.filter((t) => t.active).length} tables / ${seats} couverts`;
    $('#tbl-list').innerHTML = `<table class="data"><tbody>${list.map((t) => `<tr>
      <td><strong>${esc(t.name)}</strong> <span class="small muted">${esc(t.zone)}</span></td>
      <td class="small">${t.min_seats}-${t.max_seats}p</td>
      <td>${t.active ? '' : '<span class="badge grey">inactive</span>'}</td>
      <td style="text-align:right"><button class="btn sm danger" data-del="${t.id}">✕</button></td></tr>`).join('')}</tbody></table>`;
    $('#tbl-list').querySelectorAll('button[data-del]').forEach((b) => b.onclick = async () => {
      await api.del(`${A}/tables/${b.dataset.del}`); reloadTables();
    });
  };
  const reloadTables = async () => paintTables((await api.get(`${A}/tables`)).tables);
  paintTables(tables);
  $('#nt-add').onclick = async () => {
    await api.post(`${A}/tables`, { name: $('#nt-name').value || 'T', zone: $('#nt-zone').value,
      min_seats: $('#nt-min').value, max_seats: $('#nt-max').value, joinable: 1 });
    toast('Table ajoutee'); reloadTables();
  };
  // Bulk generator
  const bulkRows = $('#bulk-rows');
  const addBulkRow = (count = 4, mn = 2, mx = 4) => {
    const div = document.createElement('div');
    div.className = 'row'; div.style.marginBottom = '6px';
    div.innerHTML = `<input class="bk-count" type="number" value="${count}" style="max-width:70px" title="nombre">
      <span class="small muted">tables de</span><input class="bk-min" type="number" value="${mn}" style="max-width:60px">
      <span class="small muted">a</span><input class="bk-max" type="number" value="${mx}" style="max-width:60px"><span class="small muted">pers.</span>`;
    bulkRows.appendChild(div);
  };
  addBulkRow(6, 1, 2); addBulkRow(6, 2, 4); addBulkRow(2, 4, 6);
  $('#bulk-add-row').onclick = () => addBulkRow();
  $('#bulk-gen').onclick = async () => {
    const groups = [...bulkRows.children].map((r, i) => ({
      count: r.querySelector('.bk-count').value, min_seats: r.querySelector('.bk-min').value,
      max_seats: r.querySelector('.bk-max').value, prefix: String.fromCharCode(65 + i),
    }));
    const res = await api.post(`${A}/tables/bulk`, { groups, replace: true });
    toast(`Plan genere : ${res.created} tables / ${res.capacity.seats} couverts`); reloadTables();
  };

  // Services
  const paintServices = (list) => {
    $('#svc-list').innerHTML = list.length ? `<table class="data"><tbody>${list.map((s) => `<tr>
      <td><strong>${esc(s.name)}</strong><div class="small muted">${WD[s.weekday]}</div></td>
      <td class="small">${s.start_time}–${s.last_seating}</td>
      <td class="small muted">${s.slot_capacity ? s.slot_capacity + '/cr.' : ''} ${s.service_capacity ? s.service_capacity + '/svc' : ''}</td>
      <td style="text-align:right"><button class="btn sm danger" data-del="${s.id}">✕</button></td></tr>`).join('')}</tbody></table>`
      : `<p class="muted small">Aucun service.</p>`;
    $('#svc-list').querySelectorAll('button[data-del]').forEach((b) => b.onclick = async () => {
      await api.del(`${A}/services/${b.dataset.del}`); paintServices((await api.get(`${A}/services`)).services);
    });
  };
  paintServices(services);
  $('#ns-add').onclick = async () => {
    await api.post(`${A}/services`, { name: $('#ns-name').value, weekday: $('#ns-wd').value,
      start_time: $('#ns-start').value, last_seating: $('#ns-last').value,
      slot_capacity: $('#ns-slotcap').value || null, service_capacity: $('#ns-svccap').value || null });
    toast('Service ajoute'); paintServices((await api.get(`${A}/services`)).services);
  };

  // Fermetures
  const paintClosures = (list) => {
    $('#clo-list').innerHTML = list.length ? list.map((c) => `<div class="opt-toggle">
      <span>${fmtDate(c.date)} ${c.reason ? `<span class="muted small">— ${esc(c.reason)}</span>` : ''}</span>
      <button class="btn sm danger" data-del="${c.id}" style="margin-left:auto">✕</button></div>`).join('')
      : `<p class="muted small">Aucune fermeture programmee.</p>`;
    $('#clo-list').querySelectorAll('button[data-del]').forEach((b) => b.onclick = async () => {
      await api.del(`${A}/closures/${b.dataset.del}`); paintClosures((await api.get(`${A}/closures`)).closures);
    });
  };
  paintClosures(closures);
  $('#nc-add').onclick = async () => {
    if (!$('#nc-date').value) return toast('Choisir une date', true);
    await api.post(`${A}/closures`, { date: $('#nc-date').value, reason: $('#nc-reason').value });
    toast('Fermeture ajoutee'); paintClosures((await api.get(`${A}/closures`)).closures);
  };
}

// ============================ OPTIONS =======================================
const OPTIONS = [
  ['floor_plan', 'Plan de salle digital', '10 €/mois'],
  ['events', "Reservation d'evenements", '7,50 €/mois'],
  ['group_request', 'Demande de privatisation / groupe', '3 €/mois'],
  ['group_validation', 'Validation groupe au-dela d\'un seuil', '3 €/mois'],
  ['deposit', 'Empreinte bancaire / acompte', '10 €/mois'],
  ['sms_reminder', 'SMS de rappel avant reservation', '5 €/mois'],
  ['sms_review', "Demande d'avis par SMS", '5 €/mois'],
  ['mailing', 'Campagne mailing marketing', '5 €/mois'],
  ['gift_cards', 'Cheques cadeaux en ligne', '3,5 €/mois'],
];
async function renderOptions(pane) {
  const cfg = await api.get(`${A}/settings`);
  const opts = cfg.settings.options || {};
  const threshold = cfg.settings.group_validation_threshold || 8;
  pane.innerHTML = `
    <div class="grid" style="grid-template-columns:1fr 1fr;align-items:start">
      <div class="card">
        <h2>Options modulaires</h2>
        <p class="muted small">Activez/desactivez les modules. Les surcouts reprennent votre grille tarifaire.</p>
        <div id="opt-list">${OPTIONS.map(([k, label, price]) => `
          <label class="opt-toggle"><input type="checkbox" data-opt="${k}" ${opts[k] ? 'checked' : ''}>
            <span>${label}</span><span class="price">${price}</span></label>`).join('')}</div>
      </div>
      <div class="card">
        <h2>Reglage validation groupe</h2>
        <p class="muted small">Au-dela de ce nombre de personnes, la reservation en ligne passe en "a valider" cote restaurant.</p>
        <div class="field"><label>Seuil (personnes)</label><input id="thr" type="number" min="2" value="${threshold}" style="max-width:120px"></div>
        <button class="btn" id="opt-save">Enregistrer les options</button>
      </div>
    </div>`;
  $('#opt-save').onclick = async () => {
    const newOpts = {};
    pane.querySelectorAll('input[data-opt]').forEach((c) => newOpts[c.dataset.opt] = c.checked);
    await api.patch(`${A}/settings`, { settings: { ...cfg.settings, options: newOpts, group_validation_threshold: Number($('#thr').value) } });
    toast('Options enregistrees');
  };
}

// ============================ DEMANDES (groupes + evenements) ================
async function renderGroups(pane) {
  const [{ requests }, { events }] = await Promise.all([api.get(`${A}/group-requests`), api.get(`${A}/events`)]);
  pane.innerHTML = `
    <div class="grid" style="grid-template-columns:1.2fr 1fr;align-items:start">
      <div class="card">
        <h2>Demandes de groupe / privatisation</h2>
        <div id="gr-list">${requests.length ? requests.map((g) => `
          <div class="list-item">
            <div class="spread"><strong>${esc(g.customer_name)} — ${g.party_size} pers.</strong>
              <span>${g.status === 'new' ? '<span class="badge amber">Nouvelle</span>' : g.status === 'accepted' ? '<span class="badge green">Acceptee</span>' : '<span class="badge grey">Refusee</span>'}</span></div>
            <div class="small muted">${fmtDate(g.date)} ${g.time ? 'a ' + g.time : ''} &middot; ${esc(g.event_type || 'n/c')} &middot; ${esc(g.budget || '')}</div>
            <div class="small">${esc(g.phone || '')} ${esc(g.email || '')} ${g.message ? '— ' + esc(g.message) : ''}</div>
            ${g.status === 'new' ? `<div class="row" style="margin-top:6px"><button class="btn sm" data-acc="${g.id}">Accepter</button><button class="btn sm danger" data-dec="${g.id}">Refuser</button></div>` : ''}
          </div>`).join('') : '<p class="muted small">Aucune demande.</p>'}</div>
      </div>
      <div class="card">
        <div class="spread"><h2>Evenements</h2></div>
        <div id="ev-list">${events.length ? events.map((e) => `<div class="list-item">
          <div class="spread"><strong>${esc(e.title)}</strong><button class="btn sm danger" data-delev="${e.id}">✕</button></div>
          <div class="small muted">${fmtDate(e.date)} a ${esc(e.time)} &middot; ${e.capacity} places</div></div>`).join('') : '<p class="muted small">Aucun evenement.</p>'}</div>
        <hr style="border:none;border-top:1px solid var(--line);margin:12px 0">
        <div class="field"><label>Titre</label><input id="ev-title" placeholder="Soiree jazz"></div>
        <div class="fields-2">
          <div class="field"><label>Date</label><input id="ev-date" type="date"></div>
          <div class="field"><label>Heure</label><input id="ev-time" type="time" value="20:00" step="900"></div>
        </div>
        <div class="field"><label>Capacite</label><input id="ev-cap" type="number" value="20"></div>
        <button class="btn sm" id="ev-add">Creer l'evenement</button>
      </div>
    </div>`;
  pane.querySelectorAll('button[data-acc]').forEach((b) => b.onclick = async () => { await api.patch(`${A}/group-requests/${b.dataset.acc}`, { status: 'accepted' }); toast('Demande acceptee'); renderGroups(pane); });
  pane.querySelectorAll('button[data-dec]').forEach((b) => b.onclick = async () => { await api.patch(`${A}/group-requests/${b.dataset.dec}`, { status: 'declined' }); toast('Demande refusee'); renderGroups(pane); });
  pane.querySelectorAll('button[data-delev]').forEach((b) => b.onclick = async () => { await api.del(`${A}/events/${b.dataset.delev}`); renderGroups(pane); });
  $('#ev-add').onclick = async () => {
    if (!$('#ev-title').value || !$('#ev-date').value) return toast('Titre et date requis', true);
    await api.post(`${A}/events`, { title: $('#ev-title').value, date: $('#ev-date').value, time: $('#ev-time').value, capacity: $('#ev-cap').value });
    toast('Evenement cree'); renderGroups(pane);
  };
}

// ============================ NOTIFICATIONS (outbox mockee) ==================
async function renderOutbox(pane) {
  const { items } = await api.get(`${A}/outbox`);
  pane.innerHTML = `<div class="card">
    <h2>Boite d'envoi (simulee)</h2>
    <p class="muted small">En demo, les emails / SMS / notifications ne sont pas reellement envoyes : ils sont traces ici pour visualiser les flux.</p>
    ${items.length ? items.map((m) => `<div class="list-item">
      <div class="spread"><strong>${chan(m.channel)} → ${esc(m.recipient)}</strong><span class="small muted">${esc(m.created_at)}</span></div>
      <div>${esc(m.subject)}</div><div class="small muted">${esc(m.body)}</div></div>`).join('') : '<p class="muted small">Rien pour le moment.</p>'}
  </div>`;
}
function chan(c) { return { email: '✉️ Email', sms: '📱 SMS', dashboard: '🔔 Notification' }[c] || c; }
