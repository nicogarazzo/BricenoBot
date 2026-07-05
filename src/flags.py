"""Motor de banderas rojas de BricenoBot.

Cada bandera es una consulta SQL sobre la vista contratos_clean que produce
alertas homogéneas. Una bandera roja es una señal estadística que amerita
revisión humana, nunca una acusación.

Uso:
    python -m src.flags
"""
from .db import connect

# Cada consulta debe producir exactamente estas columnas:
# codigo, bandera, nivel, nombre_entidad, nit_entidad,
# proveedor, documento_proveedor, anio, detalle, valor_cop, severidad

FLAGS: dict[str, str] = {
    # F01: mismo comprador + mismo proveedor + muchos contratos sin competencia
    # en el mismo año. Posible fraccionamiento para evadir licitación.
    "F01": """
        SELECT
            'F01' AS codigo,
            'Posible fraccionamiento' AS bandera,
            'contratista' AS nivel,
            any_value(nombre_entidad) AS nombre_entidad,
            nit_entidad,
            any_value(proveedor_adjudicado) AS proveedor,
            documento_proveedor,
            anio,
            count(*) || ' contratos sin competencia con la misma entidad en ' || anio
                || ' que suman $' || round(sum(valor_del_contrato)/1e6)::BIGINT || 'M' AS detalle,
            sum(valor_del_contrato) AS valor_cop,
            25 AS severidad
        FROM contratos_clean
        WHERE es_sin_competencia
        GROUP BY nit_entidad, documento_proveedor, anio
        HAVING count(*) >= 5 AND sum(valor_del_contrato) > 500e6
    """,
    # F02: proveedor cuya facturación anual crece más de 10x frente al año anterior
    "F02": """
        WITH por_anio AS (
            SELECT documento_proveedor,
                   any_value(proveedor_adjudicado) AS proveedor,
                   anio,
                   sum(valor_del_contrato) AS total
            FROM contratos_clean
            GROUP BY documento_proveedor, anio
        )
        SELECT
            'F02' AS codigo,
            'Salto anómalo de facturación' AS bandera,
            'contratista' AS nivel,
            NULL AS nombre_entidad,
            NULL AS nit_entidad,
            a.proveedor,
            a.documento_proveedor,
            a.anio,
            'Facturó $' || round(a.total/1e6)::BIGINT || 'M en ' || a.anio
                || ' vs $' || round(b.total/1e6)::BIGINT || 'M el año anterior ('
                || round(a.total / b.total, 1) || 'x)' AS detalle,
            a.total AS valor_cop,
            20 AS severidad
        FROM por_anio a
        JOIN por_anio b
          ON a.documento_proveedor = b.documento_proveedor AND a.anio = b.anio + 1
        WHERE a.total > 10 * b.total AND a.total > 500e6
    """,
    # F03: pico mensual de contratación de una entidad (>= 3 desviaciones
    # estándar sobre su propia media). Patrón pre-Ley de Garantías / afán de diciembre.
    "F03": """
        WITH mensual AS (
            SELECT nit_entidad, any_value(nombre_entidad) AS nombre_entidad,
                   mes_firma, count(*) AS n, sum(valor_del_contrato) AS total
            FROM contratos_clean
            GROUP BY nit_entidad, mes_firma
        ),
        stats AS (
            SELECT *,
                   avg(n) OVER (PARTITION BY nit_entidad) AS media,
                   stddev_pop(n) OVER (PARTITION BY nit_entidad) AS sd,
                   count(*) OVER (PARTITION BY nit_entidad) AS meses
            FROM mensual
        )
        SELECT
            'F03' AS codigo,
            'Pico anómalo de contratación' AS bandera,
            'entidad' AS nivel,
            nombre_entidad,
            nit_entidad,
            NULL AS proveedor,
            NULL AS documento_proveedor,
            year(mes_firma) AS anio,
            n || ' contratos firmados en ' || strftime(mes_firma, '%Y-%m')
                || ' vs media mensual de ' || round(media, 1)
                || ' (z=' || round((n - media) / sd, 1) || ')' AS detalle,
            total AS valor_cop,
            20 AS severidad
        FROM stats
        WHERE meses >= 4 AND sd > 0 AND n >= 20 AND (n - media) / sd >= 3
    """,
    # F04: concentración de la contratación de una entidad en pocos proveedores (HHI)
    "F04": """
        WITH participacion AS (
            SELECT nit_entidad, any_value(nombre_entidad) AS nombre_entidad, anio,
                   documento_proveedor,
                   sum(valor_del_contrato) AS v_prov,
                   sum(sum(valor_del_contrato)) OVER (PARTITION BY nit_entidad, anio) AS v_total,
                   sum(count(*)) OVER (PARTITION BY nit_entidad, anio) AS n_total
            FROM contratos_clean
            GROUP BY nit_entidad, anio, documento_proveedor
        )
        SELECT
            'F04' AS codigo,
            'Entidad capturada (alta concentración)' AS bandera,
            'entidad' AS nivel,
            any_value(nombre_entidad) AS nombre_entidad,
            nit_entidad,
            NULL AS proveedor,
            NULL AS documento_proveedor,
            anio,
            'HHI ' || round(sum((v_prov / v_total) ** 2), 2)
                || ' con ' || any_value(n_total) || ' contratos por $'
                || round(any_value(v_total)/1e6)::BIGINT || 'M' AS detalle,
            any_value(v_total) AS valor_cop,
            20 AS severidad
        FROM participacion
        GROUP BY nit_entidad, anio
        HAVING sum((v_prov / v_total) ** 2) > 0.5
           AND any_value(n_total) >= 10
           AND any_value(v_total) > 1000e6
    """,
    # F06: persona natural con OPS en 3+ entidades el mismo año (contratista pulpo)
    "F06": """
        SELECT
            'F06' AS codigo,
            'Contratista pulpo (persona natural)' AS bandera,
            'contratista' AS nivel,
            NULL AS nombre_entidad,
            NULL AS nit_entidad,
            any_value(proveedor_adjudicado) AS proveedor,
            documento_proveedor,
            anio,
            count(*) || ' contratos de prestación de servicios con '
                || count(DISTINCT nit_entidad) || ' entidades distintas en ' || anio
                || ' por $' || round(sum(valor_del_contrato)/1e6)::BIGINT || 'M' AS detalle,
            sum(valor_del_contrato) AS valor_cop,
            15 AS severidad
        FROM contratos_clean
        WHERE es_persona_natural
          AND tipo_de_contrato ILIKE '%prestaci%servicios%'
        GROUP BY documento_proveedor, anio
        HAVING count(DISTINCT nit_entidad) >= 3 AND count(*) >= 4
    """,
    # F08: entidad que adjudica casi todo sin competencia
    "F08": """
        SELECT
            'F08' AS codigo,
            'Contratación sin competencia dominante' AS bandera,
            'entidad' AS nivel,
            any_value(nombre_entidad) AS nombre_entidad,
            nit_entidad,
            NULL AS proveedor,
            NULL AS documento_proveedor,
            anio,
            round(100 * sum(CASE WHEN es_sin_competencia THEN valor_del_contrato ELSE 0 END)
                / sum(valor_del_contrato))::BIGINT || '% del valor adjudicado sin competencia ('
                || count(*) || ' contratos, $' || round(sum(valor_del_contrato)/1e6)::BIGINT || 'M)' AS detalle,
            sum(CASE WHEN es_sin_competencia THEN valor_del_contrato ELSE 0 END) AS valor_cop,
            15 AS severidad
        FROM contratos_clean
        GROUP BY nit_entidad, anio
        HAVING count(*) >= 50
           AND sum(valor_del_contrato) > 2000e6
           AND sum(CASE WHEN es_sin_competencia THEN valor_del_contrato ELSE 0 END)
               / sum(valor_del_contrato) > 0.8
    """,
    # F09: contrato de alto valor con objeto difuso
    "F09": """
        SELECT
            'F09' AS codigo,
            'Objeto difuso de alto valor' AS bandera,
            'contrato' AS nivel,
            nombre_entidad,
            nit_entidad,
            proveedor_adjudicado AS proveedor,
            documento_proveedor,
            anio,
            'Contrato ' || id_contrato || ' por $' || round(valor_del_contrato/1e6)::BIGINT
                || 'M con objeto genérico: '
                || left(objeto_del_contrato, 120) AS detalle,
            valor_del_contrato AS valor_cop,
            10 AS severidad
        FROM contratos_clean
        WHERE valor_del_contrato > 1000e6
          AND (objeto_del_contrato ILIKE '%apoyo a la gestión%'
               OR objeto_del_contrato ILIKE '%apoyo a la gestion%'
               OR objeto_del_contrato ILIKE '%fortalecimiento institucional%'
               OR objeto_del_contrato ILIKE '%actividades de apoyo%')
    """,
    # F10: contrato con adiciones de tiempo excesivas
    "F10": """
        SELECT
            'F10' AS codigo,
            'Adición de tiempo excesiva' AS bandera,
            'contrato' AS nivel,
            nombre_entidad,
            nit_entidad,
            proveedor_adjudicado AS proveedor,
            documento_proveedor,
            anio,
            'Contrato ' || id_contrato || ' con ' || dias_adicionados
                || ' días adicionados sobre plazo original de '
                || datediff('day', fecha_de_inicio_del_contrato, fecha_de_fin_del_contrato)
                || ' días ($' || round(valor_del_contrato/1e6)::BIGINT || 'M)' AS detalle,
            valor_del_contrato AS valor_cop,
            10 AS severidad
        FROM contratos_clean
        WHERE dias_adicionados >= 180
          AND valor_del_contrato > 200e6
    """,
}


def run() -> None:
    con = connect()
    union = "\nUNION ALL BY NAME\n".join(f"({q})" for q in FLAGS.values())
    con.execute(f"CREATE OR REPLACE TABLE alertas AS {union}")

    # Scores 0-100: suma de severidades de las alertas asociadas, con tope
    con.execute(
        """
        CREATE OR REPLACE TABLE scores_entidad AS
        SELECT nit_entidad,
               any_value(nombre_entidad) AS nombre_entidad,
               least(100, sum(severidad)) AS score,
               count(*) AS n_alertas,
               sum(valor_cop) AS valor_bajo_alerta,
               list(DISTINCT codigo) AS banderas
        FROM alertas
        WHERE nit_entidad IS NOT NULL
        GROUP BY nit_entidad
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE scores_contratista AS
        SELECT documento_proveedor,
               any_value(proveedor) AS proveedor,
               least(100, sum(severidad)) AS score,
               count(*) AS n_alertas,
               sum(valor_cop) AS valor_bajo_alerta,
               list(DISTINCT codigo) AS banderas
        FROM alertas
        WHERE documento_proveedor IS NOT NULL
        GROUP BY documento_proveedor
        """
    )

    print("Resumen de alertas por bandera:")
    for cod, band, n, v in con.execute(
        """
        SELECT codigo, any_value(bandera), count(*), round(sum(valor_cop)/1e9, 1)
        FROM alertas GROUP BY codigo ORDER BY codigo
        """
    ).fetchall():
        print(f"  {cod}  {band:<45} {n:>6,} alertas  ${v:,.1f} mil millones")
    total = con.execute("SELECT count(*) FROM alertas").fetchone()[0]
    print(f"Total: {total:,} alertas generadas.")
    con.close()


if __name__ == "__main__":
    run()
