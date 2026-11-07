"""Base SQLite partagée par le site web et l'application de bureau.

Les montants sont stockés en centimes (entiers). La base est créée et remplie
avec les données fictives au premier lancement.
"""
from __future__ import annotations

import sqlite3
import threading

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS dossiers (
    code TEXT PRIMARY KEY, nom TEXT, forme TEXT, regime_tva TEXT, cloture TEXT,
    collab TEXT, derniere_saisie TEXT, etat TEXT, verrou TEXT);
CREATE TABLE IF NOT EXISTS comptes (
    dossier TEXT, numero TEXT, libelle TEXT, PRIMARY KEY (dossier, numero));
CREATE TABLE IF NOT EXISTS tiers (
    id INTEGER PRIMARY KEY, dossier TEXT, code TEXT, nom TEXT, type TEXT, pays TEXT,
    tva TEXT, compte_charge TEXT, cree_par_saisie INTEGER DEFAULT 0, UNIQUE (dossier, code));
CREATE TABLE IF NOT EXISTS ecritures (
    id INTEGER PRIMARY KEY, dossier TEXT, journal TEXT, date TEXT, piece TEXT,
    libelle TEXT, statut TEXT, facture_id INTEGER);
CREATE TABLE IF NOT EXISTS lignes (
    id INTEGER PRIMARY KEY, ecriture_id INTEGER, compte TEXT, tiers TEXT, libelle TEXT,
    debit INTEGER, credit INTEGER, lettrage TEXT, echeance TEXT);
CREATE INDEX IF NOT EXISTS lignes_ecriture ON lignes (ecriture_id);
CREATE INDEX IF NOT EXISTS ecritures_dossier ON ecritures (dossier, date);
CREATE TABLE IF NOT EXISTS pieces (
    code TEXT PRIMARY KEY, dossier TEXT, recue_le TEXT, expediteur TEXT, reference TEXT,
    montant INTEGER, fichier TEXT);
CREATE TABLE IF NOT EXISTS factures (
    id INTEGER PRIMARY KEY, dossier TEXT, numero TEXT, tiers_id INTEGER, reference TEXT,
    date TEXT, categorie TEXT, piece TEXT, statut TEXT, total_ht INTEGER, total_tva INTEGER,
    total_ttc INTEGER, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS facture_lignes (
    id INTEGER PRIMARY KEY, facture_id INTEGER, position INTEGER, libelle TEXT,
    quantite REAL, prix_unitaire INTEGER, taxe TEXT);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY, dossier TEXT, date TEXT, de TEXT, a TEXT, objet TEXT, corps TEXT,
    piece_jointe TEXT, lu INTEGER, sens TEXT, seed INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS editions (
    id INTEGER PRIMARY KEY, dossier TEXT, type TEXT, params TEXT, numero TEXT, created_at TEXT);
"""

_lock = threading.Lock()
_ready = False


def connect() -> sqlite3.Connection:
    """Ouvre la base (et la crée avec ses données fictives si elle n'existe pas encore)."""
    global _ready
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    if not _ready:
        with _lock:
            conn.executescript(SCHEMA)
            if conn.execute("SELECT COUNT(*) FROM dossiers").fetchone()[0] == 0:
                from . import seed
                seed.build(conn)
                conn.commit()
            _ready = True
    return conn


def rebuild() -> None:
    """Efface la base et la recrée à l'identique (mêmes données fictives)."""
    global _ready
    for suffix in ("", "-wal", "-shm"):
        path = config.DB_PATH.with_name(config.DB_PATH.name + suffix)
        if path.exists():
            path.unlink()
    _ready = False
    connect().close()


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                 "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (key, value))
    conn.commit()
