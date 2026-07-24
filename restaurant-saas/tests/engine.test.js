// Tests unitaires du moteur anti-surbooking (node --test).
// Lancer : node --test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pickTables, canSeat, availability, toMinutes, toHHMM, weekdayOf } from '../server/engine.js';

const restaurant = { turn_time_min: 90, buffer_min: 0, slot_interval_min: 30 };

// Plan de salle : 2x deux-places, 1x quatre-places, 1x six-places
const tables = [
  { id: 1, name: 'T1', min_seats: 1, max_seats: 2, joinable: 1, active: 1 },
  { id: 2, name: 'T2', min_seats: 1, max_seats: 2, joinable: 1, active: 1 },
  { id: 3, name: 'T3', min_seats: 2, max_seats: 4, joinable: 1, active: 1 },
  { id: 4, name: 'T4', min_seats: 4, max_seats: 6, joinable: 0, active: 1 },
];
// Un mardi (weekday 2) : services dej + diner
const services = [
  { id: 1, name: 'Dejeuner', weekday: 2, start_time: '12:00', last_seating: '13:30', active: 1, slot_capacity: null, service_capacity: null, turn_time_min: null },
];
// 2026-07-28 est un mardi
const DATE = '2026-07-28';

test('conversions minutes <-> HH:MM', () => {
  assert.equal(toMinutes('12:30'), 750);
  assert.equal(toHHMM(750), '12:30');
  assert.equal(weekdayOf(DATE), 2);
});

test('pickTables choisit la plus petite table qui convient', () => {
  assert.deepEqual(pickTables(tables, 2), [1]);           // colle au 2-places
  assert.deepEqual(pickTables(tables, 3), [3]);           // passe au 4-places
  assert.deepEqual(pickTables(tables, 5), [4]);           // 6-places
});

test('pickTables combine des tables joignables si besoin', () => {
  const onlyTwos = tables.filter((t) => t.max_seats === 2); // 2 x 2-places
  assert.deepEqual(pickTables(onlyTwos, 4), [1, 2]);
  assert.equal(pickTables(onlyTwos, 5), null);             // 4 sieges max -> impossible
});

test('canSeat accepte quand une table est libre', () => {
  const ctx = { tables, services, reservations: [] };
  const res = canSeat(restaurant, ctx, { date: DATE, time: '12:30', partySize: 2 });
  assert.equal(res.ok, true);
  assert.equal(res.tableIds.length, 1);
});

test('canSeat refuse hors service (ferme)', () => {
  const ctx = { tables, services, reservations: [] };
  const res = canSeat(restaurant, ctx, { date: DATE, time: '18:00', partySize: 2 });
  assert.equal(res.ok, false);
  assert.equal(res.reason, 'closed');
});

test('ANTI-SURBOOKING : la table occupee n\'est pas re-attribuee sur creneau chevauchant', () => {
  // On occupe les 2 deux-places et le 4-places a 12:30 (90 min -> jusqu'a 14:00)
  const reservations = [
    { id: 10, date: DATE, time: '12:30', duration_min: 90, party_size: 2, status: 'confirmed', table_ids: '[1]' },
    { id: 11, date: DATE, time: '12:30', duration_min: 90, party_size: 4, status: 'confirmed', table_ids: '[3]' },
    { id: 12, date: DATE, time: '12:30', duration_min: 90, party_size: 2, status: 'confirmed', table_ids: '[2]' },
  ];
  const ctx = { tables, services, reservations };
  // Un groupe de 2 a 13:00 chevauche : seule reste la table 4 (6-places) -> ok mais sur T4
  const r2 = canSeat(restaurant, ctx, { date: DATE, time: '13:00', partySize: 2 });
  assert.equal(r2.ok, true);
  assert.deepEqual(r2.tableIds, [4]);
  // Un 2e groupe simultane ne trouve plus AUCUNE table -> refuse
  const withT4 = [...reservations, { id: 13, date: DATE, time: '13:00', duration_min: 90, party_size: 2, status: 'confirmed', table_ids: '[4]' }];
  const r3 = canSeat(restaurant, { tables, services, reservations: withT4 }, { date: DATE, time: '13:00', partySize: 2 });
  assert.equal(r3.ok, false);
  assert.equal(r3.reason, 'no_table');
});

test('DOUBLE SERVICE désactivé : une table = un seul groupe pour tout le service', () => {
  const svcSimple = [{ ...services[0], allow_double_seating: 0, turn_time_min: 60 }];
  const oneTable = [tables[0]]; // une seule 2-places
  // Groupe de 2 a 12:00. Avec double service OFF, la table est prise tout le service.
  const reservations = [{ id: 50, date: DATE, time: '12:00', duration_min: 60, party_size: 2, status: 'confirmed', table_ids: '[1]' }];
  const ctx = { tables: oneTable, services: svcSimple, reservations };
  // Meme apres 60 min (13:00), la table reste bloquee jusqu'a la fin du service.
  assert.equal(canSeat(restaurant, ctx, { date: DATE, time: '13:00', partySize: 2 }).ok, false);
});

test('DOUBLE SERVICE activé : la table tourne apres la duree de repas', () => {
  const svcDouble = [{ ...services[0], allow_double_seating: 1, turn_time_min: 60 }];
  const oneTable = [tables[0]];
  const reservations = [{ id: 51, date: DATE, time: '12:00', duration_min: 60, party_size: 2, status: 'confirmed', table_ids: '[1]' }];
  const ctx = { tables: oneTable, services: svcDouble, reservations };
  // A 13:00 (apres 60 min, buffer 0) la table est de nouveau libre.
  assert.equal(canSeat(restaurant, ctx, { date: DATE, time: '13:00', partySize: 2 }).ok, true);
});

test('creneau libere apres la duree du repas (pas de chevauchement)', () => {
  // Table 1 occupee 12:00->13:30. A 13:30 (buffer 0) elle redevient disponible.
  const reservations = [{ id: 20, date: DATE, time: '12:00', duration_min: 90, party_size: 2, status: 'confirmed', table_ids: '[1]' }];
  const ctx = { tables: [tables[0]], services, reservations };
  assert.equal(canSeat(restaurant, ctx, { date: DATE, time: '12:30', partySize: 2 }).ok, false); // chevauche
  assert.equal(canSeat(restaurant, ctx, { date: DATE, time: '13:30', partySize: 2 }).ok, true);  // apres
});

test('plafond de couverts par creneau respecte', () => {
  const svc = [{ ...services[0], slot_capacity: 4 }];
  const reservations = [{ id: 30, date: DATE, time: '12:00', duration_min: 90, party_size: 4, status: 'confirmed', table_ids: '[3]' }];
  const ctx = { tables, services: svc, reservations };
  // 4 couverts deja sur ce creneau -> un +1 depasse le plafond meme si des tables restent libres
  const res = canSeat(restaurant, ctx, { date: DATE, time: '12:00', partySize: 2 });
  assert.equal(res.ok, false);
  assert.equal(res.reason, 'slot_full');
});

test('availability marque les creneaux complets', () => {
  // Restaurant a une seule table 2-places, occupee tout le service
  const ctx = {
    tables: [tables[0]], services,
    reservations: [{ id: 40, date: DATE, time: '12:00', duration_min: 120, party_size: 2, status: 'confirmed', table_ids: '[1]' }],
  };
  const av = availability(restaurant, ctx, { date: DATE, partySize: 2 });
  const dej = av.find((s) => s.service === 'Dejeuner');
  assert.ok(dej.slots.every((s) => !s.available || toMinutes(s.time) >= toMinutes('14:00')));
});
