// Definition de toutes les routes API. Regroupees ici pour la lisibilite du demo.
import { db } from '../db.js';
import {
  getRestaurant, loadContext, isClosed, listTables, listServices, listClosures,
  listReservations, listReservationsRange, createReservation, setReservationStatus,
  totalCapacity, notify,
} from '../repo.js';
import { availability, canSeat, weekdayOf, toMinutes, turnFor, serviceForDateTime } from '../engine.js';

const bad = (message, status = 400) => ({ __status: status, error: 'bad_request', message });
const notFound = () => ({ __status: 404, error: 'not_found' });

// Vue publique d'un restaurant (sans donnees sensibles).
function publicRestaurant(r) {
  return {
    slug: r.slug, name: r.name, phone: r.phone, address: r.address,
    maxPartyOnline: r.max_party_online, horizonDays: r.horizon_days,
    slotInterval: r.slot_interval_min, options: r.settings.options || {},
    groupValidationThreshold: r.settings.group_validation_threshold || null,
    capacity: totalCapacity(r.id),
  };
}

export function registerRoutes(route) {
  // ========================================================================
  //  COTE CLIENT (site + web app)
  // ========================================================================
  route('GET', '/api/r/:slug', ({ params }) => {
    const r = getRestaurant(params.slug);
    return r ? publicRestaurant(r) : notFound();
  });

  route('GET', '/api/r/:slug/availability', ({ params, query }) => {
    const r = getRestaurant(params.slug);
    if (!r) return notFound();
    const date = query.date;
    const party = Number(query.party || 2);
    if (!date) return bad('date requise');
    if (isClosed(r.id, date)) return { date, closed: true, services: [] };
    const ctx = loadContext(r.id, date);
    return { date, closed: false, party, services: availability(r, ctx, { date, partySize: party }) };
  });

  route('POST', '/api/r/:slug/reservations', ({ params, body }) => {
    const r = getRestaurant(params.slug);
    if (!r) return notFound();
    if (!body.customer_name || !body.date || !body.time || !body.party_size) {
      return bad('Champs requis : nom, date, heure, couverts.');
    }
    const result = createReservation(r, { ...body, source: body.source || 'web' });
    if (result.error) return { __status: 409, ...result };
    return result;
  });

  route('POST', '/api/r/:slug/group-requests', ({ params, body }) => {
    const r = getRestaurant(params.slug);
    if (!r) return notFound();
    if (!(r.settings.options || {}).group_request) return bad('Option non activee.');
    if (!body.customer_name || !body.date || !body.party_size) return bad('Champs requis manquants.');
    const info = db.prepare(`
      INSERT INTO group_requests (restaurant_id, date, time, party_size, event_type, budget, customer_name, phone, email, message)
      VALUES (?,?,?,?,?,?,?,?,?,?)
    `).run(r.id, body.date, body.time || '', Number(body.party_size), body.event_type || '', body.budget || '',
      body.customer_name, body.phone || '', body.email || '', body.message || '');
    notify(r.id, 'dashboard', 'restaurant', 'Nouvelle demande de groupe',
      `${body.customer_name} - ${body.party_size} pers. le ${body.date}. Type: ${body.event_type || 'n/c'}.`);
    return { id: info.lastInsertRowid, status: 'new' };
  });

  route('GET', '/api/r/:slug/events', ({ params }) => {
    const r = getRestaurant(params.slug);
    if (!r) return notFound();
    const events = db.prepare('SELECT * FROM events WHERE restaurant_id = ? AND date >= date(\'now\') ORDER BY date, time').all(r.id);
    return { events };
  });

  // ========================================================================
  //  COTE ADMIN (tableau de bord restaurant)
  //  NB : demo -> pas d'authentification. En prod, proteger par session/JWT.
  // ========================================================================
  const admin = (slug) => getRestaurant(slug);

  route('GET', '/api/admin/:slug/overview', ({ params, query }) => {
    const r = admin(params.slug);
    if (!r) return notFound();
    const date = query.date || new Date().toISOString().slice(0, 10);
    const resas = listReservations(r.id, date).filter((x) => x.status !== 'cancelled');
    const covers = resas.reduce((s, x) => s + x.party_size, 0);
    const pending = db.prepare("SELECT COUNT(*) c FROM reservations WHERE restaurant_id=? AND status='pending'").get(r.id).c;
    const groupReqs = db.prepare("SELECT COUNT(*) c FROM group_requests WHERE restaurant_id=? AND status='new'").get(r.id).c;
    return {
      restaurant: { slug: r.slug, name: r.name, settings: r.settings },
      capacity: totalCapacity(r.id),
      today: { date, reservations: resas.length, covers, pending },
      groupRequests: groupReqs,
    };
  });

  // ---- Tables --------------------------------------------------------------
  route('GET', '/api/admin/:slug/tables', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    return { tables: listTables(r.id) };
  });
  route('POST', '/api/admin/:slug/tables', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    const info = db.prepare(`INSERT INTO dining_tables (restaurant_id,name,min_seats,max_seats,zone,joinable,pos_x,pos_y)
      VALUES (?,?,?,?,?,?,?,?)`).run(r.id, body.name || 'T', Number(body.min_seats || 1), Number(body.max_seats || 2),
      body.zone || 'Salle', body.joinable ? 1 : 0, Number(body.pos_x || 0), Number(body.pos_y || 0));
    return { id: info.lastInsertRowid };
  });
  route('PATCH', '/api/admin/:slug/tables/:id', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    const t = db.prepare('SELECT * FROM dining_tables WHERE id=? AND restaurant_id=?').get(params.id, r.id);
    if (!t) return notFound();
    const f = { ...t, ...body };
    db.prepare(`UPDATE dining_tables SET name=?,min_seats=?,max_seats=?,zone=?,joinable=?,active=?,pos_x=?,pos_y=? WHERE id=?`)
      .run(f.name, Number(f.min_seats), Number(f.max_seats), f.zone, f.joinable ? 1 : 0, f.active ? 1 : 0, Number(f.pos_x), Number(f.pos_y), t.id);
    return { ok: true };
  });
  route('DELETE', '/api/admin/:slug/tables/:id', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    db.prepare('DELETE FROM dining_tables WHERE id=? AND restaurant_id=?').run(params.id, r.id);
    return { ok: true };
  });
  // Generation rapide du plan de salle a partir de comptages (config express).
  route('POST', '/api/admin/:slug/tables/bulk', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    // body.groups = [{count, min_seats, max_seats, zone, prefix}]
    const groups = Array.isArray(body.groups) ? body.groups : [];
    if (body.replace) db.prepare('DELETE FROM dining_tables WHERE restaurant_id=?').run(r.id);
    const ins = db.prepare(`INSERT INTO dining_tables (restaurant_id,name,min_seats,max_seats,zone,joinable,pos_x,pos_y) VALUES (?,?,?,?,?,?,?,?)`);
    let created = 0;
    for (const g of groups) {
      const prefix = g.prefix || 'T';
      for (let i = 1; i <= Number(g.count || 0); i++) {
        ins.run(r.id, `${prefix}${i}`, Number(g.min_seats || 1), Number(g.max_seats || 2), g.zone || 'Salle', 1, (i - 1) % 4 + 1, created % 4 + 1);
        created++;
      }
    }
    return { created, capacity: totalCapacity(r.id) };
  });

  // ---- Services & fermetures ----------------------------------------------
  route('GET', '/api/admin/:slug/services', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    return { services: listServices(r.id) };
  });
  route('POST', '/api/admin/:slug/services', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    const info = db.prepare(`INSERT INTO services (restaurant_id,name,weekday,start_time,last_seating,slot_capacity,service_capacity,turn_time_min)
      VALUES (?,?,?,?,?,?,?,?)`).run(r.id, body.name || 'Service', Number(body.weekday), body.start_time, body.last_seating,
      body.slot_capacity ? Number(body.slot_capacity) : null, body.service_capacity ? Number(body.service_capacity) : null,
      body.turn_time_min ? Number(body.turn_time_min) : null);
    return { id: info.lastInsertRowid };
  });
  route('DELETE', '/api/admin/:slug/services/:id', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    db.prepare('DELETE FROM services WHERE id=? AND restaurant_id=?').run(params.id, r.id);
    return { ok: true };
  });
  route('GET', '/api/admin/:slug/closures', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    return { closures: listClosures(r.id) };
  });
  route('POST', '/api/admin/:slug/closures', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    if (!body.date) return bad('date requise');
    const info = db.prepare('INSERT INTO closures (restaurant_id,date,reason) VALUES (?,?,?)').run(r.id, body.date, body.reason || '');
    return { id: info.lastInsertRowid };
  });
  route('DELETE', '/api/admin/:slug/closures/:id', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    db.prepare('DELETE FROM closures WHERE id=? AND restaurant_id=?').run(params.id, r.id);
    return { ok: true };
  });

  // ---- Reservations (consultation, saisie tel, statuts) --------------------
  route('GET', '/api/admin/:slug/reservations', ({ params, query }) => {
    const r = admin(params.slug); if (!r) return notFound();
    if (query.from && query.to) return { reservations: listReservationsRange(r.id, query.from, query.to) };
    const date = query.date || new Date().toISOString().slice(0, 10);
    const tablesById = Object.fromEntries(listTables(r.id).map((t) => [t.id, t.name]));
    const reservations = listReservations(r.id, date).map((x) => ({
      ...x, table_names: JSON.parse(x.table_ids).map((id) => tablesById[id] || `#${id}`),
    }));
    return { date, reservations };
  });
  route('POST', '/api/admin/:slug/reservations', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    const result = createReservation(r, { ...body, source: 'phone' }); // saisie telephone
    if (result.error) return { __status: 409, ...result };
    return result;
  });
  route('PATCH', '/api/admin/:slug/reservations/:id', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    const allowed = ['confirmed', 'pending', 'seated', 'cancelled', 'no_show'];
    if (!allowed.includes(body.status)) return bad('statut invalide');
    const row = setReservationStatus(params.id, body.status);
    return { ok: true, status: row.status };
  });

  // ---- Plan de salle (option floor_plan) : occupation a un instant T -------
  route('GET', '/api/admin/:slug/floorplan', ({ params, query }) => {
    const r = admin(params.slug); if (!r) return notFound();
    const date = query.date || new Date().toISOString().slice(0, 10);
    const time = query.time || '20:00';
    const ctx = loadContext(r.id, date);
    const svc = serviceForDateTime(r, ctx.services, date, time);
    const duration = svc ? turnFor(r, svc) : r.turn_time_min;
    const start = toMinutes(time), end = start + duration, buf = r.buffer_min;
    const active = ctx.reservations.filter((x) => ['confirmed', 'pending', 'seated'].includes(x.status));
    const occ = {};
    for (const x of active) {
      const s = toMinutes(x.time), e = s + x.duration_min + buf;
      if (s < end + buf && start < e) for (const id of JSON.parse(x.table_ids)) occ[id] = x;
    }
    const tables = ctx.tables.map((t) => ({
      id: t.id, name: t.name, zone: t.zone, min: t.min_seats, max: t.max_seats,
      active: !!t.active, pos_x: t.pos_x, pos_y: t.pos_y,
      occupiedBy: occ[t.id] ? { ref: occ[t.id].ref, name: occ[t.id].customer_name, party: occ[t.id].party_size, time: occ[t.id].time } : null,
    }));
    const seatsTotal = ctx.tables.filter((t) => t.active).reduce((s, t) => s + t.max_seats, 0);
    const seatsOccupied = Object.values(occ).reduce((s, x) => s + x.party_size, 0);
    return { date, time, open: !!svc, service: svc?.name || null, tables, seatsTotal, seatsOccupied };
  });

  // ---- Reglages (options + configuration generale) -------------------------
  route('GET', '/api/admin/:slug/settings', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    return {
      general: {
        name: r.name, phone: r.phone, address: r.address,
        slot_interval_min: r.slot_interval_min, turn_time_min: r.turn_time_min,
        buffer_min: r.buffer_min, max_party_online: r.max_party_online, horizon_days: r.horizon_days,
      },
      settings: r.settings,
    };
  });
  route('PATCH', '/api/admin/:slug/settings', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    const g = body.general || {};
    if (Object.keys(g).length) {
      db.prepare(`UPDATE restaurants SET name=?,phone=?,address=?,slot_interval_min=?,turn_time_min=?,buffer_min=?,max_party_online=?,horizon_days=? WHERE id=?`)
        .run(g.name ?? r.name, g.phone ?? r.phone, g.address ?? r.address,
          Number(g.slot_interval_min ?? r.slot_interval_min), Number(g.turn_time_min ?? r.turn_time_min),
          Number(g.buffer_min ?? r.buffer_min), Number(g.max_party_online ?? r.max_party_online),
          Number(g.horizon_days ?? r.horizon_days), r.id);
    }
    if (body.settings) {
      db.prepare('UPDATE restaurants SET settings=? WHERE id=?').run(JSON.stringify(body.settings), r.id);
    }
    return { ok: true };
  });

  // ---- Boite d'envoi simulee (mail/SMS mockes) -----------------------------
  route('GET', '/api/admin/:slug/outbox', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    const items = db.prepare('SELECT * FROM outbox WHERE restaurant_id=? ORDER BY id DESC LIMIT 50').all(r.id);
    return { items };
  });

  // ---- Demandes de groupe / privatisation ----------------------------------
  route('GET', '/api/admin/:slug/group-requests', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    return { requests: db.prepare('SELECT * FROM group_requests WHERE restaurant_id=? ORDER BY id DESC').all(r.id) };
  });
  route('PATCH', '/api/admin/:slug/group-requests/:id', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    const status = ['new', 'accepted', 'declined'].includes(body.status) ? body.status : 'new';
    db.prepare('UPDATE group_requests SET status=? WHERE id=? AND restaurant_id=?').run(status, params.id, r.id);
    return { ok: true, status };
  });

  // ---- Evenements ----------------------------------------------------------
  route('GET', '/api/admin/:slug/events', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    return { events: db.prepare('SELECT * FROM events WHERE restaurant_id=? ORDER BY date, time').all(r.id) };
  });
  route('POST', '/api/admin/:slug/events', ({ params, body }) => {
    const r = admin(params.slug); if (!r) return notFound();
    if (!body.title || !body.date || !body.time || !body.capacity) return bad('Champs requis manquants.');
    const info = db.prepare('INSERT INTO events (restaurant_id,title,date,time,capacity,description) VALUES (?,?,?,?,?,?)')
      .run(r.id, body.title, body.date, body.time, Number(body.capacity), body.description || '');
    return { id: info.lastInsertRowid };
  });
  route('DELETE', '/api/admin/:slug/events/:id', ({ params }) => {
    const r = admin(params.slug); if (!r) return notFound();
    db.prepare('DELETE FROM events WHERE id=? AND restaurant_id=?').run(params.id, r.id);
    return { ok: true };
  });
}
