-- =============================================================================
-- XTS Platform — Nuevos schemas y tablas (Marco's architecture)
-- Ejecutar en: XTS database
-- Idempotente: puede correrse múltiples veces sin error
-- =============================================================================

USE XTS;
GO

-- ── Schemas nuevos ─────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'enverus')
    EXEC('CREATE SCHEMA enverus');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'weather')
    EXEC('CREATE SCHEMA weather');
GO

-- (ercot, caiso, cenace, guatemala ya existen en 01_schemas.sql)

PRINT 'Schemas: enverus, weather creados (si no existian)';
GO

-- =============================================================================
-- ETL Monitoring
-- =============================================================================
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='etl_log')
BEGIN
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
    PRINT 'Tabla creada: dbo.etl_log';
END
GO

-- =============================================================================
-- ERCOT Schema
-- =============================================================================

-- Precios DA/RT por nodo (DC_L, DC_R, hubs, load zones)
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='ercot' AND TABLE_NAME='prices')
BEGIN
    CREATE TABLE ercot.prices (
        fecha       DATETIME NOT NULL,
        node        VARCHAR(30) NOT NULL,
        market      VARCHAR(5) NOT NULL,   -- DA, RT
        lmp         FLOAT NULL,
        PRIMARY KEY (fecha, node, market)
    );
    CREATE INDEX IX_ercot_prices_fecha ON ercot.prices (fecha);
    PRINT 'Tabla creada: ercot.prices';
END
GO

-- Componentes LMP (energy, congestion, loss) por nodo
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='ercot' AND TABLE_NAME='lmp_components')
BEGIN
    CREATE TABLE ercot.lmp_components (
        fecha       DATETIME NOT NULL,
        node        VARCHAR(30) NOT NULL,
        market      VARCHAR(5) NOT NULL,   -- DA, RT
        energy      FLOAT NULL,
        congestion  FLOAT NULL,
        loss        FLOAT NULL,
        PRIMARY KEY (fecha, node, market)
    );
    PRINT 'Tabla creada: ercot.lmp_components';
END
GO

-- Carga por zona climática
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='ercot' AND TABLE_NAME='load')
BEGIN
    CREATE TABLE ercot.load (
        fecha       DATETIME NOT NULL,
        zone        VARCHAR(20) NOT NULL,  -- SYSTEM, COAST, EAST, etc.
        data_type   VARCHAR(10) NOT NULL,  -- ACTUAL, FORECAST
        load_mw     FLOAT NULL,
        PRIMARY KEY (fecha, zone, data_type)
    );
    PRINT 'Tabla creada: ercot.load';
END
GO

-- Generación eólica por región
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='ercot' AND TABLE_NAME='wind')
BEGIN
    CREATE TABLE ercot.wind (
        fecha       DATETIME NOT NULL,
        region      VARCHAR(20) NOT NULL,  -- SYSTEM, coastal, north, etc.
        data_type   VARCHAR(10) NOT NULL,  -- ACTUAL, FORECAST_STPF, FORECAST_COP
        gen_mw      FLOAT NULL,
        PRIMARY KEY (fecha, region, data_type)
    );
    PRINT 'Tabla creada: ercot.wind';
END
GO

-- Generación solar
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='ercot' AND TABLE_NAME='solar')
BEGIN
    CREATE TABLE ercot.solar (
        fecha       DATETIME NOT NULL,
        data_type   VARCHAR(10) NOT NULL,  -- ACTUAL, FORECAST_STPF, FORECAST_COP
        gen_mw      FLOAT NULL,
        PRIMARY KEY (fecha, data_type)
    );
    PRINT 'Tabla creada: ercot.solar';
END
GO

-- Fuel mix
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='ercot' AND TABLE_NAME='fuel_mix')
BEGIN
    CREATE TABLE ercot.fuel_mix (
        fecha       DATETIME NOT NULL,
        fuel_type   VARCHAR(20) NOT NULL,
        gen_mw      FLOAT NULL,
        PRIMARY KEY (fecha, fuel_type)
    );
    PRINT 'Tabla creada: ercot.fuel_mix';
END
GO

-- Ancillary services
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='ercot' AND TABLE_NAME='ancillary')
BEGIN
    CREATE TABLE ercot.ancillary (
        fecha       DATETIME NOT NULL,
        market      VARCHAR(5) NOT NULL,   -- DA, RT
        as_type     VARCHAR(20) NOT NULL,  -- REGUP, REGDN, RRSFFR, RRSPFR, ECRSM, ECRSS, NONSPIN
        price       FLOAT NULL,
        cleared_mw  FLOAT NULL,
        PRIMARY KEY (fecha, market, as_type)
    );
    PRINT 'Tabla creada: ercot.ancillary';
END
GO

-- ORDC (scarcity adder)
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='ercot' AND TABLE_NAME='ordc')
BEGIN
    CREATE TABLE ercot.ordc (
        fecha       DATETIME NOT NULL,
        adder_rt    FLOAT NULL,
        PRIMARY KEY (fecha)
    );
    PRINT 'Tabla creada: ercot.ordc';
END
GO

-- Binding constraints
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='ercot' AND TABLE_NAME='binding_constraints')
BEGIN
    CREATE TABLE ercot.binding_constraints (
        fecha            DATETIME NOT NULL,
        constraint_name  VARCHAR(100) NOT NULL,
        shadow_price     FLOAT NULL,
        PRIMARY KEY (fecha, constraint_name)
    );
    PRINT 'Tabla creada: ercot.binding_constraints';
END
GO

-- =============================================================================
-- CAISO Schema
-- =============================================================================

-- Precios DA/FMM por nodo
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='caiso' AND TABLE_NAME='prices')
BEGIN
    CREATE TABLE caiso.prices (
        fecha       DATETIME NOT NULL,
        node        VARCHAR(50) NOT NULL,
        market      VARCHAR(5) NOT NULL,   -- DA, FMM, RT5
        lmp         FLOAT NULL,
        energy      FLOAT NULL,
        congestion  FLOAT NULL,
        loss        FLOAT NULL,
        PRIMARY KEY (fecha, node, market)
    );
    CREATE INDEX IX_caiso_prices_fecha ON caiso.prices (fecha);
    PRINT 'Tabla creada: caiso.prices';
END
GO

-- Ancillary services
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='caiso' AND TABLE_NAME='ancillary')
BEGIN
    CREATE TABLE caiso.ancillary (
        fecha       DATETIME NOT NULL,
        market      VARCHAR(5) NOT NULL,
        as_type     VARCHAR(20) NOT NULL,
        price       FLOAT NULL,
        cleared_mw  FLOAT NULL,
        PRIMARY KEY (fecha, market, as_type)
    );
    PRINT 'Tabla creada: caiso.ancillary';
END
GO

-- =============================================================================
-- CENACE Schema
-- =============================================================================

-- PML por zona (108 zonas)
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='cenace' AND TABLE_NAME='pml_zonas')
BEGIN
    CREATE TABLE cenace.pml_zonas (
        fecha       DATETIME NOT NULL,
        sistema     VARCHAR(5) NOT NULL,   -- SIN, BCA, BCS
        zona        VARCHAR(20) NOT NULL,
        mercado     VARCHAR(5) NOT NULL,   -- MDA, MTR
        pml         FLOAT NULL,
        componente_energia     FLOAT NULL,
        componente_congestion  FLOAT NULL,
        componente_perdidas    FLOAT NULL,
        PRIMARY KEY (fecha, sistema, zona, mercado)
    );
    CREATE INDEX IX_cenace_pmlzonas_fecha ON cenace.pml_zonas (fecha);
    PRINT 'Tabla creada: cenace.pml_zonas';
END
GO

-- PML nodos P frontera (IVY, OMS, LAA, RRD, LBR, ENS, MXL)
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='cenace' AND TABLE_NAME='pml_nodos_p')
BEGIN
    CREATE TABLE cenace.pml_nodos_p (
        fecha       DATETIME NOT NULL,
        nodo        VARCHAR(20) NOT NULL,
        mercado     VARCHAR(5) NOT NULL,   -- MDA, MTR
        pml         FLOAT NULL,
        componente_energia     FLOAT NULL,
        componente_congestion  FLOAT NULL,
        componente_perdidas    FLOAT NULL,
        PRIMARY KEY (fecha, nodo, mercado)
    );
    PRINT 'Tabla creada: cenace.pml_nodos_p';
END
GO

-- Demanda por zona
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='cenace' AND TABLE_NAME='demanda')
BEGIN
    CREATE TABLE cenace.demanda (
        fecha       DATETIME NOT NULL,
        sistema     VARCHAR(5) NOT NULL,
        zona        VARCHAR(20) NOT NULL,
        data_type   VARCHAR(10) NOT NULL,  -- FORECAST, ACTUAL
        demanda_mw  FLOAT NULL,
        PRIMARY KEY (fecha, sistema, zona, data_type)
    );
    PRINT 'Tabla creada: cenace.demanda';
END
GO

-- Cross-border: capacidad, import/export, deficit/excedente
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='cenace' AND TABLE_NAME='cross_border')
BEGIN
    CREATE TABLE cenace.cross_border (
        fecha              DATETIME NOT NULL,
        enlace             VARCHAR(30) NOT NULL,
        capacidad_mw       FLOAT NULL,
        importacion_mw     FLOAT NULL,
        exportacion_mw     FLOAT NULL,
        deficit_mw         FLOAT NULL,
        excedente_mw       FLOAT NULL,
        PRIMARY KEY (fecha, enlace)
    );
    PRINT 'Tabla creada: cenace.cross_border';
END
GO

-- =============================================================================
-- Enverus Schema
-- =============================================================================

-- Generación renovable forecasts (wind/solar multi-modelo)
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='enverus' AND TABLE_NAME='renewable_forecasts')
BEGIN
    CREATE TABLE enverus.renewable_forecasts (
        fecha         DATETIME NOT NULL,
        iso           VARCHAR(10) NOT NULL,
        resource_type VARCHAR(10) NOT NULL,  -- WIND, SOLAR
        region        VARCHAR(30) NOT NULL,
        model         VARCHAR(20) NOT NULL,  -- RPP, STPF, HRRR, ECMWF, COP_HSL
        gen_mw        FLOAT NULL,
        PRIMARY KEY (fecha, iso, resource_type, region, model)
    );
    PRINT 'Tabla creada: enverus.renewable_forecasts';
END
GO

-- Outages
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='enverus' AND TABLE_NAME='outages')
BEGIN
    CREATE TABLE enverus.outages (
        fecha         DATETIME NOT NULL,
        iso           VARCHAR(10) NOT NULL,
        outage_type   VARCHAR(20) NOT NULL,  -- DISPATCHABLE, RENEWABLE, FORCED
        capacity_mw   FLOAT NULL,
        PRIMARY KEY (fecha, iso, outage_type)
    );
    PRINT 'Tabla creada: enverus.outages';
END
GO

-- COP/HSL (congestión por nodo)
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='enverus' AND TABLE_NAME='cop_hsl')
BEGIN
    CREATE TABLE enverus.cop_hsl (
        fecha         DATETIME NOT NULL,
        iso           VARCHAR(10) NOT NULL,
        node          VARCHAR(50) NOT NULL,
        data_type     VARCHAR(15) NOT NULL,  -- FORECAST, ACTUAL, COMPOSITE
        value         FLOAT NULL,
        PRIMARY KEY (fecha, iso, node, data_type)
    );
    PRINT 'Tabla creada: enverus.cop_hsl';
END
GO

-- Grid conditions
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='enverus' AND TABLE_NAME='grid_conditions')
BEGIN
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
    PRINT 'Tabla creada: enverus.grid_conditions';
END
GO

-- Load por zona (hub, weather zone)
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='enverus' AND TABLE_NAME='load')
BEGIN
    CREATE TABLE enverus.load (
        fecha       DATETIME NOT NULL,
        iso         VARCHAR(10) NOT NULL,
        zone_type   VARCHAR(15) NOT NULL,  -- HUB, WEATHER_ZONE, SYSTEM
        zone_name   VARCHAR(30) NOT NULL,
        data_type   VARCHAR(15) NOT NULL,  -- ACTUAL, FORECAST, NET_LOAD
        load_mw     FLOAT NULL,
        PRIMARY KEY (fecha, iso, zone_type, zone_name, data_type)
    );
    PRINT 'Tabla creada: enverus.load';
END
GO

-- Tie flows
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='enverus' AND TABLE_NAME='tie_flows')
BEGIN
    CREATE TABLE enverus.tie_flows (
        fecha         DATETIME NOT NULL,
        iso           VARCHAR(10) NOT NULL,
        interface_id  VARCHAR(50) NOT NULL,
        flow_mw       FLOAT NULL,
        PRIMARY KEY (fecha, iso, interface_id)
    );
    PRINT 'Tabla creada: enverus.tie_flows';
END
GO

-- Synthetic forecasts probabilísticos
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='enverus' AND TABLE_NAME='synthetic_forecasts')
BEGIN
    CREATE TABLE enverus.synthetic_forecasts (
        fecha         DATETIME NOT NULL,
        dataset       VARCHAR(10) NOT NULL,  -- lmp_da, lmp_rt, as_da, as_rt, rtrdpa
        entity        VARCHAR(50) NOT NULL,  -- DC_L, DC_R, + otros pnodes
        as_of         DATETIME NOT NULL,     -- Timestamp de publicación
        p05           FLOAT NULL,
        p33           FLOAT NULL,
        p50           FLOAT NULL,
        p66           FLOAT NULL,
        p95           FLOAT NULL,
        PRIMARY KEY (fecha, dataset, entity, as_of)
    );
    PRINT 'Tabla creada: enverus.synthetic_forecasts';
END
GO

-- Price forecasts con bandas P25/P75
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='enverus' AND TABLE_NAME='price_forecasts')
BEGIN
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
    PRINT 'Tabla creada: enverus.price_forecasts';
END
GO

-- Ancillary services
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='enverus' AND TABLE_NAME='ancillary')
BEGIN
    CREATE TABLE enverus.ancillary (
        fecha       DATETIME NOT NULL,
        iso         VARCHAR(10) NOT NULL,
        market      VARCHAR(5) NOT NULL,
        as_type     VARCHAR(20) NOT NULL,
        price       FLOAT NULL,
        cleared_mw  FLOAT NULL,
        PRIMARY KEY (fecha, iso, market, as_type)
    );
    PRINT 'Tabla creada: enverus.ancillary';
END
GO

-- =============================================================================
-- Weather Schema
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA='weather' AND TABLE_NAME='observations')
BEGIN
    CREATE TABLE weather.observations (
        fecha            DATETIME NOT NULL,
        city_code        VARCHAR(10) NOT NULL,  -- TIJ, MXL, HOU, DAL, etc.
        temperature_c    FLOAT NULL,
        windspeed_kmh    FLOAT NULL,
        direct_radiation FLOAT NULL,
        diffuse_radiation FLOAT NULL,
        PRIMARY KEY (fecha, city_code)
    );
    PRINT 'Tabla creada: weather.observations';
END
GO

-- =============================================================================
-- Views backward compatible (para no romper código legacy)
-- =============================================================================

-- View: weather.observations → dbo.TEMPERATURAS
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.VIEWS
               WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='v_temperaturas_new')
BEGIN
    EXEC('
    CREATE VIEW dbo.v_temperaturas_new AS
    SELECT
        fecha,
        city_code,
        temperature_c   AS TEMP_C,
        windspeed_kmh   AS VIENTO_KMH,
        direct_radiation AS RAD_DIR,
        diffuse_radiation AS RAD_DIF
    FROM weather.observations
    ');
    PRINT 'View creada: dbo.v_temperaturas_new';
END
GO

PRINT '=== 04_new_tables.sql completado ===';
GO
