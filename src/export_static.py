"""Exporta los agregados del radar a docs/data.js para el dashboard público.

Uso:
    python -m src.export_static
"""
import json
from datetime import date
from pathlib import Path

from .db import connect

DOCS = Path(__file__).resolve().parent.parent / "docs"

DESCRIPCIONES = {
    "F01": "Muchos contratos sin competencia entre la misma entidad y el mismo proveedor en un año. Patrón clásico para evadir umbrales de licitación.",
    "F02": "Proveedor cuya facturación anual con el Estado crece más de 10x frente al año anterior.",
    "F03": "Mes en que una entidad firma contratos muy por encima de su propia media histórica. Patrón pre-Ley de Garantías y afán de diciembre.",
    "F04": "Entidad cuya contratación se concentra en muy pocos proveedores (índice HHI mayor a 0.5).",
    "F06": "Persona natural con contratos de prestación de servicios simultáneos en tres o más entidades.",
    "F08": "Entidad que adjudica más del 80% de su valor por modalidades sin competencia.",
    "F09": "Contrato de más de $1.000M con objeto genérico tipo 'apoyo a la gestión'.",
    "F10": "Contrato con 180 o más días adicionados sobre el plazo original.",
}


def rows(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main() -> None:
    con = connect(read_only=True)

    kpi = rows(con, """
        SELECT count(*)::BIGINT AS contratos,
               sum(valor_del_contrato) AS valor_total,
               round(100 * sum(CASE WHEN es_sin_competencia THEN valor_del_contrato ELSE 0 END)
                     / sum(valor_del_contrato)) AS pct_sin_competencia,
               count(DISTINCT nit_entidad)::BIGINT AS entidades,
               count(DISTINCT documento_proveedor)::BIGINT AS proveedores,
               min(fecha_de_firma)::date::VARCHAR AS desde,
               max(fecha_de_firma)::date::VARCHAR AS hasta
        FROM contratos_clean
    """)[0]
    kpi_alertas = rows(con, "SELECT count(*)::BIGINT AS n, sum(valor_cop) AS v FROM alertas")[0]
    kpi["alertas"] = kpi_alertas["n"]
    kpi["valor_alerta"] = kpi_alertas["v"]

    data = {
        "generado": date.today().isoformat(),
        "kpi": kpi,
        "serie_diaria": rows(con, """
            SELECT fecha_de_firma::date::VARCHAR AS d, count(*)::BIGINT AS n,
                   round(sum(valor_del_contrato)/1e9, 2) AS v
            FROM contratos_clean GROUP BY 1 ORDER BY 1
        """),
        "modalidades": rows(con, """
            SELECT modalidad_de_contratacion AS m, count(*)::BIGINT AS n,
                   round(sum(valor_del_contrato)/1e9, 1) AS v,
                   bool_or(es_sin_competencia) AS sin_comp
            FROM contratos_clean GROUP BY 1 ORDER BY v DESC LIMIT 9
        """),
        "banderas": [
            {**r, "descripcion": DESCRIPCIONES.get(r["codigo"], "")}
            for r in rows(con, """
                SELECT codigo, any_value(bandera) AS bandera, count(*)::BIGINT AS n,
                       round(sum(valor_cop)/1e9, 1) AS v
                FROM alertas GROUP BY codigo ORDER BY codigo
            """)
        ],
        "top_entidades": rows(con, """
            SELECT nombre_entidad AS nombre, score::BIGINT AS score,
                   n_alertas::BIGINT AS alertas, round(valor_bajo_alerta/1e9, 1) AS v
            FROM scores_entidad ORDER BY score DESC, valor_bajo_alerta DESC LIMIT 10
        """),
        "top_contratistas": rows(con, """
            SELECT proveedor AS nombre, score::BIGINT AS score,
                   n_alertas::BIGINT AS alertas, round(valor_bajo_alerta/1e9, 1) AS v
            FROM scores_contratista
            WHERE proveedor IS NOT NULL
            ORDER BY score DESC, valor_bajo_alerta DESC LIMIT 10
        """),
        "departamentos": rows(con, """
            SELECT c.departamento AS d, round(sum(a.valor_cop)/1e9, 1) AS v
            FROM alertas a
            JOIN (SELECT DISTINCT nit_entidad, departamento FROM contratos_clean) c
              ON a.nit_entidad = c.nit_entidad
            WHERE c.departamento IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC LIMIT 12
        """),
        "alertas_top": rows(con, """
            SELECT codigo, bandera, coalesce(nombre_entidad, '') AS entidad,
                   coalesce(proveedor, '') AS contratista,
                   detalle, round(valor_cop/1e9, 2) AS v
            FROM alertas ORDER BY severidad DESC, valor_cop DESC LIMIT 12
        """),
    }

    DOCS.mkdir(exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, default=str)
    (DOCS / "data.js").write_text(f"window.DATA = {payload};\n", encoding="utf-8")
    print(f"Exportado docs/data.js ({len(payload):,} bytes)")
    con.close()


if __name__ == "__main__":
    main()
