# Instrucciones para Marco: Infraestructura de Extractores XTS
> Fecha: 2026-04-06 | Ejecutar: 2026-04-07+
> Contexto: Este plan cubre la creación de TODOS los extractores para la plataforma XTS y sus posiciones en la base de datos.

---

## 1. CONTEXTO Y OBJETIVO

Construir una infraestructura completa de extractores que alimente la base de datos XTS con datos de 7 fuentes (CENACE, ERCOT, CAISO, Guatemala AMM, Enverus Mosaic, Enverus Synthetic/MarginalUnit, Open-Meteo/Banxico). El CSV `datasets_completo.csv` tiene 162 datasets marcados como SI.

**Principios:**
- Los datos **fact** (precios settled, generación real, load real) NUNCA se sobreescriben una vez insertados
- Los datos **forecast** se actualizan en cada corrida (se sobreescribe el forecast anterior)
- Los extractores deben ser **extensibles** — poder agregar nodos, zonas, o settlement points sin cambiar código
- Todo debe funcionar primero en **desarrollo local**, luego se migra al **Office Server**

---

## 2. ARQUITECTURA BASE DEL EXTRACTOR

### 2.1 Estructura de Directorio

```
etl/
  base/
    __init__.py
    extractor.py          # BaseExtractor abstract class
    api_client.py          # BaseAPIClient con retry/backoff
    credentials.py         # Centralizado — SOLO env vars, CERO hardcoded
    validators.py          # Validaciones de datos
    db.py                  # Conexión DB + bulk upsert con MERGE
    scheduling.py          # Lógica de fact vs forecast, timing

  cenace/
    api/
      pml_api.py           # PML fetch (zonas + nodos P)
      demand_api.py         # SWDEMAM + SWDEMREAL
      generation_api.py     # Generación por tecnología
      cross_border_api.py   # Capacidad transferencia, import/export, déficit BCA
    ecd/
      ecd_extractor.py      # SOAP download
      ecd_parser.py         # CSV parser
    extractors/
      pml_extractor.py      # Zonas de carga (108) + Nodos P seleccionados
      demand_extractor.py
      generation_extractor.py
      cross_border_extractor.py
    config.py               # Listas de nodos, zonas, sistemas — CONFIGURABLE
    run_cenace.py

  ercot/
    api/
      ercot_api.py          # Existente, extender
      marginalunit_api.py   # Existente
    extractors/
      prices_extractor.py   # DA/RT por settlement point (configurable)
      load_extractor.py     # Load total + por weather zone
      generation_extractor.py  # Wind (system + regiones) + Solar + Fuel mix
      ancillary_extractor.py   # AS prices (REGUP, REGDN, RRS, ECRS, NSRS)
      scarcity_extractor.py    # ORDC
      constraints_extractor.py # Binding constraints
      forecast_error_extractor.py  # Wind/Solar forecast vs actual
    config.py               # Settlement points, weather zones, report IDs — CONFIGURABLE
    run_ercot.py

  caiso/
    api/
      oasis_api.py          # Existente, extender para componentes
    extractors/
      prices_extractor.py   # DA + FMM + HASP con TODOS los componentes (ENE, CONG, LOSS, GHG)
      load_extractor.py     # Load + peak
      renewable_extractor.py # Solar + Wind
      ancillary_extractor.py # AS prices (SR, NR, RU, RD, RMU, RMD)
      constraints_extractor.py # Shadow prices
      cenace_border_extractor.py  # IVY, OMS con componentes ENE/CNG/PER
    config.py               # Nodos CAISO + nodos CENACE frontera — CONFIGURABLE
    run_caiso.py

  guatemala/
    api/
      amm_api.py            # Excel download + parse múltiples sheets
    extractors/
      gtm_extractor.py      # POE + LBR con componentes + dispatch + import/export
    config.py
    run_gtm.py

  enverus/                   # NUEVO módulo — separar de ercot
    api/
      mosaic_api.py          # Cliente Mosaic API genérico
      synthetic_api.py       # Cliente MarginalUnit/Synthetic
    extractors/
      wind_extractor.py      # Wind actuals + forecasts (multi-modelo, por región)
      solar_extractor.py     # Solar actuals + forecasts
      load_extractor.py      # Load por hub/weather zone + net load
      fuel_mix_extractor.py  # Fuel mix (RT, delayed initial, delayed final)
      outages_extractor.py   # Dispatchable + renewable + scheduled outages
      congestion_extractor.py # COP/HSL forecast + actual + composite
      grid_extractor.py      # RT system conditions, PRC, reserves, tie flows, lambda
      prices_extractor.py    # LMP actuals + forecasts + composites + bands (P25/P75)
      ancillary_extractor.py # AS data
      synthetic_extractor.py # lmp_da, lmp_rt, as_da, as_rt, rtrdpa
      caiso_extractor.py     # Datos CAISO vía Enverus
    config.py               # Datasets, entities, ISOs — CONFIGURABLE
    run_enverus.py

  common/
    tipo_cambio.py           # Existente
    temperaturas.py          # Existente + expandir ciudades + wind/radiation
    db_connection.py         # Existente → refactorizar a base/db.py

  runner/
    run_all.py               # Orquestador principal
    daily_runner.py          # Runner con retry + alertas
    scheduler.py             # NUEVO: lógica de horarios (mañana 6:30, tarde 14:00)
```

### 2.2 BaseExtractor — Clase Abstracta

```python
# etl/base/extractor.py
from abc import ABC, abstractmethod
import pandas as pd
import logging
from datetime import datetime

class BaseExtractor(ABC):
    name: str                    # Nombre único del extractor
    source: str                  # "cenace", "ercot", "caiso", "guatemala", "enverus"
    data_type: str               # "fact" o "forecast"
    database: str = "XTS"        # Base de datos target
    schema: str = "dbo"          # Schema target
    table: str                   # Tabla target
    schedule: str = "morning"    # "morning", "afternoon", "both", "hourly"

    def __init__(self):
        self.logger = logging.getLogger(f"etl.{self.source}.{self.name}")

    @abstractmethod
    def extract(self, fecha_ini: str, fecha_fin: str) -> pd.DataFrame:
        """Extrae datos de la fuente. Retorna DataFrame con columnas esperadas."""
        ...

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validaciones genéricas. Override para validaciones específicas."""
        if df.empty:
            self.logger.warning(f"Sin datos para el período solicitado")
            return df

        # Check columnas esperadas
        expected = self.expected_columns()
        missing = set(expected) - set(df.columns)
        if missing:
            raise ValueError(f"Columnas faltantes: {missing}")

        # Check nulls excesivos (>50% en cualquier columna numérica)
        for col in df.select_dtypes(include='number').columns:
            null_pct = df[col].isna().mean()
            if null_pct > 0.5:
                self.logger.warning(f"Columna {col}: {null_pct:.0%} nulls")

        # Check rango de fechas
        if 'fecha' in df.columns:
            if df['fecha'].isna().any():
                raise ValueError("Fechas nulas encontradas")

        return df

    def upsert(self, df: pd.DataFrame) -> int:
        """
        Bulk upsert usando MERGE.
        - Si data_type == "fact": solo INSERT donde no exista (NUNCA sobreescribe)
        - Si data_type == "forecast": UPDATE si existe, INSERT si no
        """
        if df.empty:
            return 0

        from etl.base.db import get_connection, bulk_upsert
        conn = get_connection(self.database)
        count = bulk_upsert(
            conn=conn,
            schema=self.schema,
            table=self.table,
            df=df,
            key_columns=self.key_columns(),
            mode="insert_only" if self.data_type == "fact" else "upsert"
        )
        self.logger.info(f"Upserted {count} rows → {self.schema}.{self.table}")
        return count

    def run(self, fecha_ini: str, fecha_fin: str) -> int:
        """Pipeline completo: extract → validate → upsert."""
        self.logger.info(f"Iniciando {self.name} [{fecha_ini} → {fecha_fin}]")
        try:
            df = self.extract(fecha_ini, fecha_fin)
            df = self.validate(df)
            count = self.upsert(df)
            self.logger.info(f"Completado: {count} rows")
            return count
        except Exception as e:
            self.logger.error(f"Error en {self.name}: {e}", exc_info=True)
            raise

    @abstractmethod
    def key_columns(self) -> list[str]:
        """Columnas que forman la llave única (para MERGE)."""
        ...

    @abstractmethod
    def expected_columns(self) -> list[str]:
        """Columnas que debe tener el DataFrame."""
        ...
```

### 2.3 Bulk Upsert con MERGE (NO fila por fila)

```python
# etl/base/db.py
def bulk_upsert(conn, schema, table, df, key_columns, mode="upsert"):
    """
    1. Carga df a tabla temporal (#tmp_etl)
    2. MERGE INTO target USING #tmp_etl
    3. mode="insert_only" → solo WHEN NOT MATCHED THEN INSERT
       mode="upsert" → WHEN MATCHED THEN UPDATE + WHEN NOT MATCHED THEN INSERT
    """
    cursor = conn.cursor()
    temp_table = "#tmp_etl"

    # Crear temp table con estructura del df
    # INSERT df en temp table (fast_executemany=True)
    # MERGE statement
    # Return rows affected
    ...
```

### 2.4 Credenciales — CERO Hardcoded

```python
# etl/base/credentials.py
import os
from dotenv import load_dotenv

load_dotenv()  # Carga .env en desarrollo

def require(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        raise EnvironmentError(f"Variable de entorno requerida no encontrada: {var}")
    return val

# Todas las credenciales:
# ERCOT_USERNAME, ERCOT_PASSWORD, ERCOT_KEY, ERCOT_CLIENT_ID
# ENVERUS_USER, ENVERUS_PASS
# MU_USERNAME, MU_PASSWORD  (MarginalUnit/Synthetic)
# CENACE_BCA_USER, CENACE_BCA_PASS, CENACE_SIN_USER, CENACE_SIN_PASS
# BANXICO_TOKEN
# XTS_DB_SERVER, XTS_DB_PORT, XTS_DB_USER, XTS_DB_PASSWORD
# ALERT_EMAIL_FROM, ALERT_EMAIL_TO, ALERT_EMAIL_PASS
```

Crear archivo `.env.example` con todas las variables documentadas (sin valores reales).

---

## 3. ESQUEMA DE BASE DE DATOS — CAMBIOS NECESARIOS

### 3.1 Principio: Schemas por Fuente, Tablas por Tipo de Dato

Mantener los schemas existentes (`ercot`, `caiso`, `cenace`, `guatemala`, `trading`, `backoffice`) y agregar `enverus`, `weather`.

### 3.2 Nuevas Tablas Necesarias

**Servidor:** Office Server (migrar desde 100.70.216.12)
**Base de datos:** XTS (consolidar todo — eliminar la DB "PML" separada)

#### ERCOT Schema — Tablas Nuevas/Modificadas

```sql
-- Expandir DATOS_ERCOT existente (agregar columnas)
ALTER TABLE dbo.DATOS_ERCOT ADD
    SOLAR_ERCOT    FLOAT NULL,    -- Ya existe en schema pero confirmar
    WIND_PANHANDLE FLOAT NULL,    -- Nuevo: wind por región
    WIND_COASTAL   FLOAT NULL,
    FUEL_GAS_MW    FLOAT NULL,    -- Nuevo: fuel mix
    FUEL_COAL_MW   FLOAT NULL,
    FUEL_NUCLEAR_MW FLOAT NULL,
    FUEL_WIND_MW   FLOAT NULL,
    FUEL_SOLAR_MW  FLOAT NULL,
    FUEL_HYDRO_MW  FLOAT NULL,
    ORDC_ADDER     FLOAT NULL;    -- Nuevo: scarcity pricing

-- Tabla de load por weather zone
CREATE TABLE ercot.load_by_zone (
    fecha          DATETIME NOT NULL,
    weather_zone   VARCHAR(20) NOT NULL,  -- COAST, EAST, FAR_WEST, etc.
    load_mw        FLOAT NULL,
    PRIMARY KEY (fecha, weather_zone)
);

-- Tabla de ancillary services
CREATE TABLE ercot.ancillary_prices (
    fecha     DATETIME NOT NULL,
    as_type   VARCHAR(10) NOT NULL,  -- REGUP, REGDN, RRS, ECRS, NSRS
    price     FLOAT NULL,
    PRIMARY KEY (fecha, as_type)
);

-- Tabla de binding constraints
CREATE TABLE ercot.binding_constraints (
    fecha           DATETIME NOT NULL,
    constraint_name VARCHAR(200) NOT NULL,
    shadow_price    FLOAT NULL,
    PRIMARY KEY (fecha, constraint_name)
);

-- Tabla de forecast error renovable
CREATE TABLE ercot.renewable_forecast_error (
    fecha          DATETIME NOT NULL,
    resource_type  VARCHAR(10) NOT NULL,  -- WIND, SOLAR
    forecast_mw    FLOAT NULL,
    actual_mw      FLOAT NULL,
    error_mw       FLOAT NULL,
    PRIMARY KEY (fecha, resource_type)
);

-- Tabla de precios por settlement point (extensible)
CREATE TABLE ercot.prices (
    fecha            DATETIME NOT NULL,
    settlement_point VARCHAR(50) NOT NULL,  -- DC_L, DC_R, HB_BUSAVG, HB_HOUSTON, LZ_*, etc.
    market           VARCHAR(5) NOT NULL,   -- DA, RT
    lmp              FLOAT NULL,
    PRIMARY KEY (fecha, settlement_point, market)
);
```

#### CAISO Schema — Tablas Nuevas

```sql
-- Tabla de precios con TODOS los componentes (extensible por nodo)
CREATE TABLE caiso.prices (
    fecha        DATETIME NOT NULL,
    node         VARCHAR(50) NOT NULL,  -- ROA-230_2_N101, TJI-230_2_N101, + futuro
    market       VARCHAR(5) NOT NULL,   -- DA, FMM, HASP
    lmp          FLOAT NULL,
    lmp_ene      FLOAT NULL,            -- Componente energía
    lmp_cong     FLOAT NULL,            -- Componente congestión
    lmp_loss     FLOAT NULL,            -- Componente pérdidas
    lmp_ghg      FLOAT NULL,            -- Componente GHG
    PRIMARY KEY (fecha, node, market)
);

-- Tabla de CENACE nodos frontera con componentes
CREATE TABLE caiso.cenace_border (
    fecha        DATETIME NOT NULL,
    nodo         VARCHAR(20) NOT NULL,  -- 07IVY-230, 07OMS-230, + futuro
    mercado      VARCHAR(5) NOT NULL,   -- MDA, MTR
    pml          FLOAT NULL,
    pml_ene      FLOAT NULL,
    pml_cng      FLOAT NULL,
    pml_per      FLOAT NULL,
    PRIMARY KEY (fecha, nodo, mercado)
);

-- Tabla de ancillary services
CREATE TABLE caiso.ancillary_prices (
    fecha     DATETIME NOT NULL,
    as_type   VARCHAR(10) NOT NULL,  -- SR, NR, RU, RD, RMU, RMD
    price     FLOAT NULL,
    PRIMARY KEY (fecha, as_type)
);

-- Tabla de constraint shadow prices
CREATE TABLE caiso.constraints (
    fecha           DATETIME NOT NULL,
    constraint_name VARCHAR(200) NOT NULL,
    shadow_price    FLOAT NULL,
    market          VARCHAR(5) NOT NULL,
    PRIMARY KEY (fecha, constraint_name, market)
);
```

#### CENACE Schema — Tablas Nuevas

```sql
-- Consolidar PML de DB "PML" a schema cenace (eliminar DB separada)
-- Nodos P (extensible — empezar con nodos frontera + nodos de interés)
CREATE TABLE cenace.pml_nodos_p (
    fecha      DATETIME NOT NULL,
    sistema    VARCHAR(5) NOT NULL,   -- SIN, BCA
    nodo       VARCHAR(20) NOT NULL,  -- 07IVY-230, 06LAA-138, etc.
    mercado    VARCHAR(5) NOT NULL,   -- MDA, MTR
    pml        FLOAT NULL,
    pml_ene    FLOAT NULL,
    pml_per    FLOAT NULL,
    pml_cng    FLOAT NULL,
    PRIMARY KEY (fecha, sistema, nodo, mercado)
);

-- Demanda por zona
CREATE TABLE cenace.demanda (
    fecha      DATETIME NOT NULL,
    sistema    VARCHAR(5) NOT NULL,
    zona       VARCHAR(50) NOT NULL,
    tipo       VARCHAR(10) NOT NULL,  -- FORECAST (SWDEMAM), REAL (SWDEMREAL)
    demanda_mw FLOAT NULL,
    PRIMARY KEY (fecha, sistema, zona, tipo)
);

-- Generación por tipo de tecnología
CREATE TABLE cenace.generacion (
    fecha        DATETIME NOT NULL,
    sistema      VARCHAR(5) NOT NULL,
    tecnologia   VARCHAR(30) NOT NULL,  -- SOLAR, EOLICA, HIDRO, TERMICA, etc.
    generacion_mw FLOAT NULL,
    PRIMARY KEY (fecha, sistema, tecnologia)
);

-- Capacidad transferencia enlaces internacionales
-- Ya existe dbo.CAPACIDADES — usar esa tabla

-- Import/Export — ya existe dbo.IMPEXP — usar esa tabla

-- Déficit/Excedente — ya existe dbo.DEF_EXC — usar esa tabla
```

#### Enverus Schema — Tablas Nuevas

```sql
CREATE SCHEMA enverus;

-- Wind/Solar forecasts multi-modelo por región
CREATE TABLE enverus.renewable_forecasts (
    fecha          DATETIME NOT NULL,
    iso            VARCHAR(10) NOT NULL,  -- ERCOT, CAISO
    resource_type  VARCHAR(10) NOT NULL,  -- WIND, SOLAR, COMBINED
    region         VARCHAR(30) NOT NULL,  -- coastal, panhandle, west, south, north, total
    model          VARCHAR(20) NOT NULL,  -- RPP, STPF, HRRR, ECMWF, COP_HSL
    generation_mw  FLOAT NULL,
    data_type      VARCHAR(10) NOT NULL,  -- ACTUAL, FORECAST
    PRIMARY KEY (fecha, iso, resource_type, region, model, data_type)
);

-- Fuel mix
CREATE TABLE enverus.fuel_mix (
    fecha         DATETIME NOT NULL,
    iso           VARCHAR(10) NOT NULL,
    source_type   VARCHAR(10) NOT NULL,  -- RT, DELAYED_INITIAL, DELAYED_FINAL
    gas_mw        FLOAT NULL,
    coal_mw       FLOAT NULL,
    nuclear_mw    FLOAT NULL,
    wind_mw       FLOAT NULL,
    solar_mw      FLOAT NULL,
    hydro_mw      FLOAT NULL,
    battery_mw    FLOAT NULL,
    other_mw      FLOAT NULL,
    PRIMARY KEY (fecha, iso, source_type)
);

-- Outages
CREATE TABLE enverus.outages (
    fecha         DATETIME NOT NULL,
    iso           VARCHAR(10) NOT NULL,
    outage_type   VARCHAR(20) NOT NULL,  -- DISPATCHABLE, RENEWABLE, TOTAL, SCHEDULED
    outage_mw     FLOAT NULL,
    PRIMARY KEY (fecha, iso, outage_type)
);

-- COP/HSL (congestión por nodo)
CREATE TABLE enverus.congestion (
    fecha         DATETIME NOT NULL,
    iso           VARCHAR(10) NOT NULL,
    node          VARCHAR(50) NOT NULL,
    data_type     VARCHAR(15) NOT NULL,  -- FORECAST, ACTUAL, COMPOSITE
    value         FLOAT NULL,
    PRIMARY KEY (fecha, iso, node, data_type)
);

-- Grid conditions
CREATE TABLE enverus.grid_conditions (
    fecha              DATETIME NOT NULL,
    iso                VARCHAR(10) NOT NULL,
    frequency_hz       FLOAT NULL,
    prc_mw             FLOAT NULL,
    operating_reserves FLOAT NULL,
    dam_lambda         FLOAT NULL,
    sced_lambda        FLOAT NULL,
    PRIMARY KEY (fecha, iso)
);

-- Load por zona (hub, weather zone)
CREATE TABLE enverus.load (
    fecha       DATETIME NOT NULL,
    iso         VARCHAR(10) NOT NULL,
    zone_type   VARCHAR(15) NOT NULL,  -- HUB, WEATHER_ZONE, SYSTEM
    zone_name   VARCHAR(30) NOT NULL,
    data_type   VARCHAR(15) NOT NULL,  -- ACTUAL, FORECAST, NET_LOAD
    load_mw     FLOAT NULL,
    PRIMARY KEY (fecha, iso, zone_type, zone_name, data_type)
);

-- Tie flows
CREATE TABLE enverus.tie_flows (
    fecha         DATETIME NOT NULL,
    iso           VARCHAR(10) NOT NULL,
    interface_id  VARCHAR(50) NOT NULL,
    flow_mw       FLOAT NULL,
    PRIMARY KEY (fecha, iso, interface_id)
);

-- Synthetic forecasts (probabilísticos)
CREATE TABLE enverus.synthetic_forecasts (
    fecha         DATETIME NOT NULL,
    dataset       VARCHAR(10) NOT NULL,  -- lmp_da, lmp_rt, as_da, as_rt, rtrdpa
    entity        VARCHAR(50) NOT NULL,  -- DC_L, DC_R, + otros pnodes
    as_of         DATETIME NOT NULL,     -- Timestamp de publicación
    p05           FLOAT NULL,
    p33           FLOAT NULL,
    p50           FLOAT NULL,            -- Mediana
    p66           FLOAT NULL,
    p95           FLOAT NULL,
    PRIMARY KEY (fecha, dataset, entity, as_of)
);

-- Price forecasts Enverus (DA/RT con bandas)
CREATE TABLE enverus.price_forecasts (
    fecha         DATETIME NOT NULL,
    iso           VARCHAR(10) NOT NULL,
    node          VARCHAR(50) NOT NULL,
    market        VARCHAR(5) NOT NULL,   -- DA, RT
    forecast_type VARCHAR(15) NOT NULL,  -- FORECAST, COMPOSITE
    lmp           FLOAT NULL,
    lmp_p25       FLOAT NULL,
    lmp_p75       FLOAT NULL,
    PRIMARY KEY (fecha, iso, node, market, forecast_type)
);

-- Ancillary services
CREATE TABLE enverus.ancillary (
    fecha       DATETIME NOT NULL,
    iso         VARCHAR(10) NOT NULL,
    market      VARCHAR(5) NOT NULL,   -- DA, RT
    as_type     VARCHAR(20) NOT NULL,
    price       FLOAT NULL,
    cleared_mw  FLOAT NULL,
    PRIMARY KEY (fecha, iso, market, as_type)
);
```

#### Weather Schema

```sql
CREATE SCHEMA weather;

-- Expandir temperaturas (más ciudades + wind + radiación)
CREATE TABLE weather.observations (
    fecha            DATETIME NOT NULL,
    city_code        VARCHAR(10) NOT NULL,  -- TIJ, MXL, HOU, DAL, etc.
    temperature_c    FLOAT NULL,
    windspeed_kmh    FLOAT NULL,
    direct_radiation FLOAT NULL,
    diffuse_radiation FLOAT NULL,
    PRIMARY KEY (fecha, city_code)
);
```

### 3.3 Tablas Existentes que se Mantienen

| Tabla | Acción |
|-------|--------|
| dbo.DATOS_ERCOT | Mantener + agregar columnas nuevas |
| dbo.DATOS_CAISO | Mantener por compatibilidad (legacy) — nueva data va a `caiso.prices` |
| dbo.GTM | Mantener + agregar columnas (dispatch, import/export) |
| dbo.CAPACIDADES | Usar para capacidad transferencia CENACE |
| dbo.DEF_EXC | Usar para déficit/excedente BCA |
| dbo.IMPEXP | Usar para import/export CENACE |
| dbo.TIPO_CAMBIO | Mantener |
| dbo.TEMPERATURAS | Migrar a weather.observations (backward compatible view) |
| dbo.ESTADOS_DE_CUENTA_XML | Mantener |
| PML.dbo.MDA_D | Migrar a cenace.pml_zonas (backward compatible view) |
| PML.dbo.MTR | Migrar a cenace.pml_zonas (backward compatible view) |
| trading.trades | Mantener |

---

## 4. SCHEDULING — CUÁNDO CORRE QUÉ

### 4.1 Corrida Matutina (6:00 AM CST)

**Objetivo:** Tener toda la información fresca para el desk de trading a las 7:00 AM.

| Prioridad | Extractor | Datos | Tipo | Tiempo Est. |
|-----------|-----------|-------|------|-------------|
| 1 | ERCOT DA prices | Precios DA del día anterior (fact) | fact | 30s |
| 1 | ERCOT RT prices | Precios RT del día anterior (fact) | fact | 30s |
| 1 | CAISO DA + FMM + componentes | Precios + componentes del día anterior | fact | 45s |
| 1 | CENACE PML MDA + MTR (108 zonas) | Precios por zona del día anterior | fact | 5 min |
| 1 | Guatemala POE + LBR | Precios spot + PML frontera | fact | 30s |
| 2 | CENACE nodos P frontera | IVY, OMS, LAA, RRD, LBR con componentes | fact | 30s |
| 2 | ERCOT wind/solar/load | Generación y carga del día anterior | fact | 1 min |
| 2 | ERCOT fuel mix | Mix de generación | fact | 30s |
| 2 | Tipo de cambio | FIX USD/MXN | fact | 5s |
| 3 | Enverus Synthetic lmp_da/lmp_rt | Forecasts probabilísticos (48h) | forecast | 1 min |
| 3 | Enverus wind forecasts (multi-modelo) | RPP, STPF, HRRR, ECMWF por región | forecast | 2 min |
| 3 | Enverus solar forecasts | COP/HSL, RPP, STPF | forecast | 1 min |
| 3 | Enverus net load forecast | Load - renewables | forecast | 30s |
| 3 | MarginalUnit DA/RT forecasts | Synthetic percentiles DC_L, DC_R | forecast | 30s |
| 4 | ERCOT ORDC | Scarcity adder | fact | 30s |
| 4 | ERCOT ancillary services | AS prices | fact | 30s |
| 4 | ERCOT binding constraints | Constraints activas | fact | 30s |
| 4 | Enverus outages | Dispatchable + renewable | fact | 30s |
| 4 | Enverus COP/HSL | Congestión por nodo (forecast + actual) | mixed | 1 min |
| 4 | Enverus fuel mix | RT + delayed | fact | 30s |
| 4 | Enverus tie flows | Flujos inter-área | fact | 30s |
| 4 | Enverus grid conditions | Lambda, reserves, PRC | fact | 30s |
| 5 | CENACE demanda (SWDEMAM/SWDEMREAL) | Pronóstico + real por zona | mixed | 3 min |
| 5 | CENACE cross-border | Capacidad, import/export, déficit | fact | 1 min |
| 5 | Temperaturas | 15 ciudades + wind + radiación | fact | 30s |
| 5 | CAISO AS prices | Ancillary services | fact | 30s |
| 5 | CAISO constraints | Shadow prices | fact | 30s |
| 5 | Guatemala dispatch + import/export | Sheets adicionales del Excel | fact | 30s |

**Total estimado: ~20 minutos** (con paralelización por fuente)

### 4.2 Corrida de la Tarde (14:00 CST)

Solo actualizar **forecasts** y datos que cambian intradía:

| Extractor | Datos | Por qué |
|-----------|-------|---------|
| Enverus Synthetic lmp_da/lmp_rt | Forecasts actualizados | Nuevo as_of del día |
| Enverus wind/solar forecasts | Pronósticos renovables actualizados | Modelos se refrescan |
| Enverus COP/HSL | Congestión actualizada | Condiciones cambian intradía |
| Enverus outages | Outages nuevos/actualizados | Pueden aparecer forzados |
| MarginalUnit forecasts | Nuevos percentiles | Se publican cada hora |
| ERCOT RT prices (parcial) | RT del día en curso (hasta la hora actual) | Monitoreo intradía |
| ERCOT load/wind/solar (actual) | Generación/carga del día en curso | Validar vs forecast |

### 4.3 Regla Fact vs Forecast

```python
# En cada extractor, definir:
class ErcotDAPricesExtractor(BaseExtractor):
    data_type = "fact"  # NUNCA sobreescribir

class EnverusSyntheticExtractor(BaseExtractor):
    data_type = "forecast"  # Siempre actualizar con último forecast

# En la tabla synthetic_forecasts, mantener TODOS los as_of (historial de forecasts)
# En las tablas de fact, usar INSERT WHERE NOT EXISTS
```

---

## 5. CONFIGURACIÓN EXTENSIBLE — NODOS Y ZONAS

### 5.1 Archivos de Config (NO hardcoded en extractores)

```python
# etl/ercot/config.py
SETTLEMENT_POINTS = {
    "hubs": ["DC_L", "DC_R", "HB_BUSAVG", "HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST"],
    "load_zones": [],  # Agregar después: LZ_AEN, LZ_CPS, LZ_HOUSTON, etc.
}
WEATHER_ZONES = ["COAST", "EAST", "FAR_WEST", "NORTH", "NORTH_C", "SOUTH_C", "SOUTHERN", "WEST"]
WIND_REGIONS = ["coastal", "north", "panhandle", "south", "west"]

# etl/caiso/config.py
NODES = ["ROA-230_2_N101", "TJI-230_2_N101"]  # Agregar más después
CENACE_BORDER_NODES = {
    "BCA": ["07IVY-230", "07OMS-230"],
}

# etl/cenace/config.py
NODOS_P_PRIORITARIOS = {
    "BCA": ["07IVY-230", "07OMS-230", "07ENS-230", "07MXL-230", "07TIJ-230"],
    "SIN": ["06LAA-138", "06RRD-138", "09LBR-230"],
    # Agregar más después sin tocar código
}

# etl/enverus/config.py
ERCOT_WIND_REGIONS = ["coastal", "north", "panhandle", "south", "west"]
ERCOT_FORECAST_MODELS = ["RPP", "STPF", "HRRR", "ECMWF", "COP_HSL"]
SYNTHETIC_ENTITIES = ["DC_L", "DC_R"]  # Agregar más pnodes después
SYNTHETIC_DATASETS = ["lmp_da", "lmp_rt", "as_da", "as_rt", "rtrdpa"]
```

Para agregar un nuevo nodo o settlement point: **solo editar el config.py** — el extractor lo toma automáticamente.

---

## 6. ERROR HANDLING Y MONITOREO

### 6.1 Retry por Fuente (no global)

```python
# Si CENACE falla, no bloquea ERCOT
# Cada fuente tiene su propia retry con backoff
RETRY_CONFIG = {
    "cenace": {"max_retries": 3, "backoff_seconds": 60},
    "ercot":  {"max_retries": 4, "backoff_seconds": 15},
    "caiso":  {"max_retries": 3, "backoff_seconds": 10},
    "enverus": {"max_retries": 3, "backoff_seconds": 30},
    "guatemala": {"max_retries": 2, "backoff_seconds": 30},
}
```

### 6.2 Validaciones Post-Extracción

```python
# Precios: rango esperado
PRICE_RANGES = {
    "ercot_da": (-500, 10000),   # USD/MWh
    "ercot_rt": (-500, 10000),
    "cenace_mda": (-500, 5000),
    "cenace_mtr": (-500, 5000),
    "caiso_da": (-500, 5000),
    "caiso_fmm": (-500, 5000),
    "guatemala_poe": (0, 500),
}

# Completitud: horas esperadas por día
HOURS_PER_DAY = 24  # 23 en spring forward, 25 en fall back → manejar excepciones DST
```

### 6.3 Logging Estructurado

```python
# Cada extractor loggea:
# [TIMESTAMP] [LEVEL] [SOURCE] [EXTRACTOR] [ACTION] [DETAILS]
# Ejemplo:
# 2026-04-07 06:05:12 INFO ercot prices_extractor extract rows=168 fecha_ini=2026-04-06
# 2026-04-07 06:05:13 INFO ercot prices_extractor upsert inserted=168 updated=0

# Log file: logs/etl_{YYYY-MM-DD}.log
# Rotación: mantener 30 días
```

### 6.4 Tabla de Monitoreo

```sql
CREATE TABLE dbo.etl_log (
    id              INT IDENTITY PRIMARY KEY,
    run_date        DATETIME NOT NULL DEFAULT GETDATE(),
    source          VARCHAR(20) NOT NULL,
    extractor       VARCHAR(50) NOT NULL,
    status          VARCHAR(10) NOT NULL,  -- SUCCESS, FAILED, PARTIAL
    rows_extracted  INT NULL,
    rows_inserted   INT NULL,
    rows_updated    INT NULL,
    duration_sec    FLOAT NULL,
    error_message   VARCHAR(2000) NULL,
    fecha_ini       DATE NULL,
    fecha_fin       DATE NULL
);
```

### 6.5 Alerta por Email

Si algún extractor falla después de todos los retries:
- Email a equipo de trading
- Incluir: qué falló, cuántos retries, último error
- No bloquear otros extractores

---

## 7. DEPLOYMENT — OFFICE SERVER

### 7.1 Desarrollo → Office Server

**Paso 1: Desarrollo local (esta semana)**
- Crear toda la infraestructura en la máquina de desarrollo
- Correr contra la DB actual (100.70.216.12 o local)
- Validar que cada extractor funciona

**Paso 2: Migrar al Office Server**
- Instalar Python 3.10+ en Office Server
- Instalar ODBC Driver 17 for SQL Server
- Clonar repo
- Crear `.env` con credenciales de producción
- Configurar SQL Server en Office Server
- Ejecutar scripts de migración de DB (schemas + tablas nuevas)

### 7.2 SQL Server en Office Server — Recomendaciones

```
Instancia: MSSQL en Office Server
Base: XTS (una sola — eliminar DB "PML" separada)

Schemas:
  dbo        → tablas legacy + tablas compartidas (tipo_cambio, etl_log)
  ercot      → todo ERCOT (precios, load, wind, solar, AS, constraints)
  caiso      → todo CAISO (precios con componentes, AS, constraints)
  cenace     → todo CENACE (PML zonas, PML nodos P, demanda, generación)
  guatemala  → todo Guatemala (POE, dispatch, import/export)
  enverus    → todo Enverus (renewable forecasts, fuel mix, outages, COP/HSL, grid, synthetic)
  weather    → temperaturas + viento + radiación
  trading    → trades, snapshots, históricos
  backoffice → settlements, billing, ECDs

Backups:
  - Full backup diario a las 23:00
  - Differential cada 6 horas
  - Transaction log cada 30 min

Maintenance:
  - Rebuild indexes semanal (domingos 02:00)
  - Update statistics diario (23:30)
  - Shrink log files mensual
```

### 7.3 Scheduling en Office Server

```
Windows Task Scheduler:
  06:00 CST → python -m etl.runner.run_all --schedule morning
  14:00 CST → python -m etl.runner.run_all --schedule afternoon
  23:30 CST → python -m etl.runner.run_all --schedule maintenance (backfill gaps)
```

---

## 8. ORDEN DE EJECUCIÓN — FASES

### Fase 1: Fundación (Días 1-3)

1. Crear `etl/base/` — extractor.py, db.py, credentials.py, validators.py
2. Migrar credenciales hardcodeadas a `.env`
3. Implementar bulk upsert con MERGE
4. Estandarizar logging
5. Ejecutar scripts SQL para nuevos schemas y tablas
6. **Test:** Refactorizar un extractor existente (ERCOT) sobre BaseExtractor

### Fase 2: Quick Wins (Días 4-6)

7. Conectar ERCOT solar (código ya existe)
8. Parsear CAISO componentes LMP (datos ya se descargan)
9. Extraer componentes de IVY/OMS/LBR
10. Agregar ERCOT wind por región
11. Integrar CENACE en run_all.py
12. **Test:** Validar datos nuevos vs datos anteriores

### Fase 3: Nuevos Extractores ERCOT + CAISO (Días 7-12)

13. ERCOT fuel mix, ORDC, AS prices
14. ERCOT binding constraints, load by weather zone
15. ERCOT forecast vs actual
16. CAISO HASP LMP, AS prices, constraints
17. CAISO wind forecast
18. **Test:** Backfill 7 días de cada nuevo extractor

### Fase 4: CENACE Expandido (Días 13-16)

19. CENACE nodos P (empezar con 7 nodos frontera)
20. CENACE demanda (SWDEMAM/SWDEMREAL)
21. CENACE generación por tecnología
22. CENACE cross-border (capacidad, import/export, déficit)
23. Guatemala sheets adicionales
24. **Test:** Validar completitud de datos CENACE

### Fase 5: Enverus Completo (Días 17-22)

25. Módulo `etl/enverus/` con Mosaic API client
26. Wind/Solar forecasts multi-modelo por región
27. Fuel mix, outages, COP/HSL
28. Grid conditions (lambda, reserves, PRC, tie flows)
29. Load por hub/weather zone + net load
30. Synthetic forecasts (lmp_da, lmp_rt, as_da, as_rt, rtrdpa)
31. Price forecasts + composites + bands P25/P75
32. **Test:** Validar contra notebooks existentes

### Fase 6: Orquestación y Monitoring (Días 23-25)

33. Scheduler (morning 6:00, afternoon 14:00)
34. Fact vs forecast logic
35. Tabla etl_log + alertas email
36. Validaciones post-extracción
37. **Test:** Corrida completa end-to-end

### Fase 7: Migración a Office Server (Días 26-28)

38. Setup SQL Server en Office Server
39. Migrar schemas + tablas + datos históricos
40. Instalar Python + dependencias
41. Configurar .env de producción
42. Setup Windows Task Scheduler
43. **Test:** 3 días de corrida en paralelo (dev + prod)

---

## 9. ARCHIVOS DE REFERENCIA

| Archivo | Ubicación | Qué contiene |
|---------|-----------|-------------|
| datasets_completo.csv | Extractors/context/ | 249 datasets con SI/NO, nodos, componentes |
| extractor_universe_map.md | Extractors/context/ | Inventario detallado de APIs |
| XTS_Estructura_BaseDatos.xlsx | Downloads/ | Estructura DB actual |
| db/01_schemas.sql | db/ | Schemas SQL existentes |
| db/02_views.sql | db/ | Views existentes |
| db/03_morning_historico.sql | db/ | Tablas históricas |

---

## 10. PREGUNTAS ABIERTAS PARA DECISIÓN

1. **Nodos P adicionales de CENACE:** Empezamos con los 7 frontera (IVY, OMS, LAA, RRD, LBR, ENS, MXL). ¿Hay otros nodos P específicos que quieran? La estructura permite agregar sin cambiar código.

2. **Settlement points adicionales de ERCOT:** Empezamos con DC_L, DC_R + 5 hubs. ¿Quieren load zones también (LZ_HOUSTON, LZ_SOUTH, etc.)?

3. **Nodos CAISO adicionales:** Empezamos con ROA y TJI. ¿Hay otros nodos CAISO relevantes para cross-border?

4. **Enverus Synthetic entities:** Empezamos con DC_L y DC_R. ¿Quieren forecasts sintéticos para otros pnodes?

5. **Retención de datos forecast:** ¿Mantener historial de TODOS los forecasts (cada as_of), o solo el último? Recomendación: mantener todos para backtesting.

6. **Office Server specs:** ¿Cuánta RAM/disco tiene? Para dimensionar la DB y los procesos ETL.
