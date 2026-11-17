# Guía Técnica de Defensa para Jueces — **Kultiva**

Documento de estudio para el equipo del hackathon. Explica, con base exacta en los datos reales (`data/`) y el motor de simulación (`src/agroshift_engine.py`, `server.py`, `static/app.js`), **de dónde salen los números de Kultiva, qué ocurre con cada decisión del agricultor y qué fórmulas calculan los 3 escenarios a 3 años**.

---

## 0. Arquitectura en 30 segundos (para abrir el pitch)

1. **Frontend móvil (`static/index.html`, `static/app.js`)**: Asistente de 6 pasos con mapa satelital Leaflet + polígonos Turf.js + capa térmica NASA GIBS WMTS y gráficas Chart.js.
2. **Backend FastAPI (`server.py`)**: Expone `/api/init` (catálogos e histórico 2016–2026) y `POST /api/simulate` (validación Pydantic `SimulateRequest` y orquestación).
3. **Motor agronómico-climático (`src/agroshift_engine.py`)**: Cruza climatología histórica NASA + perfil edáfico real/editado + catálogo económico-agronómico de cultivos para simular **6 ciclos (3 años)** bajo 3 estrategias comparables:
   - **Plan Actual**: Monocultivo del cultivo base del usuario.
   - **Plan Conservación Hídrica**: Mantiene el cultivo base en Año 1 y rota en Años 2–3 minimizando demanda de agua.
   - **Plan Regenerativo**: Mantiene el cultivo base en Año 1 y maximiza leguminosas fijadoras de nitrógeno + cobertura vegetal continua en Años 2–3.

> **Clave geoespacial:** Todas las fuentes satelitales y de suelo se unen mediante una llave única **`location_id`**: `UAAAN_La_Narro`, `Los_Lirios_Arteaga` y `General_Cepeda`.

---

## 1. Inventario Real de Bases de Datos

El proyecto conserva **6 archivos fuente/crudos en la raíz** (más scripts ETL) y **16 archivos procesados dentro de `data/processed/`** (13 CSV y 3 JSON; la carpeta `data/` solo contiene `data/processed/`).

### 1.1 Fuentes originales y orígenes NASA

| Archivo crudo (raíz) | Fuente científica | Cobertura espacial / Resolución | Periodo exacto | Filas |
|---|---|---|---|---|
| `nasa_power_la_narro.csv` | NASA POWER (`MERRA-2` + `GPM/IMERG` + `CERES SYN1deg`) | Lat `25.3413`, Lon `-101.0295` · Celda `0.5° × 0.625°` (~50 km), elev. celda `1611.58 m` | `2016-01-01` a `2026-11-14` (con `-999` en días sin cierre al final) | 3,971 |
| `nasa_power_los_lirios.csv` | NASA POWER (`MERRA-2` + `GPM/IMERG` + `CERES SYN1deg`) | Lat `25.3929`, Lon `-100.5929` · Celda `0.5° × 0.625°`, elev. celda `1626.96 m` | `2016-01-01` a `2026-11-14` | 3,971 |
| `nasa_power_general_cepeda.csv` | NASA POWER (`MERRA-2` + `GPM/IMERG` + `CERES SYN1deg`) | Lat `25.3736`, Lon `-101.4863` · Celda `0.5° × 0.625°`, elev. celda `1611.58 m` | `2016-01-01` a `2026-11-14` | 3,971 |
| `coahuila-ndvi-MOD13Q1-061-results.csv` | NASA LP DAAC **MODIS `MOD13Q1 v061`** (Terra/Aqua) | Tile `h08v06` · **250 m** por píxel, compuesto cada **16 días** (La Narro, Los Lirios, General Cepeda) | `2015-12-19` a `2026-10-16` | 750 (250/sitio) |
| `suelos_coahuila.csv` | Caracterización edáfica local de Coahuila | 3 zonas agrícolas de referencia | Catálogo estático | 3 |
| `cultivos_coahuila.csv` | Catálogo agronómico regional | Coahuila (Primavera-Verano, Otoño-Invierno y Perenne) | Catálogo estático | 6 |
| *(Capa web en vivo)* | **NASA GIBS WMTS** (`MODIS_Terra_Land_Surface_Temp_Day`) | Mapa térmico global sobre Esri World Imagery (`maxNativeZoom: 7`) | Snapshot `2026-05-15` | Tiles |

### 1.2 Inventario completo en `data/processed/` (16 archivos)

#### A. Series climáticas NASA POWER procesadas (`clean_nasa_power*.py`)
Se eliminan filas vacías (`-999`), se interpolan huecos cortos (`<= 3 días`) en `ALLSKY_SFC_SW_DWN` e `IMERG_PRECTOT` y se calculan variables agronómicas diarias:
- `temp_range = T2M_MAX - T2M_MIN`
- `gdd_base10 = max(0, ((T2M_MAX + T2M_MIN) / 2) - 10)` (Grados-día base 10 °C)
- `soil_moisture_avg = (GWETTOP + GWETROOT) / 2` (promedio humedad superficial 0–5 cm y zona raíz 0–100 cm, escala 0 a 1)
- `frost_risk = 1` si `T2M_MIN <= 2.0 °C`
- `pest_risk = 1` (agregado en `build_agroshift_master.py`) si `20.0 <= T2M <= 32.0 °C` y `RH2M >= 65.0%`

Archivos generados:
1. `nasa_power_la_narro_clean.csv` — 3,969 filas diarias (`2016-01-01` a `2026-11-12`), 23 columnas, `UAAAN_La_Narro`.
2. `nasa_power_los_lirios_clean.csv` — 3,969 filas diarias (`2016-01-01` a `2026-11-12`), 23 columnas, `Los_Lirios_Arteaga`.
3. `nasa_power_general_cepeda_clean.csv` — 3,969 filas diarias (`2016-01-01` a `2026-11-12`), 23 columnas, `General_Cepeda`.
4. `nasa_power_la_narro_monthly.csv` — 131 filas mensuales (`2016-01` a `2026-11`), 13 columnas.
5. `nasa_power_los_lirios_monthly.csv` — 131 filas mensuales (`2016-01` a `2026-11`), 13 columnas.
6. `nasa_power_general_cepeda_monthly.csv` — 131 filas mensuales (`2016-01` a `2026-11`), 13 columnas.
7. **`nasa_power_coahuila_daily.csv`** — Consolidado diario de los 3 sitios: **11,907 filas** (`2016-01-01` a `2026-11-12`), **24 columnas** (incluye `pest_risk`).
8. **`nasa_power_coahuila_monthly.csv`** — Consolidado mensual: **393 filas** (131 meses × 3 sitios), **14 columnas** (incluye `pest_risk_days`).

> **Valores reales de ejemplo (`nasa_power_coahuila_daily.csv`):**
> - Día 1 (`2016-01-01`, `UAAAN_La_Narro`): `T2M = 9.6 °C`, `T2M_MAX = 14.15 °C`, `T2M_MIN = 7.34 °C`, `RH2M = 83.21%`, `GWETTOP = 0.27`, `GWETROOT = 0.46`, `WS2M = 2.49 m/s`, `ALLSKY_SFC_SW_DWN = 6.07 MJ/m²/día`, `IMERG_PRECTOT = 0.38 mm`, `PRECTOTCORR = 1.89 mm`.
> - Día 1 (`2016-01-01`, `Los_Lirios_Arteaga`): `T2M = 7.7 °C`, `T2M_MAX = 11.4 °C`, `T2M_MIN = 5.73 °C`, `RH2M = 90.55%`, `GWETTOP = 0.43`, `GWETROOT = 0.45`, `PRECTOTCORR = 2.82 mm`.

#### B. Series satelitales de verdor MODIS NDVI procesadas (`clean_modis_ndvi.py`)
Filtra píxeles con nubes (`Mixed_Clouds == "Yes"` o `MODLAND_Description == "Pixel produced, but most probably cloudy"`) o valores fuera de `[-0.2, 1.0]` (**solo 4 de 750 registros** tuvieron contaminación por nubes), interpola por tiempo (`limit=2`) y calcula anomalía mensual (`ndvi_clean - promedio_historico_del_mes`):
9. **`modis_ndvi_coahuila_clean.csv`** — **750 filas** (cada 16 días, `2015-12-19` a `2026-10-16`), **14 columnas**: `location_id`, `date`, `year`, `month`, `season`, `Latitude`, `Longitude`, `ndvi_raw`, `ndvi_clean`, `ndvi_rolling_3`, `ndvi_anomaly`, `vegetation_cover_state`, `qa_status`, `is_cloud_contaminated`.
   - *Ejemplo real:* `General_Cepeda` el `2015-12-19` → `ndvi_raw = 0.2926`, `ndvi_anomaly = +0.0287`, estado `Vegetacion_Escasa_o_Estres`. `UAAAN_La_Narro` el `2026-10-16` → `ndvi_raw = 0.571`, `ndvi_rolling_3 = 0.5544`, estado `Vigor_Vegetal_Alto`.
10. **`modis_ndvi_coahuila_monthly.csv`** — **393 filas mensuales** (`2015-12` a `2026-10`, 131 meses × 3 sitios), **7 columnas**: `location_id`, `year`, `month`, `ndvi_mean`, `ndvi_min`, `ndvi_max`, `ndvi_anomaly_mean`.

#### C. Suelos y cultivos limpios (`prepare_suelos_coahuila.py`, `prepare_cultivos_catalog.py`)
11 y 12. **`suelos_coahuila_clean.csv` y `.json`** — **3 filas**, **22 columnas/campos**. Resumen exacto:

| `location_id` | Municipio | Lat / Lon (suelo) | Altitud local | Tipo / Textura | % MO | Pendiente | Retención / Erosión (score) | Banderas automáticas |
|---|---|---|---|---|---|---|---|---|
| `UAAAN_La_Narro` | Saltillo | `25.34, -101.01` | `1,760 msnm` | Xerosol Cálcico · Franco Arcilloso | `1.4%` | `2.5%` | Media (`2`) / Media (`2`) | `needs_nitrogen_fixation=1`, `needs_erosion_cover=0`, `high_drought_vulnerability=0` |
| `Los_Lirios_Arteaga` | Arteaga | `25.39, -100.58` | `2,280 msnm` | Feozem Lúvico · Franco Limoso | `2.8%` | `6.5%` | Alta (`3`) / Alta (`3`) | `needs_nitrogen_fixation=0`, `needs_erosion_cover=1`, `high_drought_vulnerability=0` |
| `General_Cepeda` | General Cepeda | `25.39, -101.45` | `1,470 msnm` | Regosol Calcárico · Franco Arenoso | `0.9%` | `1.8%` | Baja (`1`) / Alta (`3`) | `needs_nitrogen_fixation=1`, `needs_erosion_cover=1`, `high_drought_vulnerability=1` |

13 y 14. **`cultivos_coahuila_clean.csv` y `.json`** — **6 cultivos**, **26 campos**:

| Cultivo (`cultivo`) | Ciclo | Agua (mm) | Temp °C | Helada (°C) | Raíz (cm) | Fija N | Control erosión / Seq. / Hel. (1–4) | Rend. (t/ha) × Precio ($/t) | Costo/ha | Neto base/ha |
|---|---|---|---|---|---|---|---|---|---|---|
| **Maíz Grano** | P-V | `550` | `10–35` | `2.0` | `90` | No (`0`) | `1` / `2` / `1` | `4.5 × $6,200 = $27,900` | `$16,500` | `$11,400` |
| **Frijol Pinto** | P-V | `350` | `12–32` | `2.0` | `60` | Sí (`1`) | `2` / `2` / `1` | `1.4 × $21,000 = $29,400` | `$14,000` | `$15,400` |
| **Avena Forrajera** | O-I | `280` | `2–26` | `0.0` | `70` | No (`0`) | `3` / `3` / `3` | `18.0 × $1,450 = $26,100` | `$11,500` | `$14,600` |
| **Sorgo Forrajero** | P-V | `380` | `15–38` | `2.0` | `140` | No (`0`) | `2` / `4` / `1` | `22.0 × $1,250 = $27,500` | `$12,000` | `$15,500` |
| **Alfalfa** | Todo el año | `750` | `0–34` | `0.0` | `200` | Sí (`1`) | `4` / `2` / `3` | `28.0 × $1,850 = $51,800` | `$24,000` | `$27,800` |
| **Cebada Forrajera** | O-I | `260` | `0–25` | `-2.0` | `65` | No (`0`) | `3` / `3` / `4` | `16.5 × $1,400 = $23,100` | `$10,800` | `$12,300` |

*(Además, el motor incluye en código `Barbecho_Suelo_Desnudo` con consumo `0 mm` y costo de rastreo/limpia de `-$1,200 MXN/ha`, y 3 perfiles personalizados `__otro__`: ver Sección 2).*

#### D. Datasets maestros fusionados (los que alimentan la app en producción)
15. **`agroshift_parcelas_monthly.csv`** — Unión interna (`inner merge`) por `["location_id", "year", "month"]` entre NASA POWER mensual y MODIS mensual + suelos.
    - **Filas:** **390** (130 meses × 3 zonas), **40 columnas**.
    - **Rango exacto:** **`2016-01` a `2026-10`** (se descartan `2015-12` porque NASA POWER inicia en ene-2016 y `2026-11` porque MODIS llega a oct-2026).
    - **Alerta mensual calculada:** `bare_soil_or_stress_alert = 1` si `ndvi_mean < 0.25` **o** `ndvi_anomaly_mean < -0.05`.
    - *Ejemplo real (`UAAAN_La_Narro`, `2026-10`):* `t2m_mean = 18.46 °C`, `t2m_max_mean = 25.15 °C`, `t2m_min_mean = 13.81 °C`, `prectotcorr_sum = 109.54 mm`, `soil_moisture_avg_mean = 0.4263`.
16. **`agroshift_climatology_12m.json`** — Climatología de **12 meses promedio por parcela** (11 años muestreados en ene–oct y 10 en nov–dic) más metadatos de suelo. Resumen anual climatológico real que lee `src/agroshift_engine.py`:

| Zona | Lluvia anual histórica | Temp. media | Humedad suelo media | NDVI medio | Días riesgo helada/año | Días riesgo plaga/año | Meses/año alerta MODIS | Enero / Julio (Lluvia · NDVI) |
|---|---|---|---|---|---|---|---|---|
| `UAAAN_La_Narro` | `337.0 mm` | `19.31 °C` | `0.4165` | `0.3726` | `12.0 días` | `28.9 días` | `2.10 meses` | Ene: `11.8 mm, 0.30` · Jul: `58.5 mm, 0.44` |
| `Los_Lirios_Arteaga` | `498.7 mm` | `18.18 °C` | `0.4547` | `0.4898` | `14.2 días` | `55.3 días` | `2.02 meses` | Ene: `15.8 mm, 0.46` · Jul: `66.4 mm, 0.57` |
| `General_Cepeda` | `337.0 mm` | `19.31 °C` | `0.4165` | `0.2746` | `12.0 días` | `28.9 días` | `5.76 meses` | Ene: `11.8 mm, 0.24` · Jul: `58.5 mm, 0.31` |

> **Observación brillante para responder a jueces técnicos:**
> *¿Por qué `UAAAN_La_Narro` y `General_Cepeda` tienen la misma lluvia anual (`337.0 mm`) y días de helada/plaga (`12.0` / `28.9`)?*
> Porque la malla regional `MERRA-2` de NASA POWER tiene celdas de **`0.5° × 0.625°` (~50 km)** y ambas zonas caen en la misma celda sinóptica (elevación media de celda `1611.58 m`). **Kultiva supera esa limitación** fusionando tres capas finas encima: (1) **MODIS NDVI a 250 m** (verdor real: `0.3726` vs `0.2746` y `2.1` vs `5.76` meses de estrés), (2) **perfil edáfico y altitud local** (`1760 m` Xerosol `1.4% MO` vs `1470 m` Regosol arenoso `0.9% MO`), y (3) la **calibración manual del productor**. Además, cada tarjeta incluye la sección *"¿Qué no ve el satélite?"* advirtiendo esta resolución de ~50 km y 250 m.

---

## 2. Qué pasa con cada opción que elige el agricultor (`Inputs → Efectos`)

### 2.1 Dibujo de parcela y ubicación (Paso 2)
- **Cómo calcula las hectáreas:** Al trazar un polígono o rectángulo en Leaflet (`Leaflet.Draw`), `applyLayerArea` en `static/app.js` mide el área geodésica en m² usando **`turf.area(layer.toGeoJSON())`** (con respaldo `L.GeometryUtil.geodesicArea`), divide entre **`10,000`**, redondea a 1 decimal y aplica límites **`0.5 ha` mínimo** y **`50,000 ha` máximo** (en API el mínimo es `> 0` y el motor usa `max(0.1, hectares)`).
- **Cómo asigna la estación/microclima NASA:** Calcula el centroide del polígono (`layer.getBounds().getCenter()`) y ejecuta `findNearestStation(lat, lon)` minimizando la distancia euclidiana `sqrt((lat_estacion - lat)^2 + (lon_estacion - lon)^2)` contra las 3 zonas calibradas (`UAAAN_La_Narro`, `Los_Lirios_Arteaga`, `General_Cepeda`). Si cambia la zona ganadora, limpia cualquier edición manual previa de suelo (`soilOverride = null`), actualiza la pestaña, la ficha de suelo y la gráfica NASA.
- **Efecto en el motor:** `hectares` escala linealmente la utilidad neta total (`$/ha × ha`), el ahorro de fertilizante (`$/ha × ha`), y el consumo/ahorro total de agua (`mm × 10 × ha = m³`). En la interfaz también escala el texto guía del deslizador de agua (`(wWater / 100) × ha × 7,900,000 L`), pero **al backend solo viajan las ponderaciones normalizadas**.

### 2.2 Suelo y edición manual (`soil_override`)
Cuando el productor edita el suelo manualmente (`is_custom_soil = True`), envía 7 variables al motor (`_apply_soil_override`), acotadas por seguridad:
- `tipo_suelo_label` y `textura_label`
- `water_retention_score` (`1 = Baja`, `2 = Media`, `3 = Alta`)
- `erosion_risk_score` (`1 = Bajo`, `2 = Medio`, `3 = Alto`)
- `materia_organica_pct` (`0.1%` a `10.0%`)
- `local_elevation_m` (`500 m` a `3,500 m`)
- `pendiente_pct` (`0.0%` a `30.0%`)

**Auto-detección amigable:** Tanto en JS (`inferSoilScoresFromText`) como en Python (`_apply_soil_override`), si el usuario cambia el tipo/textura a palabras como `"aren..." / "regosol"` asigna retención `1` y erosión `3`; `"arcill..." / "vertisol"` retención `3` y erosión `1`; `"feozem" / "negra" / "aluvial"` retención `3`; `"limo"` erosión `3`.

**Efectos exactos de cada variable del suelo en las fórmulas:**
1. **`water_retention_score` (`1, 2, 3`)**:
   - Cambia la **evaporación cuando el suelo queda desnudo**: en invierno `195 / 165 / 135 mm`; en verano `315 / 275 / 235 mm`; en alfalfa perenne `115 / 95 / 75 mm`.
   - Sube el **crédito de humedad por cobertura completa**: `45 + 12 × water_retention_score` (`57 / 69 / 81 mm`).
   - Sube la **esponja de agua del suelo (`soil_buffer_mm`)**: multiplica la humedad satelital por `(590 + 135 × water_retention_score + ajuste_MO)`.
   - Si vale `1`, activa `high_drought_vulnerability = 1`, sumando `+10.0` puntos al índice de estrés por sequía.
2. **`materia_organica_pct` (% MO)**:
   - Si `MO < 1.5%`, activa `needs_nitrogen_fixation = 1` (otorga `+6.0` a `nitrogen_score` a planes con `>= 2` ciclos fijadores de N); si `MO < 1.0%`, activa `high_drought_vulnerability = 1`.
   - En suelo personalizado (`is_custom_soil`), agrega un ajuste hídrico: `(MO - 1.5) × 18 mm` dentro del amortiguador de suelo.
   - Si `MO < 1.5%` y el usuario eligió fertilización `"ninguno"`, activa penalización progresiva de rendimiento en el Plan Actual (`0.90 → 0.85 → 0.80`).
   - En suelo personalizado con `MO < 1.5%`, un `mo_deficit = 1.5 - MO` da bonos directos tanto a `nitrogen_score` como a `suitability_score` (`+8.5 × déficit` si fija N `>= 2` veces; `-6.0 × déficit` si no fija N).
3. **`pendiente_pct` y `erosion_risk_score`**:
   - Si `pendiente >= 5.0%` o `erosion_risk_score >= 3`, activa `needs_erosion_cover = 1`.
   - En suelo personalizado sin cobertura los 12 meses, suma pérdida por escorrentía: `max(0, pendiente - 3.5) × 6.0 mm/año`.
   - Con labranza convencional + erosión `3` y sin cobertura anual completa, suma `+18.0 mm × factor_calor` de escorrentía y `+5.5` al estrés por sequía.
   - En suelo personalizado con pendiente alta/erosión alta, premia planes sin meses desnudos en `nitrogen_score` y `suitability_score` (hasta `1.15×` del factor de erosión en `plan_regenerativo` vs `-1.2×` si deja suelo desnudo).
4. **`local_elevation_m` (msnm)**:
   - Si `altitud >= 2,000 msnm`, suma exposición de helada por altitud: `+14.0` si hay barbecho invernal, o `(4 - tolerancia_heladas_OI) × 4.5` si hay cultivo de invierno (la Cebada tolerancia `4` da `0`).
   - En suelo personalizado, cada `100 m` por encima o debajo de la altitud base de la estación (`elev_diff_m / 100`) suma o resta riesgo térmico multiplicado por `3.5` (barbecho) o `max(1.2, (4.5 - tolerancia_OI) × 1.1)`.

### 2.3 Cultivo actual y perfiles personalizados (`__otro__`)
- Si escoge uno de los **6 cultivos del catálogo**, ese cultivo define el **Plan Actual** (los 3 años) y el **Año 1** de los otros dos planes.
- Si elige **"Otro"** (`__otro__`), la app detecta palabras clave del nombre (ej. `papa, manzana, nuez, nogal, tomate, chile...` → `alto`; `trigo, girasol, garbanzo, soya...` → `medio`; `zacate, mijo, nopal, maguey, agave...` → `bajo`) o usa el selector manual con estos parámetros internos (`Primavera-Verano`):
  - **Consumo Alto (`alto`)**: `700 mm`, tolerancias `1/1/1`, helada `2.0 °C`, `18 t/ha × $6,500 - $85,000 = $32,000 MXN/ha`.
  - **Consumo Medio (`medio`)**: `450 mm`, tolerancias `2/2/2`, helada `1.0 °C`, `4 t/ha × $6,000 - $13,000 = $11,000 MXN/ha`.
  - **Consumo Bajo (`bajo`)**: `300 mm`, tolerancias `3/2/3`, helada `0.5 °C`, `16 t/ha × $1,350 - $10,500 = $11,100 MXN/ha`.

### 2.4 Fertilizantes (4 opciones exactas en Paso 4)
Cada opción modifica **tres mecanismos distintos** en `_evaluate_year`:

| Opción (`fertilizer_type`) | Amortiguamiento de agua en suelo | Costo extra por dependencia sintética *(solo `plan_actual`)* | Ahorro por fijación de N *(solo planes con rotación, por ciclo fijador)* | Bono residual en verano si hubo leguminosa previa (`carryover`) | Efecto extra |
|---|---|---|---|---|---|
| **`quimico`** (*Urea / DAP*) | `+0 mm` | Si 0 fijaciones o monocultivo repetido: **`$1,600 + $900 × años_consec`** (`$1,600` Año 1, `$2,500` Año 2, `$3,400` Año 3/ha) | **`+$3,200 / ha`** | **`+$2,600 / ha`** | Mayor ahorro económico al rotar con Frijol/Alfalfa |
| **`mixto`** (*Químico + Orgánico*) | **`+12 mm`** | En Año 2 y 3 de monocultivo: **`$750 × años_consec`** (`$0` Año 1, `$750` Año 2, `$1,500` Año 3/ha) | **`+$2,100 / ha`** | **`+$1,800 / ha`** | Balance nutricional e hídrico intermedio |
| **`organico`** (*Composta / Biofert.*) | **`+26 mm`** | `$0` | **`+$1,400 / ha`** | **`+$1,500 / ha`** | Máxima retención física de humedad edáfica |
| **`ninguno`** (*Sin fertilización*) | `+0 mm` | `$0` | **`+$2,200 / ha`** *(valor equivalente de N aportado)* | **`+$1,900 / ha`** | Si `MO < 1.5%` en `plan_actual`: castiga rendimiento **`× 0.90`** (Año 1), **`× 0.85`** (Año 2), **`× 0.80`** (Año 3) |

### 2.5 Manejo de rastrojo (`tillage_mode`), Régimen hídrico (`irrigation_mode`) y Destino (`market_goal`)
- **Rastrojo (`conservacion` vs `convencional`)**:
  - Dejar rastrojo (`conservacion`) reduce **16%** la evaporación en suelo desnudo (`× 0.84`), aporta **`+22 mm`** de crédito por cobertura (ponderado a `×0.5` en alfalfa y `×0.6` si solo hay un ciclo), suma **`+24 mm`** al amortiguador del suelo y reduce en **`-3.5`** puntos el índice de sequía.
  - Labranza convencional (`convencional`) con `erosion_risk_score >= 3` añade **`+18 mm`** de pérdida por escorrentía si hay suelo desnudo, suma **`+5.5`** puntos al índice de sequía y resta `-5.0` puntos a `nitrogen_score` en planes con barbecho.
- **Régimen de agua (`temporal` vs `riego`)**:
  - `riego` (riego de auxilio) añade **`+135 mm/año`** a la oferta hídrica disponible y suaviza las pérdidas de rendimiento por sequía (`0.94` amarillo / `0.82` rojo vs `0.88` amarillo / `0.68` rojo en temporal).
  - `temporal` además aplica `high_demand_temporal_penalty` a cultivos que exigen `>= 500 mm` (Maíz `550 mm`, Alfalfa `750 mm` o personalizado alto `700 mm`) cuando hay sequía simulada, ola de calor o Alfalfa perenne.
- **Destino (`grano` vs `forraje`)**: No altera precios ni toneladas del catálogo, sino el **`market_alignment_bonus`** en la calificación final (`suitability_score`): `forraje` suma `(proporción_forrajera - 0.35) × 12.0` (hasta `+7.8` si todo es forraje o `-4.2` si es puro grano); `grano` suma **`+2.0`** si el plan tiene `>= 2` cultivos de grano (`Maiz_Grano` o `Frijol_Pinto`).

### 2.6 Problemas seleccionados (1 a 4 checkboxes en Paso 4)
El usuario debe mantener al menos 1 activo (`sequia`, `suelo`, `plagas`, `heladas`). Actúan en **dos niveles**:

1. **Ajuste de pesos antes de re-normalizar (`simulate_scenarios`):**
   - Si marca **`sequia`**: suma **`+0.18`** a `weight_water`.
   - Si marca **`suelo`**: suma **`+0.18`** a `weight_nitrogen`.
   - Luego divide `(w_water, w_profit, w_nitrogen)` entre su suma para que vuelvan a sumar **`1.0` (100%)**.
   - *(Importante: `plagas` y `heladas` **no** alteran los pesos de los 3 sliders, sino el bono directo de idoneidad).*

2. **Bono o castigo directo al puntaje final (`concern_alignment_bonus`):**
   - **`sequia`**: `+4.2` al Plan Conservación Hídrica, `+1.8` al Plan Regenerativo, `-3.0` al Plan Actual.
   - **`suelo`**: `+4.8` al Plan Regenerativo, `+2.0` al Plan Conservación Hídrica, `-3.5` al Plan Actual.
   - **`plagas`**: Si `semaforo_plagas == VERDE`, suma `+3.8` al Plan Regenerativo y `+3.2` a los demás; si es `ROJO`, resta `-4.0`.
   - **`heladas`**: Si `semaforo_heladas == VERDE` y `0` meses de suelo desnudo, suma `+3.8`; si solo tiene `0` meses desnudos (sin verde), suma `+2.0`; si deja meses desnudos, resta `-3.0`.
   - **Factor multi-selección:** Si hay **2 o más problemas** marcados simultáneamente, el `concern_alignment_bonus` acumulado se multiplica por **`0.75`** para evitar que la suma sature artificialmente la escala a 100.

### 2.7 Simulador Climático ("What-If": reducción de lluvia y ola de calor)
En interfaz permite `-0% a -30%` de lluvia (botón rápido `-20%`) y `+0.0 a +3.0 °C` (botón rápido `+2.0 °C`; el API acepta hasta `-80%` de lluvia):
- **Lluvia ajustada:** `Lluvia_simulada = Lluvia_histórica × (1 - %_reducción_lluvia)`
- **Humedad de suelo satélite ajustada:** `Humedad_suelo_sim = Humedad_histórica × (1 - 0.45 × %_reducción_lluvia) × max(0.75, 1 - 0.035 × ΔT)`
  *(pierde 45% proporcional a la sequía y 3.5% adicional por cada +1 °C, con piso 0.75)*
- **Evapotranspiración / Demanda de agua:** `Factor_calor = 1 + 0.06 × ΔT` (**+6% más consumo de agua** y evaporación por cada `+1.0 °C`).
- **Presión de plagas:** `Días_plaga_año = Días_históricos × (1 + 0.12 × ΔT)` (**+12% más días con riesgo** térmico-húmedo por cada `+1.0 °C`).
- **Estrés térmico y heladas:** Suma `+4.5 × ΔT` al índice de sequía; eleva la temperatura mínima en `+ΔT` y reduce el puntaje de helada en `-2.5 × ΔT`. En `temporal`, cultivos de `>= 500 mm` sufren además `6.0 × (%_sequía / 0.20 + 0.5 × ΔT)` puntos extra en sequía (y `12.0 + ese término` si es Alfalfa perenne).

---

## 3. Fórmulas paso a paso del Escenario Base y los 3 Planes a 3 Años

### Cómo se arman los 3 planes (`_build_rotation_templates`)
Define cobertura invernal primaria según altitud: **`Cebada_Forrajera`** en `Los_Lirios_Arteaga` (alta resistencia a heladas) y **`Avena_Forrajera`** en el resto (`winter_cover_alt` es la opuesta):
- **`plan_actual`**: 3 años de `current_crop` (en el medio año vacío queda `Barbecho_Suelo_Desnudo`, salvo `Alfalfa` que ocupa ambos ciclos).
- **`plan_conservacion_hidrica`**: Año 1 conserva `current_crop` (acompañado en el otro ciclo de `winter_cover_primary`, o `Sorgo_Forrajero` si el cultivo base es O-I). Años 2 y 3 alternan cultivos de bajo consumo hídrico: `Sorgo_Forrajero (380 mm)` / `Frijol_Pinto (350 mm)` en P-V y `Cebada_Forrajera (260 mm)` / `winter_cover_primary` en O-I.
- **`plan_regenerativo`**: Año 1 conserva `current_crop` + `winter_cover_primary` (o `Frijol_Pinto` si el base es O-I). En Años 2–3 prioriza leguminosas (`Frijol_Pinto` y `Alfalfa`) y cobertura continua; **excepción inteligente:** en `General_Cepeda` (zona hiperárida, retención baja), en lugar de meter Alfalfa (`750 mm`) en Año 3 o Maíz, sustituye por `Sorgo_Forrajero + Avena_Forrajera` o `Frijol_Pinto`.

---

### 3.1 Consumo y Ahorro de Agua (`m³` y `L`)

Para cada año (`1, 2, 3`), primero se ajusta la demanda bruta de cada cultivo multiplicando su `consumo_agua_mm` por `(1 + 0.06 × ΔT)` *(en Alfalfa perenne se divide 60% en P-V y 40% en O-I)*. Luego la **demanda hídrica efectiva (`mm/ha`)** se calcula según la cobertura:

1. **Con cobertura completa (P-V + O-I distintos de Alfalfa):**
   `Demanda_efectiva = Agua_PV + Agua_OI - Lluvia_invernal_capturada - Crédito_acolchado + Pérdida_escorrentía`
   - donde `Lluvia_invernal_capturada = mínimo(0.72 × Agua_OI, 0.85 × Lluvia_OI_simulada)`
   - y `Crédito_acolchado = 45 + (12 × Retención_suelo) + (22 si es Rastrojo conservación)`
2. **Solo cultivo Primavera-Verano + Barbecho desnudo en Invierno:**
   `Demanda_efectiva = Agua_PV + Evaporación_barbecho_invernal - (0.6 × Bono_rastrojo) + Pérdida_escorrentía`
   - donde `Evaporación_barbecho_invernal = (195 / 165 / 135 mm según Retención 1/2/3) × Factor_calor × (0.84 si es Rastrojo conservación)`
3. **Solo cultivo Otoño-Invierno + Barbecho desnudo en Verano:**
   `Demanda_efectiva = Evaporación_barbecho_verano + Agua_OI - Lluvia_capturada_OI - (0.6 × Bono_rastrojo) + Pérdida_escorrentía`
   - donde `Evaporación_barbecho_verano = (315 / 275 / 235 mm) × Factor_calor × (0.84 si es Rastrojo conservación)`
4. **Alfalfa perenne (todo el año):**
   `Demanda_efectiva = Agua_PV + Agua_OI + Recargo_transpiración(115 / 95 / 75 × Factor_calor) - Lluvia_capturada_OI(máx 45% de Agua_OI o 70% lluvia OI) - (0.5 × Bono_rastrojo) + Pérdida_escorrentía`

La **`Pérdida_escorrentía`** suma `22 × años_consecutivos_monocultivo × Factor_calor`, más `18 × Factor_calor` si hay labranza convencional con erosión `3` sin cobertura anual, más `(pendiente - 3.5) × 6` si el suelo es personalizado sin cobertura completa.

**Conversión física a 3 años (`1 mm de lámina en 1 ha = 10 m³ = 10,000 litros`):**
- `Demanda_3_años_mm = Suma(Demanda_efectiva de Año 1 + Año 2 + Año 3)`
- `Consumo_agua_total_m3 = Demanda_3_años_mm × 10 × Hectáreas`
- `Consumo_agua_litros = Consumo_agua_total_m3 × 1,000`
- `Ahorro_agua_m3 = (Demanda_3_años_Plan_Actual - Demanda_3_años_Plan) × 10 × Hectáreas`

---

### 3.2 Nivel de Riesgo (Semáforos `VERDE`, `AMARILLO`, `ROJO`)

Cada año recibe sus 3 semáforos y el **semáforo a 3 años del plan toma el peor de los 3 años** (si algún año da `ROJO`, el plan queda en `ROJO`; si no y alguno da `AMARILLO`, queda en `AMARILLO`; si los 3 años dan `VERDE`, queda en `VERDE`):

#### A. Semáforo de Sequía (`drought_stress_index`)
1. `Oferta_agua_mm = Lluvia_anual_simulada + Esponja_suelo_mm + (135 mm si Riego de Auxilio)`
   - donde `Esponja_suelo_mm = Humedad_suelo_sim × (590 + 135 × Retención + Ajuste_MO) + Bono_fert_orgánico(26 o 12) + Bono_rastrojo(24 o 0)`
2. `Índice_sequía = (Demanda_efectiva / máx(200, Oferta_agua_mm)) × 100 - (Tolerancia_sequía_cultivo - 2.0) × 14 + Penalización_vulnerabilidad_suelo + (2.5 × años_monocultivo) + (4.5 × ΔT) + Penalización_alta_demanda_temporal`
3. **Umbrales:** **`VERDE`** `< 84.0` · **`AMARILLO`** `84.0 a 105.9` · **`ROJO`** `>= 106.0`.

#### B. Semáforo de Heladas (`frost_risk_score`)
`Puntaje_helada = máx(0, Días_helada_OI × (3.6 - 0.78 × Tol_helada_OI) + Días_helada_PV × (7.0 - 1.4 × Tol_helada_PV) + Penalización_altitud_>=2000m + Ajuste_diferencia_altitud_manual + máx(0, Umbral_helada_OI - (Temp_min_OI - 4.0)) × 2.5 - 2.5 × ΔT)`
- **Umbrales:** **`VERDE`** `< 22.0` · **`AMARILLO`** `22.0 a 37.9` · **`ROJO`** `>= 38.0`.

#### C. Semáforo de Plagas (`effective_pest_days`)
- Monocultivo consecutivo: **`× 1.35` en Año 2** (+35%) y **`× 1.70` en Año 3** (+70%).
- Sin monocultivo repetido: **`× 0.62`** si hay cobertura anual completa + leguminosa fijadora de N; **`× 0.70`** si solo hay cobertura completa; **`× 1.00`** si hay barbecho.
- `Días_plaga_efectivos = Días_plaga_históricos × (1 + 0.12 × ΔT) × Multiplicador_rotación`
- **Umbrales:** **`VERDE`** `< 30.0` días · **`AMARILLO`** `30.0 a 44.9` días · **`ROJO`** `>= 45.0` días.

*(Nota sobre la gráfica de Paso 5 en `static/app.js`: las franjas rosas sombreadas en la gráfica marcan visualmente meses donde `lluvia < 20 mm` **o** `NDVI < 0.34`; mientras que el conteo histórico del motor usa la columna ETL `bare_soil_or_stress_alert`, que marca `ndvi_mean < 0.25` o anomalía `< -0.05`).*

---

### 3.3 Ganancia Neta e Ingresos (`$ MXN`)

Para cada año del plan:
1. `Utilidad_base_ha = Neto_PV + Neto_OI` *(si es Alfalfa perenne, se toma una sola vez `$27,800/ha`; si hay barbecho, suma `-$1,200/ha` de rastreo)*.
2. **Multiplicador combinado de rendimiento (`combined_yield_factor`)** = multiplicación de 5 factores:
   - `Mult_sequía`: en `temporal` `1.00` (Verde), `0.88` (Amarillo), `0.68` (Rojo); en `riego` `1.00`, `0.94`, `0.82`.
   - `Factor_hídrico_continuo`: `acotado[0.75 a 1.03]` de `1.0 - máx(0, Índice_sequía - 65.0) × 0.0025` *(afina gradualmente el rendimiento incluso antes de cambiar de color el semáforo)*.
   - `Mult_helada`: `1.00` (Verde), `0.93` (Amarillo), `0.78` (Rojo).
   - `Mult_plaga`: `1.00` (Verde), `0.94` (Amarillo), `0.82` (Rojo).
   - `Mult_agotamiento`: `1.00` salvo si `fertilizante = ninguno`, `MO < 1.5%` y `plan_actual` (`0.90`, `0.85`, `0.80`, piso `0.76`).
3. `Utilidad_neta_año_ha = (Utilidad_base_ha × Factor_rendimiento_combinado) + Ahorro_fertilizante_N_ha - Costo_extra_sintético_ha`
4. **Total a 3 años:** `Utilidad_neta_total_MXN = Suma(Utilidad_neta_año_ha de los 3 años) × Hectáreas`.

---

### 3.4 Balance de Nitrógeno y Salud del Suelo (`nitrogen_soil_score`, 5 a 100)

Cada plan acumula en 3 años (36 meses / 6 ciclos):
- `Meses_suelo_protegido` (`0 a 36`) y `Meses_suelo_desnudo` (`36 - cubiertos`).
- `Ciclos_fijación_N` (`0 a 6`; cada ciclo de Frijol Pinto aporta `1` y cada año de Alfalfa aporta `1`).

La fórmula del sub-puntaje de salud de suelo (`5 a 100`) es:
`Nitrogen_Soil_Score = Mín(52, Ciclos_N × 24) + (Meses_protegidos / 36) × 42 + Bono_necesidad_suelo`
- donde `Bono_necesidad_suelo` suma `+6.0` si el suelo necesita N y el plan fija `>= 2` veces; añade o resta según déficit de MO (`< 1.5%`) y pendiente/erosión en suelo personalizado, y suma `+3.5` o resta `-5.0` si hay labranza convencional con erosión `3`.

---

### 3.5 Puntaje de Idoneidad (`suitability_score`, 5 a 100) y Recomendación

El motor evalúa 3 sub-puntajes de 0–100 (con piso de `5.0` y techo de `100.0`):

1. **`water_score`**:
   `100 - máx(0, Promedio_3a_Índice_sequía - 55.0) × 1.05 + Bono_ahorro_agua[-10 a +28] + Bono_semáforo_sequía(+14 Verde, 0 Amarillo, -18 Rojo)`
   *(donde `Bono_ahorro_agua = (Ahorro_mm_vs_actual / 650.0) × 28.0`, acotado entre `-10` y `+28`)*.
2. **`profit_score`**:
   `(Utilidad_neta_3a_por_ha / 92,000 MXN) × 100 - Penalización_plagas(8 Rojo / 3 Amarillo / 0 Verde) - Penalización_heladas(8 Rojo / 3 Amarillo / 0 Verde)`
3. **`nitrogen_soil_score`**: Explicado en 3.4.

**Fórmula final de `suitability_score` (acotada de `5.0` a `100.0`):**
`Suitability = (w_agua × water_score) + (w_dinero × profit_score) + (w_suelo × nitrogen_soil_score) + Bono_mercado(grano/forraje) + Ajuste_urgencia_suelo_custom + Bono_problemas_seleccionados(concerns)`

- El motor ordena los 3 planes de mayor a menor `suitability_score` y designa **`ranked[0]` como `recommended_plan_id`**.
- **Detalle visual en Paso 6 (`static/app.js`):** Excluye al `plan_actual` (que ya se mostró en Paso 5) y ordena las dos rotaciones **de menor a mayor afinidad** para mostrar arriba la *"Primera alternativa"* y abajo la tarjeta destacada como **"Mejor opción"** (el plan óptimo).

---

## 4. Ejemplo Real Verificado (caso base listo para citar)

Simulación ejecutada directamente en el motor con el caso por defecto: **`UAAAN_La_Narro` (Saltillo)**, **`10 ha`**, **`Maiz_Grano`**, **`Solo Temporal`**, **`Químico`**, **`Labranza convencional`**, problema **`sequia`**, prioridades **`33% / 33% / 34%`**, clima histórico (`0%` sequía, `+0.0 °C`):

| Plan (3 años) | Utilidad neta total (10 ha) | Consumo agua (3 años) | Ahorro agua vs actual | Ahorro fertilizante N | Semáforos (Seq · Hel · Pla) | Sub-puntajes (`W / P / N`) | **`suitability_score`** |
|---|---|---|---|---|---|---|---|
| **Plan Actual** *(Monocultivo Maíz + Barbecho)* | **`$101,012 MXN`** | `221,100 m³` | `0 m³` | `$0` | **ROJO · AMARILLO · ROJO** | `25.8 / 5.0 / 21.0` | **`17.61%`** |
| **Plan Conservación Hídrica** *(Año 1 Maíz+Avena → Sorgo/Cebada → Frijol/Avena)* | **`$826,258 MXN`** *(+$725k extra)* | `152,520 m³` | **`68,580 m³`** *(68.58 M litros)* | **`$32,000 MXN`** | **AMARILLO · VERDE · VERDE** | `100.0 / 89.8 / 66.0` | **`93.55%` (Recomendado)** |
| **Plan Regenerativo** *(Año 1 Maíz+Avena → Frijol/Cebada → Alfalfa)* | **`$720,768 MXN`** *(+$620k extra)* | `180,090 m³` | **`41,010 m³`** *(41.01 M litros)* | **`$64,000 MXN`** | **ROJO · VERDE · VERDE** | `66.0 / 78.3 / 96.0` | **`81.89%`** |

> **Por qué gana Conservación Hídrica aquí:** En temporal con solo `337 mm/año` de lluvia, meter Alfalfa (`750 mm`) en el Año 3 dentro del Plan Regenerativo dispara la alerta `ROJA` de sequía y reduce `water_score` a `66.0`. En cambio, si el agricultor cambia a **`Riego de Auxilio`** o marca **`Tierra cansada`** en un suelo pobre con poca materia orgánica, el Plan Regenerativo sube fuertemente al aprovechar los `$64,000 MXN` en fijación de nitrógeno y el máximo `nitrogen_soil_score` (`96.0`).

---

## 5. Preguntas rápidas que suelen hacer los jueces

1. **"¿Es una caja negra o Machine Learning inventado?"**
   No. Es un **motor agronómico determinista y transparente** calibrado sobre **10 años de series satelitales reales de NASA (2016–2026: POWER MERRA-2, GPM IMERG, CERES y MODIS MOD13Q1 250 m)**. El agricultor ve exactamente qué peso tiene cada criterio y por qué cambia la recomendación en tiempo real.
2. **"¿La NASA mide el suelo por debajo o reemplaza un análisis de laboratorio?"**
   No: los satélites miden precipitación, temperatura, radiación, humedad superficial/raíz (`GWETTOP`/`GWETROOT`, resolución ~50 km) y verdor (`NDVI` a 250 m). Por eso integramos perfiles locales reales (`Xerosol`, `Feozem`, `Regosol`), permitimos que el productor edite sus datos de suelo en campo y mostramos en cada plan la sección *"¿Qué no ve el satélite?"* recomendando confirmar pH, salinidad y semilla local.
3. **"¿Por qué en el Año 1 mantienen el cultivo que ya siembra el productor?"**
   Por **viabilidad real de adopción**: pedirle a un productor que tire el cultivo que ya planeó para este ciclo genera rechazo. Mantener su cultivo en el Año 1 con cobertura invernal y hacer la transición escalonada en Años 2 y 3 respeta su liquidez y flujo de caja.
4. **"¿Cómo manejan cultivos que no están en los 6 del catálogo?"**
   Con un clasificador por nivel de demanda hídrica (`alto 700 mm`, `medio 450 mm`, `bajo 300 mm`) y auto-detección de palabras clave (ej. papa, nogal, trigo, nopal) para anclar el Año 1 y comparar contra rotaciones probadas en Coahuila.
