// ============================================================================
//  MOTEUR ANTI-SURBOOKING
// ----------------------------------------------------------------------------
//  Principe : une reservation n'est acceptee que s'il existe, pour toute la
//  duree du repas, une (ou plusieurs) table(s) physique(s) reellement libre(s)
//  capable(s) d'accueillir le groupe. La capacite physique du restaurant (ses
//  tables / chaises) est donc la limite dure -> le surbooking est impossible.
//
//  Contraintes cumulatives verifiees :
//    1. Assignation d'au moins une table libre couvrant [heure, heure+duree]
//       (avec buffer de remise en place), combinaison de tables autorisee.
//    2. Plafond de couverts par creneau        (optionnel, par service)
//    3. Plafond de couverts sur tout le service (optionnel, par service)
// ============================================================================

const ACTIVE_STATUSES = ['confirmed', 'pending', 'seated'];

// 'HH:MM' -> minutes depuis minuit
export function toMinutes(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
}
// minutes -> 'HH:MM'
export function toHHMM(mins) {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

// Deux intervalles [aStart,aEnd] et [bStart,bEnd] se chevauchent-ils ?
function overlaps(aStart, aEnd, bStart, bEnd) {
  return aStart < bEnd && bStart < aEnd;
}

// Duree d'un repas pour un service donne (surcharge possible par service).
export function turnFor(restaurant, service) {
  return (service && service.turn_time_min) || restaurant.turn_time_min;
}

// weekday JS : 0=dimanche ... 6=samedi (aligne avec la colonne services.weekday)
export function weekdayOf(dateStr) {
  // dateStr = 'YYYY-MM-DD' -> on force midi UTC pour eviter les glissements de TZ
  return new Date(`${dateStr}T12:00:00Z`).getUTCDay();
}

// ----------------------------------------------------------------------------
//  Choix des tables : renvoie la liste d'ids couvrant partySize, ou null.
//  Strategie :
//    - d'abord la plus petite table unique qui accueille le groupe
//      (max_seats >= party, en minimisant le gaspillage de sieges) ;
//    - sinon, combinaison gloutonne de tables "joinable" (max 3) dont la
//      somme des sieges >= party.
// ----------------------------------------------------------------------------
export function pickTables(freeTables, partySize, maxCombine = 3) {
  // 1) table unique, celle qui colle le mieux
  const singles = freeTables
    .filter((t) => t.max_seats >= partySize)
    .sort((a, b) => a.max_seats - b.max_seats || a.min_seats - b.min_seats);
  if (singles.length) return [singles[0].id];

  // 2) combinaison de tables jointes (grandes tables d'abord pour limiter le nombre)
  const joinable = freeTables
    .filter((t) => t.joinable)
    .sort((a, b) => b.max_seats - a.max_seats);
  const combo = [];
  let seats = 0;
  for (const t of joinable) {
    combo.push(t);
    seats += t.max_seats;
    if (seats >= partySize) return combo.map((x) => x.id);
    if (combo.length >= maxCombine) break;
  }
  return null;
}

// ----------------------------------------------------------------------------
//  canSeat : peut-on asseoir `partySize` a `date`/`time` ?
//  Retourne { ok, tableIds, reason }.
//  ctx = { tables, reservations, services } charge par l'appelant (voir repo).
// ----------------------------------------------------------------------------
// ----------------------------------------------------------------------------
//  occupiedTables : quelles tables sont occupees sur la fenetre [start,end] ?
//  Applique la regle du double service : si un service interdit le double
//  service, ses tables sont bloquees pour TOUTE la duree du service (un seul
//  passage) ; sinon elles se liberent apres la duree du repas (+ buffer).
//  Renvoie une Map tableId -> reservation. Logique partagee moteur / plan de salle.
// ----------------------------------------------------------------------------
export function occupiedTables(restaurant, services, reservations, date, start, end) {
  const buffer = restaurant.buffer_min;
  const occ = new Map();
  for (const r of reservations) {
    if (r.date !== date || !ACTIVE_STATUSES.includes(r.status)) continue;
    const rStart = toMinutes(r.time);
    const rSvc = serviceForDateTime(restaurant, services, date, r.time);
    const noDouble = rSvc && rSvc.allow_double_seating === 0;
    let occStart, occEnd;
    if (noDouble) {
      occStart = toMinutes(rSvc.start_time);
      occEnd = toMinutes(rSvc.last_seating) + turnFor(restaurant, rSvc) + buffer;
    } else {
      occStart = rStart;
      occEnd = rStart + r.duration_min + buffer;
    }
    if (overlaps(start, end + buffer, occStart, occEnd)) {
      for (const id of JSON.parse(r.table_ids)) if (!occ.has(id)) occ.set(id, r);
    }
  }
  return occ;
}

export function canSeat(restaurant, ctx, { date, time, partySize, excludeId = null }) {
  const service = serviceForDateTime(restaurant, ctx.services, date, time);
  if (!service) return { ok: false, reason: 'closed' };

  const duration = turnFor(restaurant, service);
  const start = toMinutes(time);
  const end = start + duration;

  // Reservations actives du jour, hors celle qu'on edite eventuellement.
  const dayResa = ctx.reservations.filter(
    (r) => r.date === date && ACTIVE_STATUSES.includes(r.status) && r.id !== excludeId
  );

  // --- Contrainte 1 : tables physiques (logique double service partagee) -----
  const occupied = occupiedTables(restaurant, ctx.services, dayResa, date, start, end);
  const freeTables = ctx.tables.filter((t) => t.active && !occupied.has(t.id));
  const tableIds = pickTables(freeTables, partySize);
  if (!tableIds) return { ok: false, reason: 'no_table' };

  // --- Contraintes 2 & 3 : plafonds de couverts ------------------------------
  let coversInSlot = 0;
  let coversInService = 0;
  const svcStart = toMinutes(service.start_time);
  const svcEnd = toMinutes(service.last_seating) + duration;
  for (const r of dayResa) {
    const rStart = toMinutes(r.time);
    if (rStart === start) coversInSlot += r.party_size;
    if (overlaps(svcStart, svcEnd, rStart, rStart + r.duration_min)) coversInService += r.party_size;
  }

  // --- Contrainte 2 : plafond de couverts par creneau ------------------------
  if (service.slot_capacity != null && coversInSlot + partySize > service.slot_capacity) {
    return { ok: false, reason: 'slot_full' };
  }
  // --- Contrainte 3 : plafond de couverts sur le service ---------------------
  if (service.service_capacity != null && coversInService + partySize > service.service_capacity) {
    return { ok: false, reason: 'service_full' };
  }

  return { ok: true, tableIds, duration, service };
}

// Service couvrant un couple date/heure precis (jour de la semaine + plage).
export function serviceForDateTime(restaurant, services, date, time) {
  const wd = weekdayOf(date);
  const t = toMinutes(time);
  return (
    services.find(
      (s) =>
        s.active &&
        s.weekday === wd &&
        t >= toMinutes(s.start_time) &&
        t <= toMinutes(s.last_seating)
    ) || null
  );
}

// ----------------------------------------------------------------------------
//  availability : liste des creneaux reservables pour une date + un groupe.
//  Regroupe par service, avec pour chaque creneau ok/complet.
// ----------------------------------------------------------------------------
export function availability(restaurant, ctx, { date, partySize }) {
  const wd = weekdayOf(date);
  const services = ctx.services
    .filter((s) => s.active && s.weekday === wd)
    .sort((a, b) => toMinutes(a.start_time) - toMinutes(b.start_time));

  const result = [];
  for (const service of services) {
    const slots = [];
    const step = restaurant.slot_interval_min;
    const from = toMinutes(service.start_time);
    const to = toMinutes(service.last_seating);
    for (let t = from; t <= to; t += step) {
      const time = toHHMM(t);
      const res = canSeat(restaurant, ctx, { date, time, partySize });
      slots.push({ time, available: res.ok, reason: res.reason || null });
    }
    result.push({ service: service.name, serviceId: service.id, slots });
  }
  return result;
}
