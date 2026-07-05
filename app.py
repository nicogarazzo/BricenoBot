"""BricenoBot: dashboard de radar anticorrupción sobre SECOP II.

Lanzar con:
    streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from src.db import DB_PATH, connect

st.set_page_config(page_title="BricenoBot | Radar Anticorrupción", layout="wide")

DISCLAIMER = (
    "Una bandera roja es una señal estadística que amerita revisión humana, "
    "nunca una acusación. Datos: SECOP II, datos.gov.co (Colombia Compra Eficiente)."
)


@st.cache_resource
def get_con():
    return connect(read_only=True)


def q(sql: str, **params) -> pd.DataFrame:
    return get_con().execute(sql, params or None).fetchdf()


if not DB_PATH.exists():
    st.error(
        "No hay base de datos. Ejecuta primero:\n\n"
        "`python -m src.ingest --limit 200000` y luego `python -m src.flags`"
    )
    st.stop()

st.title("BricenoBot: Radar Anticorrupción")
st.caption(DISCLAIMER)

tab_radar, tab_alertas, tab_entidad, tab_contratista, tab_temporal = st.tabs(
    ["Radar general", "Feed de alertas", "Perfil de entidad", "Perfil de contratista", "Vista temporal"]
)

# ---------------------------------------------------------------- Radar general
with tab_radar:
    kpi = q(
        """
        SELECT count(*) AS contratos,
               sum(valor_del_contrato) AS valor_total,
               sum(CASE WHEN es_sin_competencia THEN valor_del_contrato END) AS valor_directo,
               count(DISTINCT nit_entidad) AS entidades,
               count(DISTINCT documento_proveedor) AS proveedores
        FROM contratos_clean
        """
    ).iloc[0]
    alert_kpi = q("SELECT count(*) AS n, sum(valor_cop) AS v FROM alertas").iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Contratos analizados", f"{int(kpi.contratos):,}")
    c2.metric("Valor total", f"${kpi.valor_total / 1e12:,.1f} billones")
    c3.metric(
        "Sin competencia",
        f"{100 * kpi.valor_directo / kpi.valor_total:.0f}% del valor",
        help="Contratación directa + régimen especial",
    )
    c4.metric("Alertas activas", f"{int(alert_kpi.n):,}", f"${alert_kpi.v / 1e12:,.1f} billones bajo alerta")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Entidades con mayor riesgo")
        df = q(
            """
            SELECT nombre_entidad AS Entidad, score AS Score, n_alertas AS Alertas,
                   round(valor_bajo_alerta/1e9, 1) AS "Valor bajo alerta (mil M)"
            FROM scores_entidad ORDER BY score DESC, valor_bajo_alerta DESC LIMIT 15
            """
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    with col_b:
        st.subheader("Contratistas con mayor riesgo")
        df = q(
            """
            SELECT proveedor AS Contratista, score AS Score, n_alertas AS Alertas,
                   round(valor_bajo_alerta/1e9, 1) AS "Valor bajo alerta (mil M)"
            FROM scores_contratista ORDER BY score DESC, valor_bajo_alerta DESC LIMIT 15
            """
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Valor bajo alerta por departamento")
    df = q(
        """
        SELECT c.departamento, sum(a.valor_cop)/1e9 AS valor
        FROM alertas a JOIN (SELECT DISTINCT nit_entidad, departamento FROM contratos_clean) c
          ON a.nit_entidad = c.nit_entidad
        GROUP BY 1 ORDER BY 2 DESC LIMIT 20
        """
    )
    st.plotly_chart(
        px.bar(df, x="valor", y="departamento", orientation="h",
               labels={"valor": "Miles de millones COP", "departamento": ""}),
        use_container_width=True,
    )

# ---------------------------------------------------------------- Feed de alertas
with tab_alertas:
    st.subheader("Qué investigar hoy")
    codigos = q("SELECT DISTINCT codigo || ': ' || bandera AS b FROM alertas ORDER BY 1")["b"].tolist()
    sel = st.multiselect("Filtrar por bandera", codigos, default=codigos)
    sel_codes = [s.split(":")[0] for s in sel] or ["-"]
    df = q(
        f"""
        SELECT codigo AS Código, bandera AS Bandera,
               coalesce(nombre_entidad, '') AS Entidad,
               coalesce(proveedor, '') AS Contratista,
               detalle AS Detalle,
               round(valor_cop/1e6, 1) AS "Valor (M)",
               severidad AS Severidad
        FROM alertas
        WHERE codigo IN ({",".join("'" + c + "'" for c in sel_codes)})
        ORDER BY severidad DESC, valor_cop DESC
        LIMIT 500
        """
    )
    st.dataframe(df, use_container_width=True, hide_index=True, height=600)
    st.download_button(
        "Descargar alertas (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        "alertas_bricenobot.csv",
        "text/csv",
    )

# ---------------------------------------------------------------- Perfil de entidad
with tab_entidad:
    entidades = q(
        "SELECT DISTINCT nombre_entidad FROM contratos_clean ORDER BY 1"
    )["nombre_entidad"].tolist()
    ent = st.selectbox("Entidad", entidades)
    if ent:
        resumen = q(
            """
            SELECT count(*) AS n, sum(valor_del_contrato) AS v,
                   sum(CASE WHEN es_sin_competencia THEN valor_del_contrato END) AS vd,
                   count(DISTINCT documento_proveedor) AS provs
            FROM contratos_clean WHERE nombre_entidad = $ent
            """,
            ent=ent,
        ).iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Contratos", f"{int(resumen.n):,}")
        c2.metric("Valor", f"${resumen.v / 1e9:,.1f} mil M")
        c3.metric("Sin competencia", f"{100 * (resumen.vd or 0) / resumen.v:.0f}%")
        c4.metric("Proveedores distintos", f"{int(resumen.provs):,}")

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Por modalidad")
            df = q(
                """
                SELECT modalidad_de_contratacion AS m, sum(valor_del_contrato)/1e9 AS v
                FROM contratos_clean WHERE nombre_entidad = $ent GROUP BY 1 ORDER BY 2 DESC
                """,
                ent=ent,
            )
            st.plotly_chart(px.pie(df, names="m", values="v", hole=0.4), use_container_width=True)
        with col_b:
            st.subheader("Top contratistas")
            df = q(
                """
                SELECT proveedor_adjudicado AS Contratista, count(*) AS Contratos,
                       round(sum(valor_del_contrato)/1e9, 2) AS "Valor (mil M)"
                FROM contratos_clean WHERE nombre_entidad = $ent
                GROUP BY 1 ORDER BY 3 DESC LIMIT 10
                """,
                ent=ent,
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Alertas de esta entidad")
        df = q(
            """
            SELECT codigo AS Código, bandera AS Bandera, detalle AS Detalle,
                   round(valor_cop/1e6, 1) AS "Valor (M)"
            FROM alertas WHERE nombre_entidad = $ent ORDER BY severidad DESC, valor_cop DESC
            """,
            ent=ent,
        )
        if df.empty:
            st.success("Sin alertas para esta entidad en la muestra actual.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Perfil de contratista
with tab_contratista:
    busqueda = st.text_input("Buscar contratista por nombre o documento")
    if busqueda and len(busqueda) >= 3:
        df = q(
            """
            SELECT proveedor_adjudicado AS Contratista, documento_proveedor AS Documento,
                   count(*) AS Contratos, count(DISTINCT nombre_entidad) AS Entidades,
                   round(sum(valor_del_contrato)/1e6, 1) AS "Valor total (M)",
                   min(fecha_de_firma) AS Desde, max(fecha_de_firma) AS Hasta
            FROM contratos_clean
            WHERE proveedor_adjudicado ILIKE '%' || upper($b) || '%'
               OR documento_proveedor = $b
            GROUP BY 1, 2 ORDER BY 5 DESC LIMIT 50
            """,
            b=busqueda,
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        if len(df) > 0:
            doc = st.selectbox("Ver detalle de", df["Documento"].tolist())
            det = q(
                """
                SELECT fecha_de_firma AS Firma, nombre_entidad AS Entidad,
                       tipo_de_contrato AS Tipo, modalidad_de_contratacion AS Modalidad,
                       round(valor_del_contrato/1e6, 1) AS "Valor (M)",
                       left(objeto_del_contrato, 150) AS Objeto
                FROM contratos_clean WHERE documento_proveedor = $d
                ORDER BY fecha_de_firma DESC
                """,
                d=doc,
            )
            st.dataframe(det, use_container_width=True, hide_index=True)
            alertas = q(
                "SELECT codigo, bandera, detalle FROM alertas WHERE documento_proveedor = $d",
                d=doc,
            )
            if not alertas.empty:
                st.warning(f"{len(alertas)} alertas asociadas a este contratista")
                st.dataframe(alertas, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Vista temporal
with tab_temporal:
    st.subheader("Contratación diaria")
    st.caption(
        "Buscar picos anómalos: cierres de vigencia (diciembre) y el mes previo "
        "a la entrada en vigencia de la Ley de Garantías electorales."
    )
    df = q(
        """
        SELECT fecha_de_firma::date AS dia, count(*) AS contratos,
               sum(valor_del_contrato)/1e9 AS valor
        FROM contratos_clean GROUP BY 1 ORDER BY 1
        """
    )
    metric = st.radio("Métrica", ["contratos", "valor"], horizontal=True)
    fig = px.line(df, x="dia", y=metric,
                  labels={"dia": "", "contratos": "Contratos firmados", "valor": "Miles de millones COP"})
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Por modalidad en el tiempo")
    df = q(
        """
        SELECT mes_firma AS mes, modalidad_de_contratacion AS modalidad,
               sum(valor_del_contrato)/1e9 AS valor
        FROM contratos_clean
        GROUP BY 1, 2
        HAVING sum(valor_del_contrato) > 0
        ORDER BY 1
        """
    )
    top_mods = df.groupby("modalidad")["valor"].sum().nlargest(6).index
    fig = px.bar(df[df["modalidad"].isin(top_mods)], x="mes", y="valor", color="modalidad",
                 labels={"mes": "", "valor": "Miles de millones COP"})
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption("BricenoBot es código abierto (MIT). " + DISCLAIMER)
