// Controleur de la web app client (index.html).
import { api, SLUG, toast, esc, fmtDate, applyBranding } from './api.js';
import { mountBooking } from './booking.js';

const $ = (s) => document.querySelector(s);

(async function () {
  let R;
  try { R = await api.get(`/api/r/${SLUG}`); }
  catch { $('#info-card').innerHTML = 'Restaurant introuvable.'; return; }
  applyBranding(R.branding);
  document.title = `Reserver — ${R.name}`;
  document.querySelector('.brandmark').innerHTML = `${esc(R.name)}<span class="dot">.</span>`;

  // Fiche restaurant
  $('#info-card').innerHTML = `
    <h2>${esc(R.name)}</h2>
    <p class="small">${esc(R.address || '')}</p>
    <p class="small">Tel. ${esc(R.phone || '')}</p>
    <hr style="border:none;border-top:1px solid var(--line);margin:12px 0">
    <div class="row small muted">
      <span>🍽️ ${R.capacity.seats} couverts</span>
      <span>🪑 ${R.capacity.tables} tables</span>
      <span>📅 jusqu'a ${R.horizonDays} j</span>
    </div>`;

  // Widget de reservation
  mountBooking($('#booking'), SLUG, { onGroupRequest: openGroup });

  // Evenements (option)
  if (R.options.events) {
    try {
      const { events } = await api.get(`/api/r/${SLUG}/events`);
      if (events.length) {
        $('#events-card').classList.remove('hidden');
        $('#events-list').innerHTML = events.map((e) => `
          <div class="list-item">
            <strong>${esc(e.title)}</strong>
            <div class="small muted">${fmtDate(e.date)} a ${esc(e.time)} &middot; ${e.capacity} places</div>
            ${e.description ? `<div class="small">${esc(e.description)}</div>` : ''}
          </div>`).join('');
      }
    } catch { /* option indispo */ }
  }

  // Demande de groupe (option)
  if (R.options.group_request) {
    $('#group-card').classList.remove('hidden');
    $('#open-group').onclick = openGroup;
  }

  function openGroup() {
    $('#group-card')?.scrollIntoView({ behavior: 'smooth' });
    const box = $('#group-form');
    box.classList.remove('hidden');
    box.innerHTML = `
      <div class="fields-2">
        <div class="field"><label>Nom *</label><input id="g-name"></div>
        <div class="field"><label>Personnes *</label><input id="g-party" type="number" min="1" value="20"></div>
      </div>
      <div class="fields-2">
        <div class="field"><label>Date souhaitee *</label><input id="g-date" type="date"></div>
        <div class="field"><label>Type d'evenement</label><input id="g-type" placeholder="Anniversaire, seminaire..."></div>
      </div>
      <div class="fields-2">
        <div class="field"><label>Telephone</label><input id="g-phone"></div>
        <div class="field"><label>Budget indicatif</label><input id="g-budget" placeholder="ex. 40€/pers"></div>
      </div>
      <div class="field"><label>Message</label><textarea id="g-msg" rows="2"></textarea></div>
      <button class="btn" id="g-send">Envoyer la demande</button>`;
    $('#g-send').onclick = async (ev) => {
      const name = $('#g-name').value.trim(), party = $('#g-party').value, date = $('#g-date').value;
      if (!name || !party || !date) return toast('Nom, personnes et date requis', true);
      ev.target.disabled = true;
      try {
        await api.post(`/api/r/${SLUG}/group-requests`, {
          customer_name: name, party_size: party, date,
          event_type: $('#g-type').value, phone: $('#g-phone').value,
          budget: $('#g-budget').value, message: $('#g-msg').value,
        });
        box.innerHTML = `<div class="badge green">Demande envoyee ✔</div><p class="small muted">Le restaurant vous recontactera rapidement.</p>`;
      } catch (e) { ev.target.disabled = false; toast(e.message, true); }
    };
  }
})();
