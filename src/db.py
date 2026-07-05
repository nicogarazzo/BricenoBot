"""Utilidades de base de datos para BricenoBot."""
from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "bricenobot.duckdb"


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    DATA_DIR.mkdir(exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)
