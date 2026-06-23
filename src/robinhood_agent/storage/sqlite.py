from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union


SCHEMA_VERSION = 1


def connect(path: Union[str, Path]) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS watch_profiles (
            ticker TEXT PRIMARY KEY,
            benchmark TEXT NOT NULL,
            display_name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS thesis_states (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            view TEXT NOT NULL,
            confidence REAL NOT NULL,
            target_position_pct REAL NOT NULL,
            horizon TEXT NOT NULL,
            core_assumptions_json TEXT NOT NULL,
            risks_json TEXT NOT NULL,
            invalidation_conditions_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (ticker) REFERENCES watch_profiles(ticker)
        );
        CREATE INDEX IF NOT EXISTS idx_thesis_states_ticker_updated
            ON thesis_states(ticker, updated_at DESC);

        CREATE TABLE IF NOT EXISTS research_events (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            raw_url TEXT,
            FOREIGN KEY (ticker) REFERENCES watch_profiles(ticker),
            UNIQUE(source, external_id)
        );
        CREATE INDEX IF NOT EXISTS idx_research_events_lookup
            ON research_events(ticker, occurred_at DESC, source);

        CREATE TABLE IF NOT EXISTS research_updates (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            thesis_before TEXT NOT NULL,
            thesis_after TEXT NOT NULL,
            key_changes_json TEXT NOT NULL,
            view TEXT NOT NULL,
            confidence REAL NOT NULL,
            suggested_position_pct REAL NOT NULL,
            invalidation_conditions_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (ticker) REFERENCES watch_profiles(ticker)
        );
        CREATE INDEX IF NOT EXISTS idx_research_updates_ticker_created
            ON research_updates(ticker, created_at DESC);

        CREATE TABLE IF NOT EXISTS paper_orders (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            fee REAL NOT NULL,
            research_update_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (ticker) REFERENCES watch_profiles(ticker),
            FOREIGN KEY (research_update_id) REFERENCES research_updates(id)
        );

        CREATE TABLE IF NOT EXISTS paper_positions (
            ticker TEXT PRIMARY KEY,
            quantity REAL NOT NULL,
            average_cost REAL NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (ticker) REFERENCES watch_profiles(ticker)
        );

        CREATE TABLE IF NOT EXISTS performance_snapshots (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            window TEXT NOT NULL,
            absolute_return REAL NOT NULL,
            benchmark_return REAL NOT NULL,
            max_drawdown REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (ticker) REFERENCES watch_profiles(ticker)
        );
        """
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    connection.commit()
