// Couche base de donnees : SQLite embarque (node:sqlite, zero dependance).
// Le schema est concu pour etre "evolutif" : chaque option payante correspond
// a une colonne/table isolee, et les fonctionnalites de base sont autonomes.

import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdirSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dataDir = join(__dirname, '..', 'data');
mkdirSync(dataDir, { recursive: true });

export const DB_PATH = process.env.RESA_DB || join(dataDir, 'resa.sqlite');

export const db = new DatabaseSync(DB_PATH);
db.exec('PRAGMA journal_mode = WAL;');
db.exec('PRAGMA foreign_keys = ON;');

export function migrate() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS restaurants (
      id                INTEGER PRIMARY KEY AUTOINCREMENT,
      slug              TEXT UNIQUE NOT NULL,
      name              TEXT NOT NULL,
      phone             TEXT DEFAULT '',
      address           TEXT DEFAULT '',
      timezone          TEXT DEFAULT 'Europe/Paris',
      slot_interval_min INTEGER NOT NULL DEFAULT 15,   -- pas des creneaux proposes
      turn_time_min     INTEGER NOT NULL DEFAULT 90,   -- duree moyenne d'un repas
      buffer_min        INTEGER NOT NULL DEFAULT 10,   -- temps de remise en place entre 2 services d'une table
      max_party_online  INTEGER NOT NULL DEFAULT 10,   -- au dela => demande de groupe
      horizon_days      INTEGER NOT NULL DEFAULT 60,   -- fenetre de reservation
      settings          TEXT NOT NULL DEFAULT '{}',    -- options activees + config (JSON)
      created_at        TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS dining_tables (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
      name          TEXT NOT NULL,
      min_seats     INTEGER NOT NULL DEFAULT 1,
      max_seats     INTEGER NOT NULL DEFAULT 2,
      zone          TEXT NOT NULL DEFAULT 'Salle',
      joinable      INTEGER NOT NULL DEFAULT 1,   -- peut etre combinee avec une table voisine
      active        INTEGER NOT NULL DEFAULT 1,
      pos_x         INTEGER NOT NULL DEFAULT 0,   -- position sur le plan de salle
      pos_y         INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS services (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      restaurant_id    INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
      name             TEXT NOT NULL,             -- Dejeuner / Diner ...
      weekday          INTEGER NOT NULL,          -- 0=dimanche ... 6=samedi
      start_time       TEXT NOT NULL,             -- 'HH:MM' premier creneau
      last_seating     TEXT NOT NULL,             -- 'HH:MM' dernier creneau propose
      slot_capacity    INTEGER,                   -- couverts max par creneau (option)
      service_capacity INTEGER,                   -- couverts max sur tout le service (option)
      turn_time_min    INTEGER,                   -- duree de table pour ce service (surcharge)
      allow_double_seating INTEGER NOT NULL DEFAULT 1, -- double service sur une meme table ?
      active           INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS closures (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
      date          TEXT NOT NULL,                -- 'YYYY-MM-DD'
      reason        TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS reservations (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
      ref           TEXT NOT NULL,
      date          TEXT NOT NULL,                -- 'YYYY-MM-DD'
      time          TEXT NOT NULL,                -- 'HH:MM'
      party_size    INTEGER NOT NULL,
      duration_min  INTEGER NOT NULL,
      status        TEXT NOT NULL DEFAULT 'confirmed', -- confirmed|pending|seated|cancelled|no_show
      customer_name TEXT NOT NULL,
      phone         TEXT DEFAULT '',
      email         TEXT DEFAULT '',
      message       TEXT DEFAULT '',
      source        TEXT NOT NULL DEFAULT 'web',  -- web|widget|phone|admin
      table_ids     TEXT NOT NULL DEFAULT '[]',   -- tables assignees (JSON)
      created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_resa_lookup ON reservations(restaurant_id, date, status);

    -- Option "Reservation d'evenements"
    CREATE TABLE IF NOT EXISTS events (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
      title         TEXT NOT NULL,
      date          TEXT NOT NULL,
      time          TEXT NOT NULL,
      capacity      INTEGER NOT NULL,
      description   TEXT DEFAULT '',
      created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Option "Demande de privatisation / groupe"
    CREATE TABLE IF NOT EXISTS group_requests (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
      date          TEXT NOT NULL,
      time          TEXT DEFAULT '',
      party_size    INTEGER NOT NULL,
      event_type    TEXT DEFAULT '',
      budget        TEXT DEFAULT '',
      customer_name TEXT NOT NULL,
      phone         TEXT DEFAULT '',
      email         TEXT DEFAULT '',
      message       TEXT DEFAULT '',
      status        TEXT NOT NULL DEFAULT 'new', -- new|accepted|declined
      created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Boite d'envoi simulee : remplace mail/SMS reels pour la demo.
    CREATE TABLE IF NOT EXISTS outbox (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      restaurant_id INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,
      channel       TEXT NOT NULL,                -- email|sms|dashboard
      recipient     TEXT NOT NULL,                -- 'client' | 'restaurant' | adresse
      subject       TEXT NOT NULL,
      body          TEXT NOT NULL,
      created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );
  `);

  // Migrations additives (bases existantes) : ajoute les colonnes manquantes.
  ensureColumn('services', 'allow_double_seating', 'INTEGER NOT NULL DEFAULT 1');
}

// Ajoute une colonne si elle n'existe pas encore (idempotent).
function ensureColumn(table, column, ddl) {
  const cols = db.prepare(`PRAGMA table_info(${table})`).all();
  if (!cols.some((c) => c.name === column)) {
    db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${ddl}`);
  }
}
