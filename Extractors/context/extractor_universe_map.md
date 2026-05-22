# XTS Extractor Universe Map
> Fecha: 2026-04-06 | Mapeo completo de fuentes de datos, capacidades actuales y oportunidades

---

## 1. CENACE (Mexico) — Centro Nacional de Control de Energía

### 1A. API Pública — PML (Precios Marginales Locales)
- **URL:** `https://ws01.cenace.gob.mx:8082/SWPML/SIM/{sistema}/{proceso}/{nodos}/{dates}/JSON`
- **Auth:** Ninguna (público)
- **Sistemas:** SIN (101 zonas), BCA (4 zonas), BCS (3 zonas)
- **Procesos:** MDA (Día Adelanto), MTR (Tiempo Real)
- **Datos extraídos:** PZ/PML, ENE (energía), PER (pérdidas), CNG (congestión)
- **Límites:** Máx 7 días/request, máx 20 nodos/request
- **Status:** ✅ Activo — 108 zonas de carga

### 1B. API Pública — Demanda (NO EXTRAÍDO)
- **SWDEMAM:** `https://ws01.cenace.gob.mx:8082/SWDEMAM/SIM/{sistema}/{proceso}/{zonas}/{dates}/JSON`
  - Pronóstico de demanda MDA por zona
- **SWDEMREAL:** `https://ws01.cenace.gob.mx:8082/SWDEMREAL/SIM/{sistema}/{zonas}/{dates}/JSON`
  - Demanda real por zona
- **Status:** ❌ No se extrae — Alto valor para modelos de load forecasting

### 1C. API Pública — Otros Web Services Disponibles (NO EXTRAÍDOS)
- **SWPRECAM** — Precios de subastas MDA (auction clearing prices)
- **SWESTAC** — Estado de unidades generadoras (disponibilidad operativa)
- **Generación por tecnología** — Solar, eólica, hidro, térmica
- **Precios de servicios conexos** — Regulación, reservas
- **Capacidad de transferencia enlaces internacionales** — BCA↔CAISO, SIN↔Guatemala
- **Resultados importación/exportación comercial** — Flujos reales transfronterizos
- **Déficit y excedente BCA** — Si BCA importa o exporta y cuánto
- **Status:** ❌ Ninguno extraído — Referencia: https://www.cenace.gob.mx/Paginas/SIM/

### 1D. SOAP Privado — ECDs (Estados de Cuenta Diarios)
- **WSDL:** `https://ws01.cenace.gob.mx:8081/WSDownLoadEdoCta/EdoCuentaService.svc?singleWsdl`
- **Auth:** Usuario/contraseña por sistema (eCuenta/Dropbox)
- **Subcuentas BCA:** ERO, ITJ, ETJ, IRO
- **Subcuentas SIN:** ERD, ELA, EGT, IGT
- **Formato:** ZIP con CSVs (base64), contiene facturas y reliquidaciones
- **Status:** ✅ Activo — Descarga + parseo automático

### 1E. Portal SIM — Reportes Web (NO EXTRAÍDO)
- **URL:** https://www.cenace.gob.mx/Paginas/SIM/Reportes/
- Reportes de precios, generación, demanda en formato descargable
- Potencial para scraping si las APIs no cubren toda la información
- **Status:** ❌ Solo consulta manual

---

## 2. ERCOT (Texas) — Electric Reliability Council of Texas

### 2A. API Pública — Public Reports
- **URL:** `https://api.ercot.com/api/public-reports`
- **Auth:** OAuth 2.0 B2C (Azure AD) + Subscription Key
- **Paginación:** Soportada, size=1000

#### Reportes Actualmente Extraídos:
| Report ID | Endpoint | Datos | Granularidad | Status |
|-----------|----------|-------|-------------|--------|
| NP4-190-CD | dam_stlmnt_pnt_prices | DA Prices (DC_L, DC_R) | Horaria | ✅ |
| NP6-905-CD | spp_node_zone_hub | RT Prices (DC_L, DC_R) | 15-min → horaria | ✅ |
| NP6-345-CD | act_sys_load_by_wzn | System Load | Horaria | ✅ |
| NP4-732-CD | wpp_hrly_avrg_actl_fcast | Wind Generation | Horaria | ✅ |
| NP4-745-CD | spp_hrly_actual_fcast_geo | Solar Generation | Horaria | ⚠️ Código existe, no conectado |

#### Reportes de Alto Valor NO Extraídos:
| Report ID | Datos | Valor para Trading |
|-----------|-------|--------------------|
| NP3-233-CD | Fuel mix por tipo (gas, carbón, eólica, solar, nuclear) | Entender drivers de precio |
| NP6-86-CD | Ancillary Services (Reg Up/Down, RRS, ECRS) | Correlación con precios energía |
| NP6-788-CD | ORDC prices (scarcity pricing adder) | Predecir spikes RT |
| NP6-970-CD | Binding transmission constraints | Oportunidades de congestión |
| NP3-566-CD | Load forecast (7 días adelanto) | Accuracy de pronósticos |
| NP4-183-CD | Outage schedules (unidades generadoras) | Impacto supply/precio |
| NP4-188-CD | Wind/Solar forecast vs actual | Error de pronóstico → volatilidad RT |

### 2B. MarginalUnit — Pronósticos Sintéticos
- **URL:** `https://api1.marginalunit.com/pr-forecast`
- **Auth:** Basic Auth
- **Datasets:** lmp_da, lmp_rt para DC_L, DC_R
- **Horizonte:** 48 horas
- **Status:** ✅ Activo

### 2C. Enverus Mosaic — Fallback + Catálogo Completo
- **URL:** `https://api-mosaic-prod.enverus.com/mosaic-api`
- **Auth:** Basic Auth (ENVERUS_USER, ENVERUS_PASS)
- **Endpoints:** `GET /datasets` (catálogo), `GET /timeseries/{dataset}` (datos), `GET /{dataset}/entities` (entidades)
- **ISOs cubiertos:** ERCOT, CAISO, y potencialmente PJM, SPP, MISO, NYISO
- **Status:** ⚠️ Solo se usa como fallback para 2 datasets ERCOT

#### Uso Actual (mínimo):
| Dataset | Datos | Status |
|---------|-------|--------|
| ercot-price-pnode-iso_actual_da_peakwd | DA peak weekday prices | ⚠️ Solo fallback |
| ercot-price-pnode-iso_actual_rt | RT actual prices | ⚠️ Solo fallback |

#### Catálogo Completo — Datasets Disponibles NO Usados:

**Precios (100+ variantes):**
- `iso_actual_da_lmp`, `iso_actual_rt_lmp` — Precios LMP completos
- `iso_actual_da_peakwd/peakwe/offpeak` — Precios por período
- `env_composite_da_lmp`, `env_composite_rt_lmp` — Pronósticos ML-enhanced
- `env_forecast_da_lmp_25p/75p` — Bandas de incertidumbre probabilísticas
- `iso_forecast_da`, `iso_forecast_2d`, `iso_forecast_7d` — Forward 2-7 días

**Generación y Renovables:**
- `iso_actual_fuel_mix` — Fuel mix real (gas, carbón, nuclear, eólica, solar, hidro, batería)
- `iso_forecast_hourly_wind_generation` — Pronóstico eólico horario
- `iso_forecast_combined_wind_and_solar` — Pronóstico renovable combinado
- `env_forecast_generation_stpf` — Spatio-Temporal Point Forecast
- `iso_actual_total_state_charge_*` — Estado de carga baterías

**Load y Demanda:**
- `iso_actual_load`, `env_composite_load` — Carga real + ML forecast
- `env_forecast_load` — Pronóstico de carga ML

**Servicios Conexos y Reservas:**
- `iso_actual_ancillary_service*` — Regulación, reservas, spinning
- `iso_actual_operating_reserves` — Márgenes de reserva

**Outages y Restricciones (MUY VALIOSO para trading):**
- `iso_actual_dispatchable_outages` — Outages de unidades
- `iso_actual_renewable_outages` — Curtailment renovable
- `iso_scheduled_hourly_resource_outage_capacity` — Mantenimiento programado
- `iso_forecast_cop_hsl` — Congestion, Outages, Pricing por nodo
- `iso_actual_tie_flows` — Flujos inter-área (revela congestión)

**Weather (Drivers):**
- `env_actual_wind_speed`, `env_forecast_wind_speed_stpf` — Viento
- `env_actual_ghi`, `env_forecast_ghi_stpf` — Irradiación solar (GHI)
- `env_actual_temperature`, `env_composite_temperature` — Temperatura
- `env_similar_days_forecast` — Patrones de días similares

**Datos Sub-Horarios:**
- `iso_actual_5min`, `iso_forecast_5min` — Mercado 5-minutos
- `iso_actual_15min` — Intervalos de 15 minutos

**Entity Types:** geographical_region, system_wide, hub, hub_pnode, pnode, load_zone, tac_area, as_region, generator, weather_zone, dc_tie_flow_regions

**Formatos:** `csv_wide` (columnar), `json`, `csv_long`

**Referencia:** [Enverus Mosaic API](https://www.enverus.com/blog/level-up-your-trading-workflows-with-mosaic-api/), [Data Catalog](https://www.enverus.com/data-catalog/)

---

## 3. CAISO (California) — California Independent System Operator

### 3A. OASIS API
- **URL:** `https://oasis.caiso.com/oasisapi/SingleZip`
- **Auth:** Ninguna (público)
- **Formato:** XML dentro de ZIP
- **Nodos actuales:** ROA-230_2_N101 (Rosarito), TJI-230_2_N101 (Tijuana)

#### Queries Actualmente Extraídos:
| Query | Market | Datos | Status |
|-------|--------|-------|--------|
| PRC_LMP | DAM | DA LMP Prices | ✅ |
| PRC_RTPD_LMP | RTPD | FMM 15-min Prices | ✅ |
| SLD_FCST | DAM | Load Forecast | ✅ |
| SLD_REN_FCST | DAM | Solar Forecast | ✅ |

#### Catálogo Completo OASIS — Queries Disponibles NO Extraídos:

**Precios (PRC_):**
| Query | Datos | Valor para Trading |
|-------|-------|--------------------|
| PRC_HASP_LMP | Hour-Ahead Scheduling Process LMP | Precio real-time más preciso que FMM |
| PRC_INTVL_LMP | Interval LMP (5-minute market) | Datos sub-horarios para trading intradía |
| PRC_AS | Ancillary Services (Spin, Non-Spin, Reg Up/Down) | Costo total de servir carga, revenue stacking |
| PRC_CNSTR | Constraint Shadow Prices | Valor de congestión en restricciones |
| PRC_RTM_SCH_CNSTR | RT Market Scheduling Constraint Shadow Prices | Congestión real-time |
| PRC_FLEX_RAMP | Flexible Ramp Pricing | Precio de rampa/flexibilidad |
| PRC_FUEL | Fuel-based pricing | Componente combustible en precio |

**Demanda y Pronósticos (SLD_):**
| Query | Datos | Valor |
|-------|-------|-------|
| SLD_REN_FCST (wind) | Wind Forecast (misma query, filtro diferente) | Completar renovables |
| SLD_ADV_FCST | Advisory CAISO Demand Forecast | Pronóstico avanzado |
| SLD_FCST_PEAK | Peak System Load Forecast | Picos de demanda |
| SLD_SF_EVAL_DMD_FCST | Sufficiency Evaluation Demand Forecast | Evaluación suficiencia |

**Energía y Recursos (ENE_):**
| Query | Datos | Valor |
|-------|-------|-------|
| ENE_SLRS | Scheduled Load and Resources | Balance programado |
| ENE_FLEX_RAMP_REQT | Flexible Ramp Requirements | Requerimientos flexibilidad |
| ENE_AGGR_FLEX_RAMP | Flex Ramp Aggregated Awards | Premios flexibilidad |
| ENE_UNCERTAINTY_MV | Uncertainty Movement by Category | Movimientos de incertidumbre |
| ENE_HRLY_BASE_NSI | EIM BAA Hourly Base NSI | Net Scheduled Interchange |

**Servicios Conexos (AS_):**
| Query | Datos | Valor |
|-------|-------|-------|
| AS_REQ | Ancillary Services Requirements | Requerimientos por tipo |
| AS_OP_RSRV | Operating Reserve | Reservas operativas |

**Referencia (ATL_):**
| Query | Datos | Uso |
|-------|-------|-----|
| ATL_PNODE | Pricing Node Map/Attributes | Catálogo de nodos |
| ATL_SP | Scheduling Point Definition | Puntos de programación |
| ATL_BAA_TIE | BAA and Tie Definition | Definición de interconexiones |
| ATL_PRC_CORR_MSG | Price Correction Messages | Correcciones de precio |

**Datos Públicos de Ofertas (PUB_):**
| Query | Datos | Valor |
|-------|-------|-------|
| PUB_DAM_GRP | Public Bid Data (Day-Ahead) | Ofertas del mercado DA |
| PUB_RTM_GRP | Public Bid Data (Real-Time) | Ofertas del mercado RT |

**Market Run IDs disponibles:** DAM, HASP, RTPD, RTD/RTM, 2DA, ACTUAL

**Referencia:** [OASIS API Spec v3.04](https://www.caiso.com/documents/oasisapispecification.pdf), [Interface Spec v5.1.2](https://www.caiso.com/Documents/OASIS-InterfaceSpecification_v5_1_2Clean_Fall2017Release.pdf)

### 3B. CENACE BCA para nodos frontera
- **Nodos:** 07IVY-230 (Imperial Valley), 07OMS-230 (Otay Mesa)
- **Integrado en:** caiso_api.py
- **Status:** ✅ Activo

---

## 4. Guatemala — AMM (Administrador del Mercado Mayorista)

### 4A. Descarga de Excel — Despacho Diario
- **URL:** `https://www.amm.org.gt/pdfs2/programas_despacho/01_PROGRAMAS_DE_DESPACHO_DIARIO/{year}/{MM}_{MES}/WEB{ddmmYYYY}.xlsx`
- **Auth:** Ninguna (público)
- **Sheet actual:** POE (Precio de Oferta de Energía)
- **Status:** ✅ Activo — Solo POE

#### Sheets Adicionales Disponibles (NO EXTRAÍDOS):
- Despacho de generación por planta
- Pronóstico de demanda
- Costos de combustible
- Niveles de embalse
- Restricciones de transmisión
- Importación/exportación con México (Tapachula)

### 4B. CENACE SIN — Nodo LBR
- **Nodo:** 09LBR-230 (La Blanca, frontera Guatemala)
- **Status:** ✅ Activo

---

## 5. Utilidades y Datos Complementarios

### 5A. Tipo de Cambio (USD/MXN)
| Fuente | URL | Auth | Prioridad |
|--------|-----|------|-----------|
| Banxico SIE | banxico.org.mx/SieAPIRest/service/v1 | Token | Principal |
| Frankfurter | api.frankfurter.app | Ninguna | Fallback 1 |
| Fawazahmed CDN | cdn.jsdelivr.net | Ninguna | Fallback 2 |
- **Serie:** SF43718 (FIX USD/MXN)
- **Status:** ✅ Activo con 3 fallbacks

### 5B. Temperaturas — Open-Meteo
- **URLs:** archive-api.open-meteo.com, api.open-meteo.com
- **Auth:** Ninguna (gratuito)
- **Ciudades:** TIJ, MXL, SND, IVY, NLR, LRD, RYN, MCA, TPC, GTM (10 ciudades)
- **Datos:** temperature_2m horaria
- **Status:** ✅ Activo

#### Datos Meteorológicos Adicionales Disponibles (NO EXTRAÍDOS):
- **windspeed_10m** — Velocidad del viento (input para pronóstico eólico)
- **direct_radiation** — Radiación directa (input para pronóstico solar)
- **diffuse_radiation** — Radiación difusa
- **Ciudades faltantes:** Houston, Dallas, El Paso (zonas climáticas ERCOT), Hermosillo, Monterrey (nodos CENACE relevantes)

### 5C. APIs de Clima Adicionales (NO EXPLORADAS)
- Visual Crossing Weather API
- Tomorrow.io (formerly ClimaCell)
- NOAA/NWS API (gratuita, datos US)
- SMN (Servicio Meteorológico Nacional México)

---

## 6. Resumen Visual — Estado de Extracción

```
CENACE Público
  ├── PML MDA (108 zonas)      ✅ Activo
  ├── PML MTR (108 zonas)      ✅ Activo
  ├── Demanda pronóstico       ❌ No extraído
  ├── Demanda real             ❌ No extraído
  ├── Generación por tipo      ❌ No extraído
  ├── Servicios conexos        ❌ No extraído
  ├── Transferencia enlaces    ❌ No extraído
  ├── Import/Export comercial  ❌ No extraído
  └── Déficit/excedente BCA    ❌ No extraído

CENACE Privado (eCuenta)
  ├── ECD descarga             ✅ Activo
  ├── ECD parseo               ✅ Activo
  └── Otros servicios SOAP     ❓ Por explorar

ERCOT
  ├── DA Prices                ✅ Activo
  ├── RT Prices                ✅ Activo
  ├── Load                     ✅ Activo
  ├── Wind                     ✅ Activo
  ├── Solar                    ⚠️ Código existe, no conectado
  ├── Fuel Mix                 ❌ No extraído
  ├── Ancillary Services       ❌ No extraído
  ├── ORDC / Scarcity          ❌ No extraído
  ├── Constraints              ❌ No extraído
  └── Outages                  ❌ No extraído

CAISO (4 de 25+ queries disponibles)
  ├── DA LMP (PRC_LMP)         ✅ Activo
  ├── FMM LMP (PRC_RTPD_LMP)  ✅ Activo
  ├── Load Forecast (SLD_FCST) ✅ Activo
  ├── Solar Forecast           ✅ Activo
  ├── HASP LMP (PRC_HASP_LMP) ❌ No extraído — RT más preciso
  ├── 5-min LMP (PRC_INTVL)   ❌ No extraído — Sub-horario
  ├── Ancillary Services       ❌ No extraído — Spin, Reg, Non-Spin
  ├── Wind Forecast            ❌ No extraído
  ├── Flex Ramp Pricing        ❌ No extraído
  ├── Constraint Prices        ❌ No extraído
  ├── Scheduled Load/Resources ❌ No extraído
  ├── Public Bid Data          ❌ No extraído
  └── Node Atlas/Reference     ❌ No extraído

Guatemala AMM
  ├── POE precio spot          ✅ Activo
  ├── LBR (CENACE)             ✅ Activo
  ├── Despacho generación      ❌ No extraído
  ├── Demanda                  ❌ No extraído
  └── Import/Export MX         ❌ No extraído

Enverus Mosaic (2 de 100+ datasets disponibles)
  ├── ERCOT DA fallback        ⚠️ Solo fallback
  ├── ERCOT RT fallback        ⚠️ Solo fallback
  ├── Forward curves 2-7d      ❌ No usado — Pronósticos precio
  ├── Fuel mix (por ISO)       ❌ No usado — Drivers de precio
  ├── Ancillary services       ❌ No usado — Revenue stacking
  ├── Outages (plan+emergency) ❌ No usado — Predecir spikes
  ├── Congestion/constraints   ❌ No usado — Spread trading
  ├── Renewable forecasts      ❌ No usado — Eólica + Solar ML
  ├── Tie flows inter-área     ❌ No usado — Congestión transfronteriza
  ├── Operating reserves       ❌ No usado — Márgenes de reserva
  ├── Battery state of charge  ❌ No usado — Storage arbitrage
  ├── Sub-hourly (5/15 min)    ❌ No usado — Trading intradía
  ├── Weather (wind/GHI/temp)  ❌ No usado — Inputs modelos
  ├── Similar days patterns    ❌ No usado — Pattern trading
  ├── ML price bands (25p-75p) ❌ No usado — Incertidumbre
  └── CAISO datasets           ❌ No usado — Multi-ISO

MarginalUnit
  └── Forecasts DA/RT          ✅ Activo

Tipo de Cambio                 ✅ Activo (3 fuentes)
Temperaturas                   ✅ Activo (10 ciudades)
  ├── Viento                   ❌ No extraído
  └── Radiación solar          ❌ No extraído
```

---

## 7. Base de Datos Actual

| Tabla | Base | Granularidad | Columnas Principales |
|-------|------|-------------|---------------------|
| DATOS_ERCOT | XTS | Horaria (24/día) | DA_DCL, DA_DCR, RT_DCL, RT_DCR, LOAD, WIND, forecasts |
| DATOS_CAISO | XTS | Horaria (24/día) | DA_ROA, DA_TJI, FMM_ROA, FMM_TJI, PML_IVY, PML_OMS, LOAD, SOLAR |
| PML.MDA_D | PML | Horaria (24×108/día) | Sistema, Zona_Carga, PZ, PZ_ENE, PZ_PER, PZ_CNG |
| PML.MTR | PML | Horaria (24×108/día) | Sistema, Nodo, PML, PML_ENE, PML_PER, PML_CNG |
| GTM | XTS | Horaria (24/día) | PPOE, LBR |
| Tipo_Cambio | XTS | Diaria | TC |
| TEMPERATURAS | XTS | Horaria | TIJ, MXL, SND, IVY, NLR, LRD, RYN, MCA, TPC, GTM |

## 8. Credenciales y Autenticación

| Fuente | Tipo Auth | Variables de Entorno |
|--------|-----------|---------------------|
| ERCOT API | OAuth 2.0 B2C | ERCOT_USERNAME, ERCOT_PASSWORD, ERCOT_KEY, ERCOT_CLIENT_ID |
| MarginalUnit | Basic Auth | MU_USERNAME, MU_PASSWORD |
| Enverus | Basic Auth | ENVERUS_USER, ENVERUS_PASS |
| CENACE ECD | Basic (SOAP) | Hardcoded ⚠️ (migrar a env vars) |
| Banxico | Token | BANXICO_TOKEN |
| CAISO | Ninguna | — |
| CENACE PML | Ninguna | — |
| Open-Meteo | Ninguna | — |
| AMM Guatemala | Ninguna | — |
| SQL Server | User/Pass | XTS_DB_SERVER, XTS_DB_PORT, XTS_DB_USER, XTS_DB_PASSWORD |

## 9. Problemas Identificados

1. **Credenciales hardcodeadas** en ercot_api.py, ecd_extractor.py, marginalunit_api.py, db_connection.py
2. **Solar ERCOT** — función existe (`get_solar()`) pero no se llama en el extractor
3. **CENACE no integrado** en run_all.py — corre independiente
4. **Upserts fila por fila** — muy lento para backfills (debería ser bulk MERGE)
5. **Logging inconsistente** — mezcla de print() y logging.getLogger()
6. **Sin validación de datos** — no hay checks de rangos, completeness, o duplicados
