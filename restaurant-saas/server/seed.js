// Jeu de donnees de demonstration : un restaurant "Le Petit Comptoir".
// Usage : node --no-warnings server/seed.js --reset
import { db, migrate } from './db.js';

migrate();

const reset = process.argv.includes('--reset');
if (reset) {
  for (const t of ['outbox', 'group_requests', 'events', 'reservations', 'closures', 'services', 'dining_tables', 'restaurants']) {
    db.exec(`DELETE FROM ${t};`);
  }
  db.exec(`DELETE FROM sqlite_sequence;`);
}

const existing = db.prepare('SELECT id FROM restaurants WHERE slug = ?').get('petit-comptoir');
if (existing && !reset) {
  console.log('Donnees deja presentes (utilisez --reset pour reinitialiser).');
  process.exit(0);
}

const settings = {
  options: {
    sms_review: false,
    deposit: false,
    floor_plan: true,        // Plan de salle digital
    sms_reminder: false,
    mailing: false,
    gift_cards: false,
    events: true,            // Reservation d'evenements
    group_request: true,     // Demande de privatisation / groupe
    group_validation: true,  // Validation au-dela d'un seuil
  },
  group_validation_threshold: 8, // a partir de 8 personnes -> validation manuelle
};

const r = db.prepare(`
  INSERT INTO restaurants (slug, name, phone, address, slot_interval_min, turn_time_min, buffer_min, max_party_online, horizon_days, settings)
  VALUES (?,?,?,?,?,?,?,?,?,?)
`).run('petit-comptoir', 'Le Petit Comptoir', '01 23 45 67 89', '12 rue des Halles, 75001 Paris', 15, 90, 10, 12, 60, JSON.stringify(settings));
const rid = r.lastInsertRowid;

// --- Plan de salle : 12 tables, 44 couverts ---------------------------------
const insT = db.prepare(
  'INSERT INTO dining_tables (restaurant_id, name, min_seats, max_seats, zone, joinable, pos_x, pos_y) VALUES (?,?,?,?,?,?,?,?)'
);
const tables = [
  ['T1', 1, 2, 'Salle', 1, 1, 1], ['T2', 1, 2, 'Salle', 1, 2, 1],
  ['T3', 2, 2, 'Salle', 1, 3, 1], ['T4', 2, 4, 'Salle', 1, 1, 2],
  ['T5', 2, 4, 'Salle', 1, 2, 2], ['T6', 2, 4, 'Salle', 1, 3, 2],
  ['T7', 4, 6, 'Salle', 1, 1, 3], ['T8', 4, 6, 'Salle', 1, 2, 3],
  ['B1', 1, 2, 'Terrasse', 1, 5, 1], ['B2', 1, 2, 'Terrasse', 1, 6, 1],
  ['B3', 2, 4, 'Terrasse', 1, 5, 2], ['G1', 6, 8, 'Salle privee', 0, 5, 3],
];
for (const t of tables) insT.run(rid, ...t);

// --- Services : dejeuner (mar-dim) + diner (mar-sam) -------------------------
const insS = db.prepare(
  'INSERT INTO services (restaurant_id, name, weekday, start_time, last_seating, slot_capacity, service_capacity, turn_time_min) VALUES (?,?,?,?,?,?,?,?)'
);
// weekday : 0=dim,1=lun,2=mar,3=mer,4=jeu,5=ven,6=sam. Ferme le lundi.
for (const wd of [2, 3, 4, 5, 6, 0]) {
  insS.run(rid, 'Dejeuner', wd, '12:00', '13:45', 16, null, 90);
}
for (const wd of [2, 3, 4, 5, 6]) {
  insS.run(rid, 'Diner', wd, '19:00', '21:30', null, null, 105);
}

// --- Une fermeture exceptionnelle -------------------------------------------
db.prepare('INSERT INTO closures (restaurant_id, date, reason) VALUES (?,?,?)')
  .run(rid, isoInDays(9), 'Jour ferie');

// --- Un evenement de demonstration ------------------------------------------
db.prepare('INSERT INTO events (restaurant_id, title, date, time, capacity, description) VALUES (?,?,?,?,?,?)')
  .run(rid, 'Soiree degustation vins', isoInDays(14), '20:00', 24, 'Menu 5 services accorde a une selection de vins nature.');

// --- Quelques reservations pour demain (pour montrer l'occupation) ----------
const tomorrow = isoInDays(1);
const dtomorrow = new Date(`${tomorrow}T12:00:00Z`).getUTCDay();
const dinerOpen = [2, 3, 4, 5, 6].includes(dtomorrow);
const dejOpen = [2, 3, 4, 5, 6, 0].includes(dtomorrow);
const insR = db.prepare(`
  INSERT INTO reservations (restaurant_id, ref, date, time, party_size, duration_min, status, customer_name, phone, email, source, table_ids)
  VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
`);
if (dejOpen) {
  insR.run(rid, 'DE-MO01', tomorrow, '12:30', 2, 90, 'confirmed', 'Martin Dupont', '0600000001', '', 'phone', JSON.stringify([tableId(rid, 'T3')]));
  insR.run(rid, 'DE-MO02', tomorrow, '12:30', 4, 90, 'confirmed', 'Claire Petit', '0600000002', '', 'web', JSON.stringify([tableId(rid, 'T4')]));
}
if (dinerOpen) {
  insR.run(rid, 'DE-MO03', tomorrow, '20:00', 6, 105, 'confirmed', 'Groupe Lefevre', '0600000003', '', 'web', JSON.stringify([tableId(rid, 'T7')]));
}

console.log(`Seed OK -> restaurant #${rid} "Le Petit Comptoir" (slug: petit-comptoir).`);
console.log(`${tables.length} tables / ${tables.reduce((s, t) => s + t[2], 0)} couverts.`);

function isoInDays(n) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
function tableId(restaurantId, name) {
  return db.prepare('SELECT id FROM dining_tables WHERE restaurant_id = ? AND name = ?').get(restaurantId, name).id;
}
