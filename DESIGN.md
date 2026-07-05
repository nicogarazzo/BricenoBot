# BricenoBot: Radar Anticorrupción sobre SECOP

Sistema de detección automática de irregularidades en la contratación pública colombiana, inspirado en la metodología de veeduría ciudadana de Daniel Briceño (revisión sistemática de SECOP y cruce con contexto político).

Objetivo: industrializar lo que un veedor hace a mano. Cruces masivos de datos abiertos, detección estadística de patrones anómalos y un dashboard que priorice qué investigar.

---

## 1. Taxonomía de irregularidades

Basada en casos reales documentados públicamente y en patrones conocidos de la contratación pública colombiana.

### A. Irregularidades del proceso de adjudicación

| ID | Patrón | Ejemplo real / señal |
|----|--------|----------------------|
| A1 | Contratación directa abusiva ("a dedo") | 8 de cada 10 contratos del Estado se adjudican sin competencia |
| A2 | Pliegos sastre (requisitos a la medida de un proponente) | Caso Acueducto de Bogotá: reglas modificadas y certificaciones que favorecieron a un proponente en contrato de $161.000 millones |
| A3 | Proponente único o competencia artificial | Licitaciones con un solo oferente real |
| A4 | No publicación o publicación incompleta en SECOP | Propuestas nunca cargadas a la plataforma |
| A5 | Fraccionamiento para evadir umbrales de licitación | Muchos contratos pequeños, mismo objeto, mismo contratista, misma vigencia |
| A6 | Regímenes especiales como bypass | Convenios interadministrativos con universidades, EICE u organismos internacionales para esquivar la Ley 80 |

### B. Perfil sospechoso del contratista

| ID | Patrón |
|----|--------|
| B1 | Empresas recién creadas ganando contratos grandes |
| B2 | Objeto social que no corresponde al objeto del contrato |
| B3 | Concentración: pocos contratistas capturan una entidad |
| B4 | Uniones temporales fachada con integrantes recurrentes |
| B5 | Contratistas con sanciones, multas o inhabilidades que siguen contratando |
| B6 | Vínculos políticos: financiadores de campaña, familiares de funcionarios, puerta giratoria |

### C. Clientelismo y uso político del gasto

| ID | Patrón | Ejemplo real / señal |
|----|--------|----------------------|
| C1 | Nómina paralela vía contratos de prestación de servicios (OPS) | 101.400 OPS firmados el mes previo a la Ley de Garantías por $6 billones |
| C2 | Contratos a influencers y "bodegas" para propaganda oficial | Más de $2.300 millones en creadores de contenido afines al gobierno |
| C3 | Picos de contratación pre-Ley de Garantías y de fin de vigencia | El "afán de diciembre" |
| C4 | Contratos como pago de favores políticos | Activistas y militantes contratados por el Estado |

### D. Irregularidades financieras

| ID | Patrón |
|----|--------|
| D1 | Sobrecostos frente a precios de mercado o de referencia |
| D2 | Adiciones y prórrogas sistemáticas (el contrato nace barato y crece hasta el tope del 50%) |
| D3 | Anticipos altos con ejecución nula o lenta |
| D4 | Objetos difusos: "apoyo a la gestión", "fortalecimiento institucional" |
| D5 | Gasto suntuario |

### E. Irregularidades de ejecución

| ID | Patrón |
|----|--------|
| E1 | Contratos pagados sin ejecución verificable, elefantes blancos |
| E2 | Cesiones de contrato sospechosas (el ganador real aparece después) |
| E3 | Mismo supervisor o interventor en todos los contratos del mismo contratista |
| E4 | Terminaciones anticipadas y liquidaciones anómalas |

---

## 2. Detección avanzada (lo que el bot puede hacer y un humano no alcanza)

### Cruces entre fuentes

1. **Cuentas Claras (CNE) × SECOP**: financiadores de campañas que reciben contratos de la entidad gobernada por el candidato que financiaron.
2. **SIGEP × SECOP**: exfuncionarios contratando con su exentidad antes del periodo de inhabilidad; coincidencias de apellidos y direcciones entre funcionarios y contratistas.
3. **RUES × SECOP**: fecha de matrícula mercantil vs fecha del contrato; cambios recientes de objeto social; representantes legales o direcciones compartidas entre "competidores".
4. **SIRI (Procuraduría) y Responsables Fiscales (Contraloría) × SECOP**: inhabilitados que siguen contratando.

### Detección estadística sobre SECOP puro

5. **Valores justo bajo umbrales**: pico anormal en el histograma de valores justo debajo de la menor o mínima cuantía delata fraccionamiento deliberado.
6. **Ley de Benford** sobre valores contractuales por entidad: desviaciones sugieren cifras fabricadas.
7. **Velocidad de adjudicación**: procesos resueltos en tiempo récord sugieren ganador predefinido.
8. **Perdedores fantasma (bid rigging)**: mismos proponentes que siempre pierden acompañando al mismo ganador; ofertas económicas sospechosamente cercanas.
9. **Superhombres contractuales**: personas naturales con OPS simultáneos en 3+ entidades que exceden capacidad física de dedicación.
10. **Índice HHI de concentración** por entidad: qué tan capturada está una entidad por pocos contratistas.

### NLP y análisis de texto

11. **Objetos contractuales clonados**: similitud de texto entre contratos de distintas entidades o entre pliego y propuesta ganadora.
12. **Detector de vaguedad**: clasificar objetos por especificidad; "apoyo a la gestión" puntúa alto en riesgo.
13. **Metadatos de documentos**: autor o empresa en las propiedades de los archivos del pliego que coincide con el proponente ganador.

### Análisis de redes

14. **Grafo entidad-contratista-representante legal-UT-dirección-contacto**: clústeres donde competidores comparten infraestructura; comunidades de contratistas que rotan entre entidades del mismo grupo político.

### Detección de propaganda pagada

15. **Cruce de contratistas persona natural con perfiles públicos de redes sociales** de alta actividad política.

---

## 3. Fuentes de datos (todas públicas)

| Fuente | Dataset / ID | Qué aporta |
|--------|--------------|-----------|
| datos.gov.co (Socrata) | SECOP II Contratos Electrónicos `jbjy-vk9h` (~5.6M filas, 84 columnas) | El corazón: contratos electrónicos |
| datos.gov.co | SECOP II Procesos de Contratación `p6dx-8zbt` | Proponentes, plazos, modalidad, adjudicación |
| datos.gov.co | SECOP Integrado `rpmr-utcd` | Unifica SECOP I + II + Tienda Virtual |
| datos.gov.co | Multas y sanciones SECOP | Historial disciplinario de contratistas |
| Cuentas Claras (CNE) | Financiación de campañas | Cruce donante-contratista |
| SIGEP | Hojas de vida y declaraciones | Puerta giratoria, nepotismo |
| RUES | Registro mercantil | Edad de empresas, representantes, objetos sociales |
| PACO (portal.paco.gov.co) | Banderas rojas precalculadas | Baseline de comparación |
| Contraloría | Responsables fiscales | Inhabilidades |
| SIA Observa / CHIP | Presupuesto territorial | Contexto de ejecución presupuestal |

API: SODA (Socrata) en `https://www.datos.gov.co/resource/<id>.json`, con paginación por `$limit` / `$offset` y filtros SoQL (`$where`, `$select`, `$group`).

---

## 4. Arquitectura

```
Ingesta diaria (Python + SODA API)
        ↓
Normalización (NITs, nombres de entidades, deduplicación)
        ↓
Motor de reglas: banderas rojas codificadas (taxonomía sección 1 y 2)
        ↓
Scoring 0-100 por contrato, contratista y entidad
        ↓
Dashboard (Streamlit en MVP)
```

Stack MVP: Python 3.11, DuckDB como base analítica local, Streamlit para el dashboard. Migración futura: Postgres + Next.js cuando haya tracción.

Principio de diseño: la normalización de identidades (NITs con y sin dígito de verificación, nombres de entidades con variantes) es el 60% del trabajo real. Todo cruce depende de ella.

---

## 5. Vistas del dashboard

1. **Radar general**: KPIs nacionales, índice de riesgo por departamento y entidad, % contratación directa, valor bajo bandera roja.
2. **Feed de alertas**: banderas rojas recientes priorizadas por score y valor. La vista "qué investigo hoy".
3. **Perfil de entidad**: % por modalidad, HHI, picos temporales, top contratistas, comparación con pares.
4. **Perfil de contratista**: historial cross-entidad, crecimiento de facturación, sanciones, edad de empresa, red de vínculos.
5. **Explorador de red**: grafo interactivo de vínculos.
6. **Vista temporal**: contratación diaria con marcadores de Ley de Garantías, cierres de vigencia y elecciones.
7. **Constructor de casos**: watchlist + expediente exportable con contratos, banderas, vínculos y fuentes.

---

## 6. Banderas rojas del MVP (fase 1)

| Código | Bandera | Lógica |
|--------|---------|--------|
| F01 | Fraccionamiento | Misma entidad + mismo contratista + N contratos de objeto similar en la misma vigencia cuya suma supera el umbral de licitación |
| F02 | Empresa contratando por encima de su historial | Contratista cuyo valor adjudicado en el año crece más de 10x frente a su historial |
| F03 | Pico pre-Ley de Garantías | Entidad con volumen de OPS en el mes previo a la restricción mayor a 3 desviaciones estándar de su media |
| F04 | Concentración de entidad | HHI de contratistas de la entidad por encima del percentil 95 nacional |
| F05 | Valores bajo umbral | Densidad anómala de contratos entre el 90% y el 100% del valor de la menor o mínima cuantía |
| F06 | Contratista pulpo (persona natural) | Persona natural con contratos OPS simultáneos en 3+ entidades |
| F07 | Adjudicación relámpago | Días entre publicación y adjudicación en el percentil 5 inferior para su modalidad |
| F08 | Contratación directa dominante | Entidad con más del 80% del valor contratado por modalidades sin competencia |

Score de riesgo: suma ponderada de banderas activas, normalizada 0-100, calculada a nivel contrato, contratista y entidad.

---

## 7. Roadmap

- **Fase 1 (MVP)**: ingesta SECOP II, banderas F01-F08, dashboard Streamlit con radar, alertas, perfiles y vista temporal.
- **Fase 2**: cruces externos (Cuentas Claras, RUES, SIGEP, sanciones), grafo de vínculos.
- **Fase 3**: NLP (objetos clonados, vaguedad, metadatos de pliegos), Benford, bid rigging.
- **Fase 4**: constructor de casos con expediente exportable, alertas automáticas (correo/Telegram), API pública.

---

## 8. Principios éticos

- Solo datos públicos y abiertos publicados por el propio Estado colombiano.
- Una bandera roja es una señal estadística que amerita revisión humana, nunca una acusación. El lenguaje del sistema siempre es "presunto" e "indicio".
- Metodología transparente y reproducible: todo el código es abierto y las reglas son auditables.
- Sin scraping agresivo: se respetan los términos de las APIs de datos abiertos.
