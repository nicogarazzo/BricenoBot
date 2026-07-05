# BricenoBot

**Dashboard público: https://nicogarazzo.github.io/BricenoBot/**

Radar anticorrupción sobre la contratación pública colombiana. Detecta patrones de irregularidad en SECOP II usando datos abiertos oficiales, banderas rojas codificadas y un dashboard de priorización.

Inspirado en la metodología de veeduría ciudadana de revisión sistemática del SECOP: este proyecto industrializa ese trabajo con cruces masivos de datos y detección estadística.

## Qué hace

- Ingesta contratos y procesos de SECOP II desde la API de datos abiertos (datos.gov.co / Socrata) a una base DuckDB local.
- Ejecuta un motor de banderas rojas (fraccionamiento, concentración, picos pre-Ley de Garantías, contratistas pulpo, adjudicaciones relámpago y más).
- Calcula un score de riesgo 0-100 por contrato, contratista y entidad.
- Presenta todo en un dashboard Streamlit: radar general, feed de alertas, perfiles y vista temporal.
- Produce informes y expedientes reproducibles en [`informes/`](informes/), como [El afán de enero: 486.013 contratos en un mes](informes/2026-01-el-afan-de-enero.md).

## Inicio rápido

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ingesta de una muestra (rápido, para probar)
python -m src.ingest --limit 50000

# Ingesta completa (millones de filas, tarda)
python -m src.ingest --full

# Calcular banderas rojas y scores
python -m src.flags

# Lanzar el dashboard
streamlit run app.py
```

## Estructura

```
DESIGN.md              Diseño completo: taxonomía de irregularidades, fuentes, arquitectura
src/ingest.py          Ingesta SODA API → DuckDB
src/flags.py           Motor de banderas rojas y scoring
src/export_static.py   Exporta agregados a docs/data.js para el sitio público
src/expedientes.py     Expedientes de las alertas más severas para validación manual
src/db.py              Utilidades de base de datos
app.py                 Dashboard Streamlit (exploración local)
informes/              Informes y expedientes generados sobre la base completa
docs/                  Dashboard público estático (GitHub Pages)
data/                  Base DuckDB local (no versionada)
```

Para actualizar el dashboard público tras una nueva ingesta:

```bash
python -m src.flags && python -m src.export_static
git add docs/data.js && git commit -m "Actualizar datos del dashboard" && git push
```

## Fuentes de datos

Todas públicas y oficiales. Principal: [SECOP II Contratos Electrónicos](https://www.datos.gov.co/Estad-sticas-Nacionales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h) y [SECOP II Procesos](https://dev.socrata.com/foundry/www.datos.gov.co/p6dx-8zbt). Ver DESIGN.md para la lista completa (Cuentas Claras, SIGEP, RUES, PACO, Contraloría).

## Nota ética

Una bandera roja es una señal estadística que amerita revisión humana, nunca una acusación. Este proyecto usa exclusivamente datos públicos publicados por el Estado colombiano y su metodología es abierta y auditable.

## Licencia

MIT
