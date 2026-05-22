-- =============================================================================
-- DIA 5: Convertir Morning / Afternoon de snapshot a histórico
--
-- ESTRATEGIA:
--   1. Agregar columna fecha_operacion (DATE) = el día de trading
--   2. Crear tablas históricas en esquema trading con índice (fecha_operacion, hora)
--   3. Las tablas dbo.Morning_* originales se mantienen como snapshot (24 rows)
--      para compatibilidad con código existente.
--   4. El ETL escribirá a AMBAS: snapshot (DELETE+INSERT) e histórico (INSERT).
--
-- Ejecutar en: XTS database
-- =============================================================================

USE XTS;
GO

-- ── Morning ERCOT histórico ───────────────────────────────────────────────────
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'morning_ercot_hist'
)
BEGIN
    -- Copiar estructura de Morning_ERCOT y agregar fecha_operacion
    SELECT TOP 0
        CAST(GETDATE() AS DATE) AS fecha_operacion,
        *
    INTO trading.morning_ercot_hist
    FROM dbo.Morning_ERCOT;

    ALTER TABLE trading.morning_ercot_hist
        ADD CONSTRAINT PK_morning_ercot_hist
        PRIMARY KEY (fecha_operacion, fecha);

    PRINT 'Tabla trading.morning_ercot_hist creada';
END
GO

-- ── Morning CAISO histórico ───────────────────────────────────────────────────
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'morning_caiso_hist'
)
BEGIN
    SELECT TOP 0
        CAST(GETDATE() AS DATE) AS fecha_operacion,
        *
    INTO trading.morning_caiso_hist
    FROM dbo.Morning_CAISO;

    ALTER TABLE trading.morning_caiso_hist
        ADD CONSTRAINT PK_morning_caiso_hist
        PRIMARY KEY (fecha_operacion, fecha);

    PRINT 'Tabla trading.morning_caiso_hist creada';
END
GO

-- ── Morning GTM histórico ─────────────────────────────────────────────────────
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'morning_gtm_hist'
)
BEGIN
    SELECT TOP 0
        CAST(GETDATE() AS DATE) AS fecha_operacion,
        *
    INTO trading.morning_gtm_hist
    FROM dbo.Morning_GTM;

    ALTER TABLE trading.morning_gtm_hist
        ADD CONSTRAINT PK_morning_gtm_hist
        PRIMARY KEY (fecha_operacion, fecha);

    PRINT 'Tabla trading.morning_gtm_hist creada';
END
GO

-- ── Afternoon histórico ───────────────────────────────────────────────────────
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'afternoon_hist'
)
BEGIN
    SELECT TOP 0
        CAST(GETDATE() AS DATE) AS fecha_operacion,
        *
    INTO trading.afternoon_hist
    FROM dbo.Afternoon;

    ALTER TABLE trading.afternoon_hist
        ADD CONSTRAINT PK_afternoon_hist
        PRIMARY KEY (fecha_operacion, fecha);

    PRINT 'Tabla trading.afternoon_hist creada';
END
GO

-- ── Tabla de trades ───────────────────────────────────────────────────────────
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = 'trading' AND TABLE_NAME = 'trades'
)
BEGIN
    CREATE TABLE trading.trades (
        id               INT IDENTITY(1,1) PRIMARY KEY,
        fecha_operacion  DATE         NOT NULL,
        mercado          VARCHAR(20)  NOT NULL,  -- ERCOT, CAISO, CENACE, GTM
        direccion        VARCHAR(10)  NOT NULL,  -- IMPORT, EXPORT
        nodo             VARCHAR(50)  NOT NULL,
        hora             TINYINT      NOT NULL,  -- 1-24
        mw               FLOAT        NOT NULL,
        precio_da        FLOAT        NULL,
        precio_rt        FLOAT        NULL,
        contraparte      VARCHAR(100) NULL,
        notas            VARCHAR(500) NULL,
        created_at       DATETIME     DEFAULT GETDATE()
    );
    PRINT 'Tabla trading.trades creada';
END
GO

-- ── Vista histórico Morning ERCOT ─────────────────────────────────────────────
CREATE OR ALTER VIEW trading.v_morning_ercot_hist AS
    SELECT * FROM trading.morning_ercot_hist;
GO

CREATE OR ALTER VIEW trading.v_morning_caiso_hist AS
    SELECT * FROM trading.morning_caiso_hist;
GO

CREATE OR ALTER VIEW trading.v_morning_gtm_hist AS
    SELECT * FROM trading.morning_gtm_hist;
GO

CREATE OR ALTER VIEW trading.v_afternoon_hist AS
    SELECT * FROM trading.afternoon_hist;
GO

PRINT 'Script 03 completado: tablas históricas y trading.trades creadas';
GO
