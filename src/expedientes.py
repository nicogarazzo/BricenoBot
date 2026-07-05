"""Genera expedientes de las alertas más severas para validación manual.

Cada expediente toma una alerta de la tabla `alertas` y adjunta los contratos
subyacentes (id_contrato, proceso_de_compra, fechas, valores, objeto) para que
un humano pueda verificarla contra SECOP II antes de sacar cualquier conclusión.

Uso:
    python -m src.expedientes            # top 15 por severidad y valor
    python -m src.expedientes --top 30
"""
import argparse
from datetime import date
from pathlib import Path

from .db import connect

INFORMES = Path(__file__).resolve().parent.parent / "informes"

AVISO = (
    "> **Aviso metodológico.** Un expediente es una señal estadística, no una acusación. "
    "Los patrones aquí descritos pueden tener explicaciones legítimas (competencias legales, "
    "urgencias justificadas, estructuras de contratación propias de la entidad). Todo hallazgo "
    "debe verificarse contra el expediente oficial en SECOP II usando el `id_contrato` y el "
    "`proceso_de_compra` incluidos, y debe tratarse como presunto hasta que un órgano de "
    "control o una investigación periodística lo confirme.\n"
)


def rows(con, sql, params=None):
    cur = con.execute(sql, params or {})
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def contratos_de(con, alerta) -> list[dict]:
    """Contratos subyacentes de una alerta, según su tipo de agrupación."""
    conds, params = [], {}
    if alerta["nit_entidad"]:
        conds.append("nit_entidad = $nit")
        params["nit"] = alerta["nit_entidad"]
    if alerta["documento_proveedor"]:
        conds.append("documento_proveedor = $doc")
        params["doc"] = alerta["documento_proveedor"]
    if alerta["anio"] and alerta["codigo"] not in ("F06",):
        conds.append("anio = $anio")
        params["anio"] = int(alerta["anio"])
    where = " AND ".join(conds) or "1=1"
    return rows(con, f"""
        SELECT id_contrato, proceso_de_compra, fecha_de_firma::date AS firma,
               nombre_entidad, proveedor_adjudicado,
               modalidad_de_contratacion AS modalidad,
               round(valor_del_contrato/1e6)::BIGINT AS millones,
               dias_adicionados,
               left(objeto_del_contrato, 160) AS objeto
        FROM contratos_clean
        WHERE {where}
        ORDER BY valor_del_contrato DESC
        LIMIT 10
    """, params)


def fmt_contrato(c) -> str:
    extra = f" · +{int(c['dias_adicionados'])} días" if c.get("dias_adicionados") else ""
    objeto = (c["objeto"] or "").replace("\n", " ").strip()
    return (
        f"| `{c['id_contrato']}` | `{c['proceso_de_compra']}` | {c['firma']} | "
        f"{c['modalidad']} | ${c['millones']:,} M{extra} | {objeto} |"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Expedientes de alertas top")
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    con = connect(read_only=True)
    alertas = rows(con, """
        SELECT codigo, bandera, nombre_entidad, nit_entidad, proveedor,
               documento_proveedor, anio, detalle, valor_cop, severidad
        FROM alertas
        ORDER BY severidad DESC, valor_cop DESC
        LIMIT $n
    """, {"n": args.top})

    out = [
        f"# Expedientes: las {args.top} alertas más severas",
        "",
        f"Generado el {date.today().isoformat()} sobre la base completa "
        "(2018-08-07 a 2026-07-01, 5.101.581 contratos, 42.335 alertas).",
        "",
        AVISO,
    ]

    for i, a in enumerate(alertas, 1):
        partes = [p for p in (a["nombre_entidad"], a["proveedor"]) if p]
        quien = " → ".join(partes)
        out += [
            f"## Expediente {i:02d} · {a['codigo']} · {a['bandera']}",
            "",
            f"**Sujeto:** {quien}" + (f" (año {int(a['anio'])})" if a["anio"] else ""),
            "",
            f"**Señal:** {a['detalle']}",
            "",
            f"**Valor bajo alerta:** ${round(a['valor_cop']/1e6):,.0f} millones COP · "
            f"severidad {int(a['severidad'])}/100",
            "",
            "**Contratos subyacentes (top 10 por valor):**",
            "",
            "| id_contrato | proceso | firma | modalidad | valor | objeto |",
            "|---|---|---|---|---|---|",
        ]
        out += [fmt_contrato(c) for c in contratos_de(con, a)]
        out.append("")

    INFORMES.mkdir(exist_ok=True)
    path = INFORMES / "expedientes-top.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"Generado {path} ({len(alertas)} expedientes)")
    con.close()


if __name__ == "__main__":
    main()
