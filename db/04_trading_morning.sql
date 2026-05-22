-- =============================================================================
-- Módulo Morning Offers — tablas para el flujo de ofertas diarias XTS
-- Contrapartes, fees, rutas y registro de ofertas mañana
-- Ejecutar en: XTS database
-- =============================================================================

USE XTS;
GO

-- ══════════════════════════════════════════════════════════════════════════════
-- 1. trading.counterparties — contrapartes configurables
-- ══════════════════════════════════════════════════════════════════════════════
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'counterparties'
)
BEGIN
    CREATE TABLE trading.counterparties (
        id              INT IDENTITY(1,1) PRIMARY KEY,
        code            VARCHAR(20)    NOT NULL UNIQUE,
        name            VARCHAR(100)   NOT NULL,
        -- Delta en USD/MWh aplicado al break-even de C1
        -- IMPO: precio = (BE_c1 + delta + fees_impo) * TDC
        -- EXPO: precio = (BE_c1 - delta - fees_expo) * TDC
        price_delta_usd DECIMAL(10,4)  NOT NULL DEFAULT 0,
        active          BIT            NOT NULL DEFAULT 1,
        sort_order      INT            NOT NULL DEFAULT 1,
        created_at      DATETIME       NOT NULL DEFAULT GETDATE()
    );

    INSERT INTO trading.counterparties (code, name, price_delta_usd, sort_order) VALUES
    ('MFT',   'MFT',   0, 1),
    ('SHELL', 'Shell', 3, 2),
    ('BETM',  'BETM',  3, 3);

    PRINT 'trading.counterparties creada e inicializada (MFT / Shell / BETM)';
END
ELSE
    PRINT 'trading.counterparties ya existe — sin cambios';
GO

-- ══════════════════════════════════════════════════════════════════════════════
-- 2. trading.fees — fees configurables por tipo
-- ══════════════════════════════════════════════════════════════════════════════
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'fees'
)
BEGIN
    CREATE TABLE trading.fees (
        id         INT IDENTITY(1,1) PRIMARY KEY,
        fee_type   VARCHAR(50)   NOT NULL UNIQUE,  -- IMPORT, EXPORT, CARBON, SLEEVE
        fee_usd    DECIMAL(10,4) NOT NULL,
        active     BIT           NOT NULL DEFAULT 1,
        created_at DATETIME      NOT NULL DEFAULT GETDATE()
    );

    INSERT INTO trading.fees (fee_type, fee_usd) VALUES
    ('IMPORT', 20.0),
    ('EXPORT', 15.0),
    ('CARBON',  1.0),
    ('SLEEVE',  3.0);

    PRINT 'trading.fees creada — IMPORT:20 EXPORT:15 CARBON:1 SLEEVE:3';
END
ELSE
    PRINT 'trading.fees ya existe — sin cambios';
GO

-- ══════════════════════════════════════════════════════════════════════════════
-- 3. trading.paths — rutas frontera configurables
-- ══════════════════════════════════════════════════════════════════════════════
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'paths'
)
BEGIN
    CREATE TABLE trading.paths (
        id      INT IDENTITY(1,1) PRIMARY KEY,
        code    VARCHAR(20)  NOT NULL UNIQUE,
        name    VARCHAR(100),
        market  VARCHAR(20),   -- CAISO, ERCOT
        us_node VARCHAR(50),   -- nodo lado USA
        mx_node VARCHAR(50),   -- nodo lado México (CENACE)
        active  BIT NOT NULL DEFAULT 1
    );

    INSERT INTO trading.paths (code, name, market, us_node, mx_node) VALUES
    ('ROA_IVY',  'ROA — IVY',              'CAISO', 'ROA',  'IVY'),
    ('TJI_OMS',  'TJI — OMS',              'CAISO', 'TJI',  'OMS'),
    ('DC_L_LAA', 'DC_L — LAA (Laredo)',    'ERCOT', 'DC_L', 'LAA'),
    ('DC_R_RRD', 'DC_R — RRD (Río Grande)','ERCOT', 'DC_R', 'RRD');

    PRINT 'trading.paths creada — ROA_IVY / TJI_OMS / DC_L_LAA / DC_R_RRD';
END
ELSE
    PRINT 'trading.paths ya existe — sin cambios';
GO

-- ══════════════════════════════════════════════════════════════════════════════
-- 4. trading.morning_offers — cabecera de oferta por hora/tier/ruta/dirección
-- ══════════════════════════════════════════════════════════════════════════════
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'morning_offers'
)
BEGIN
    CREATE TABLE trading.morning_offers (
        id           INT IDENTITY(1,1) PRIMARY KEY,
        trade_date   DATE         NOT NULL,
        path_id      INT          NOT NULL REFERENCES trading.paths(id),
        direction    VARCHAR(5)   NOT NULL,   -- IMPO / EXPO
        hour_ending  TINYINT      NOT NULL,   -- 1-24
        tier         TINYINT      NOT NULL,   -- 1, 2, 3
        tdc          DECIMAL(10,6) NOT NULL,  -- tipo de cambio del día
        be_usd_c1    DECIMAL(10,4) NOT NULL,  -- break-even USD ingresado (referencia C1)
        -- Snapshot de fees usados al guardar (para auditoría)
        fee_impo     DECIMAL(10,4),
        fee_expo     DECIMAL(10,4),
        fee_carbon   DECIMAL(10,4),
        fee_sleeve   DECIMAL(10,4),
        created_at   DATETIME     NOT NULL DEFAULT GETDATE(),
        CONSTRAINT uq_morning_offer
            UNIQUE (trade_date, path_id, direction, hour_ending, tier)
    );

    PRINT 'trading.morning_offers creada';
END
ELSE
    PRINT 'trading.morning_offers ya existe — sin cambios';
GO

-- ══════════════════════════════════════════════════════════════════════════════
-- 5. trading.morning_offer_lines — detalle por contraparte
-- ══════════════════════════════════════════════════════════════════════════════
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'morning_offer_lines'
)
BEGIN
    CREATE TABLE trading.morning_offer_lines (
        id        INT IDENTITY(1,1) PRIMARY KEY,
        offer_id  INT           NOT NULL REFERENCES trading.morning_offers(id),
        cp_id     INT           NOT NULL REFERENCES trading.counterparties(id),
        volume_mw DECIMAL(10,4) NOT NULL DEFAULT 0,
        be_usd    DECIMAL(10,4) NOT NULL,   -- break-even calculado para esta contraparte
        price_mxn DECIMAL(10,4),            -- precio en MXN calculado
        created_at DATETIME     NOT NULL DEFAULT GETDATE(),
        CONSTRAINT uq_offer_line UNIQUE (offer_id, cp_id)
    );

    PRINT 'trading.morning_offer_lines creada';
END
ELSE
    PRINT 'trading.morning_offer_lines ya existe — sin cambios';
GO

PRINT '=== Script 04_trading_morning completado ===';
GO
