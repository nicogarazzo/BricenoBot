"""Ingesta de contratos SECOP II (datos.gov.co, API SODA) hacia DuckDB.

Dataset principal: SECOP II - Contratos Electrónicos (jbjy-vk9h).
Fuente: Agencia Nacional de Contratación Pública, Colombia Compra Eficiente.

Uso:
    python -m src.ingest --limit 50000       # muestra (contratos más recientes)
    python -m src.ingest --full              # dataset completo (~5.6M filas)
    python -m src.ingest --desde 2018-08-07  # desde una fecha (paginado por mes)
"""
import argparse
import sys
import time
from datetime import date

import pandas as pd
import requests

from .db import connect

BASE_URL = "https://www.datos.gov.co/resource/jbjy-vk9h.json"
PAGE_SIZE = 50_000

# Columnas relevantes para el motor de banderas (de las 84 disponibles)
COLUMNS = [
    "id_contrato",
    "proceso_de_compra",
    "nombre_entidad",
    "nit_entidad",
    "codigo_entidad",
    "departamento",
    "ciudad",
    "orden",
    "sector",
    "rama",
    "estado_contrato",
    "tipo_de_contrato",
    "modalidad_de_contratacion",
    "justificacion_modalidad_de",
    "objeto_del_contrato",
    "fecha_de_firma",
    "fecha_de_inicio_del_contrato",
    "fecha_de_fin_del_contrato",
    "tipodocproveedor",
    "documento_proveedor",
    "codigo_proveedor",
    "proveedor_adjudicado",
    "nombre_representante_legal",
    "identificaci_n_representante_legal",
    "es_pyme",
    "valor_del_contrato",
    "valor_pagado",
    "valor_de_pago_adelantado",
    "dias_adicionados",
]

NUMERIC_COLS = [
    "valor_del_contrato",
    "valor_pagado",
    "valor_de_pago_adelantado",
    "dias_adicionados",
]
DATE_COLS = [
    "fecha_de_firma",
    "fecha_de_inicio_del_contrato",
    "fecha_de_fin_del_contrato",
]


# Socrata ordena los NULL primero en DESC: siempre hay que excluirlos
BASE_WHERE = "fecha_de_firma IS NOT NULL AND valor_del_contrato > 0"


def fetch_page(
    offset: int,
    limit: int,
    session: requests.Session,
    where: str = BASE_WHERE,
    order: str = "fecha_de_firma DESC",
) -> list[dict]:
    params = {
        "$select": ",".join(COLUMNS),
        "$where": where,
        "$order": order,
        "$limit": limit,
        "$offset": offset,
    }
    for attempt in range(8):
        try:
            resp = session.get(BASE_URL, params=params, timeout=180)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            wait = 2**attempt
            print(f"  reintento {attempt + 1}/8 en {wait}s ({exc})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"API no respondió tras 8 intentos (offset={offset})")


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[COLUMNS].copy()
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    # Normalización básica de identidades (el 60% del trabajo real)
    df["nit_entidad"] = df["nit_entidad"].astype(str).str.strip().str.split("-").str[0]
    df["documento_proveedor"] = (
        df["documento_proveedor"].astype(str).str.strip().str.split("-").str[0]
    )
    df["nombre_entidad"] = df["nombre_entidad"].str.strip().str.rstrip("*").str.upper()
    df["proveedor_adjudicado"] = df["proveedor_adjudicado"].str.strip().str.upper()
    return df


def insert(con, df: pd.DataFrame, created: bool) -> bool:
    if not created:
        con.execute("CREATE TABLE contratos AS SELECT * FROM df")
    else:
        con.execute("INSERT INTO contratos SELECT * FROM df")
    return True


def month_windows(desde: date) -> list[tuple[str, str]]:
    """Ventanas mensuales [inicio, fin) desde una fecha hasta hoy."""
    windows = []
    y, m = desde.year, desde.month
    start = desde.isoformat()
    while date(y, m, 1) <= date.today():
        y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
        end = date(y2, m2, 1).isoformat()
        windows.append((start, end))
        y, m = y2, m2
        start = date(y, m, 1).isoformat()
    return windows


def ingest(max_rows: int | None, desde: date | None = None) -> None:
    con = connect()
    con.execute("DROP TABLE IF EXISTS contratos")
    session = requests.Session()
    session.headers["Accept"] = "application/json"
    total, created = 0, False
    t0 = time.time()

    if desde is not None:
        # Paginación particionada por mes: evita offsets profundos de Socrata
        # y permite ver el progreso. Orden ASC para recorrer cronológicamente.
        for w_start, w_end in month_windows(desde):
            where = (
                f"{BASE_WHERE} AND fecha_de_firma >= '{w_start}T00:00:00' "
                f"AND fecha_de_firma < '{w_end}T00:00:00'"
            )
            offset, mes_total = 0, 0
            while True:
                rows = fetch_page(offset, PAGE_SIZE, session, where, "fecha_de_firma ASC")
                if not rows:
                    break
                created = insert(con, normalize(pd.DataFrame(rows)), created)
                mes_total += len(rows)
                offset += len(rows)
                if len(rows) < PAGE_SIZE:
                    break
                time.sleep(0.5)  # cortesía con la API en corridas largas
            total += mes_total
            mins = (time.time() - t0) / 60
            print(f"{w_start[:7]}: {mes_total:>8,} contratos (acumulado {total:>10,}, {mins:.0f} min)",
                  flush=True)
    else:
        offset = 0
        while True:
            limit = PAGE_SIZE if max_rows is None else min(PAGE_SIZE, max_rows - total)
            if limit <= 0:
                break
            print(f"Descargando filas {offset:,} a {offset + limit:,}...", flush=True)
            rows = fetch_page(offset, limit, session)
            if not rows:
                break
            created = insert(con, normalize(pd.DataFrame(rows)), created)
            total += len(rows)
            offset += len(rows)
            if len(rows) < limit:
                break

    con.execute(
        """
        CREATE OR REPLACE VIEW contratos_clean AS
        SELECT *,
               year(fecha_de_firma)  AS anio,
               month(fecha_de_firma) AS mes,
               date_trunc('month', fecha_de_firma) AS mes_firma,
               modalidad_de_contratacion ILIKE '%directa%'
                 OR modalidad_de_contratacion ILIKE '%régimen especial%'
                 OR modalidad_de_contratacion ILIKE '%regimen especial%' AS es_sin_competencia,
               tipodocproveedor ILIKE '%cédula%'
                 OR tipodocproveedor ILIKE '%cedula%' AS es_persona_natural
        FROM contratos
        WHERE valor_del_contrato IS NOT NULL
          AND valor_del_contrato > 0
          AND fecha_de_firma IS NOT NULL
        """
    )
    n = con.execute("SELECT count(*) FROM contratos").fetchone()[0]
    print(f"Listo: {n:,} contratos en DuckDB ({total:,} descargados).")
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta SECOP II → DuckDB")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--limit", type=int, help="número máximo de filas (muestra)")
    group.add_argument("--full", action="store_true", help="dataset completo")
    group.add_argument("--desde", type=date.fromisoformat, metavar="YYYY-MM-DD",
                       help="todos los contratos firmados desde esta fecha")
    args = parser.parse_args()
    ingest(None if args.full else args.limit, desde=args.desde)


if __name__ == "__main__":
    main()
