// Acces aux donnees + regles applicatives (au-dessus du moteur).
import { db } from './db.js';
import { canSeat, serviceForDateTime, turnFor } from './engine.js';

const q = {
  restBySlug: db.prepare('SELECT * FROM restaurants WHERE slug = ?'),
  restById: db.prepare('SELECT * FROM restaurants WHERE id = ?'),
  tables: db.prepare('SELECT * FROM dining_tables WHERE restaurant_id = ? ORDER BY zone, name'),
  services: db.prepare('SELECT * FROM services WHERE restaurant_id = ? ORDER BY weekday, start_time'),
  closures: db.prepare('SELECT * FROM closures WHERE restaurant_id = ? ORDER BY date'),
  closureOn: db.prepare('SELECT * FROM closures WHERE restaurant_id = ? AND date = ?'),
  resaByDate: db.prepare('SELECT * FROM reservations WHERE restaurant_id = ? AND date = ?'),
  resaRange: db.prepare(
    'SELECT * FROM reservations WHERE restaurant_id = ? AND date >= ? AND date <= ? ORDER BY date, time'
  ),
};

export function getRestaurant(slugOrId) {
  const r =
    typeof slugOrId === 'number'
      ? q.restById.get(slugOrId)
      : q.restBySlug.get(slugOrId) || q.restById.get(Number(slugOrId));
  if (!r) return null;
  r.settings = JSON.parse(r.settings || '{}');
  return r;
}

export function loadContext(restaurantId, date) {
  return {
    tables: q.tables.all(restaurantId),
    services: q.services.all(restaurantId),
    reservations: date ? q.resaByDate.all(restaurantId, date) : [],
  };
}

export function isClosed(restaurantId, date) {
  return !!q.closureOn.get(restaurantId, date);
}

export function listTables(id) { return q.tables.all(id); }
export function listServices(id) { return q.services.all(id); }
export function listClosures(id) { return q.closures.all(id); }

export function totalCapacity(restaurantId) {
  const tables = q.tables.all(restaurantId).filter((t) => t.active);
  return {
    tables: tables.length,
    seats: tables.reduce((s, t) => s + t.max_seats, 0),
  };
}

// Reference lisible : AB-3F7K
function makeRef() {
  const a = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let s = '';
  for (let i = 0; i < 6; i++) s += a[Math.floor(Math.random() * a.length)];
  return `${s.slice(0, 2)}-${s.slice(2)}`;
}

// --- Boite d'envoi simulee (remplace mail/SMS reels) ------------------------
const insOutbox = db.prepare(
  'INSERT INTO outbox (restaurant_id, channel, recipient, subject, body) VALUES (?,?,?,?,?)'
);
export function notify(restaurantId, channel, recipient, subject, body) {
  insOutbox.run(restaurantId, channel, recipient, subject, body);
}

const insResa = db.prepare(`
  INSERT INTO reservations
    (restaurant_id, ref, date, time, party_size, duration_min, status,
     customer_name, phone, email, message, source, table_ids)
  VALUES (@restaurant_id,@ref,@date,@time,@party_size,@duration_min,@status,
     @customer_name,@phone,@email,@message,@source,@table_ids)
`);

// ----------------------------------------------------------------------------
//  Creation de reservation (transactionnelle) : re-verifie la disponibilite au
//  moment de l'ecriture pour eviter toute course entre deux clients.
// ----------------------------------------------------------------------------
export function createReservation(restaurant, payload) {
  const { date, time, party_size } = payload;
  const partySize = Number(party_size);

  if (isClosed(restaurant.id, date)) return { error: 'closed', message: 'Restaurant ferme ce jour.' };
  if (partySize < 1) return { error: 'invalid', message: 'Nombre de couverts invalide.' };
  if (partySize > restaurant.max_party_online) {
    return { error: 'too_large', message: `Au-dela de ${restaurant.max_party_online} personnes, merci de faire une demande de groupe.` };
  }

  // node:sqlite n'expose pas .transaction() : on gere BEGIN/COMMIT a la main.
  db.exec('BEGIN IMMEDIATE');
  try {
    const ctx = loadContext(restaurant.id, date);
    const seat = canSeat(restaurant, ctx, { date, time, partySize });
    if (!seat.ok) { db.exec('ROLLBACK'); return { error: seat.reason || 'unavailable', message: 'Creneau indisponible.' }; }

    // Option "validation groupe" : au-dela d'un seuil, la resa passe en attente.
    const opts = restaurant.settings.options || {};
    const threshold = restaurant.settings.group_validation_threshold;
    const needsValidation = opts.group_validation && threshold && partySize >= threshold;
    const status = needsValidation ? 'pending' : 'confirmed';

    const row = {
      restaurant_id: restaurant.id,
      ref: makeRef(),
      date,
      time,
      party_size: partySize,
      duration_min: seat.duration,
      status,
      customer_name: payload.customer_name || '',
      phone: payload.phone || '',
      email: payload.email || '',
      message: payload.message || '',
      source: payload.source || 'web',
      table_ids: JSON.stringify(seat.tableIds),
    };
    const info = insResa.run(row);
    const id = info.lastInsertRowid;

    // Notifications de base (simulees) : restaurant + client.
    notify(restaurant.id, 'dashboard', 'restaurant',
      `Nouvelle reservation ${row.ref}`,
      `${row.customer_name} - ${partySize} couverts le ${date} a ${time} (table ${seat.tableIds.join('+')}). Statut: ${status}.`);
    if (row.email) {
      notify(restaurant.id, 'email', row.email,
        needsValidation ? `Demande recue ${row.ref}` : `Confirmation de reservation ${row.ref}`,
        needsValidation
          ? `Bonjour ${row.customer_name}, votre demande pour ${partySize} personnes le ${date} a ${time} est en cours de validation par le restaurant.`
          : `Bonjour ${row.customer_name}, votre table pour ${partySize} personnes est confirmee le ${date} a ${time}. Reference ${row.ref}.`);
    }

    db.exec('COMMIT');
    return { id, ref: row.ref, status, tableIds: seat.tableIds, duration: row.duration_min };
  } catch (err) {
    try { db.exec('ROLLBACK'); } catch { /* deja termine */ }
    throw err;
  }
}

export function listReservations(restaurantId, date) {
  return q.resaByDate.all(restaurantId, date).sort((a, b) => a.time.localeCompare(b.time));
}
export function listReservationsRange(restaurantId, from, to) {
  return q.resaRange.all(restaurantId, from, to);
}

export function setReservationStatus(id, status) {
  db.prepare('UPDATE reservations SET status = ? WHERE id = ?').run(status, id);
  return db.prepare('SELECT * FROM reservations WHERE id = ?').get(id);
}
