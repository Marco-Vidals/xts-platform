-- =============================================================================
-- DIA 5: Vistas limpias sobre las tablas existentes
-- Las vistas permiten que la app use nombres consistentes sin tocar la BD raw.
-- Ejecutar en: XTS database
-- =============================================================================

USE XTS;
GO

-- ── ERCOT ─────────────────────────────────────────────────────────────────────
CREATE OR ALTER VIEW ercot.v_precios AS
    SELECT
        fecha,
        DA_DCL, DA_DCR,
        RT_DCL, RT_DCR,
        DA_DCL_FCST, DA_DCR_FCST,
        RT_DCL_FCST, RT_DCR_FCST,
        LOAD_ERCOT,
        WIND_ERCOT
    FROM dbo.DATOS_ERCOT;
GO

CREATE OR ALTER VIEW ercot.v_pml AS
    SELECT
        fecha,
        PML_LAA, PML_RRD,
        MTR_LAA, MTR_RRD,
        PML_LAA_FCST, PML_RRD_FCST,
        LBR_FCST, MTR_LBR,
        LOAD_MX
    FROM dbo.DATOS_ERCOT;
GO

CREATE OR ALTER VIEW ercot.v_morning AS
    SELECT * FROM dbo.Morning_ERCOT;
GO

-- ── CAISO ─────────────────────────────────────────────────────────────────────
CREATE OR ALTER VIEW caiso.v_precios AS
    SELECT * FROM dbo.DATOS_CAISO;
GO

CREATE OR ALTER VIEW caiso.v_morning AS
    SELECT * FROM dbo.Morning_CAISO;
GO

-- ── CENACE ────────────────────────────────────────────────────────────────────
CREATE OR ALTER VIEW cenace.v_precios_mda AS
    SELECT
        d.fecha,
        d.hora,
        d.Sistema,
        d.Zona_Carga,
        d.PZ,
        d.PZ_ENE,
        d.PZ_PER,
        d.PZ_CNG
    FROM PML.dbo.MDA_D d;
GO

CREATE OR ALTER VIEW cenace.v_precios_mtr AS
    SELECT
        t.fecha,
        t.hora,
        t.Sistema,
        t.Nodo,
        t.PML,
        t.PML_ENE,
        t.PML_PER,
        t.PML_CNG
    FROM PML.dbo.MTR t;
GO

-- ── GUATEMALA ─────────────────────────────────────────────────────────────────
CREATE OR ALTER VIEW guatemala.v_datos AS
    SELECT
        fecha,
        PPOE,
        LBR,
        LOAD,
        IMPO_ASIG,
        EXPO_ASIG,
        FPN
    FROM dbo.GTM;
GO

CREATE OR ALTER VIEW guatemala.v_morning AS
    SELECT * FROM dbo.Morning_GTM;
GO

-- ── TRADING ───────────────────────────────────────────────────────────────────
CREATE OR ALTER VIEW trading.v_capacidades AS
    SELECT * FROM dbo.CAPACIDADES;
GO

CREATE OR ALTER VIEW trading.v_deficit_excedente AS
    SELECT * FROM dbo.DEF_EXC;
GO

CREATE OR ALTER VIEW trading.v_ofertas AS
    SELECT 'T1' AS tier, * FROM dbo.OFERTAS_T1
    UNION ALL
    SELECT 'T2', * FROM dbo.OFERTAS_T2
    UNION ALL
    SELECT 'T3', * FROM dbo.OFERTAS_T3;
GO

CREATE OR ALTER VIEW trading.v_tipo_cambio AS
    SELECT fecha, TC FROM dbo.Tipo_Cambio;
GO

CREATE OR ALTER VIEW trading.v_temperaturas AS
    SELECT * FROM dbo.TEMPERATURAS;
GO

PRINT 'Vistas creadas en esquemas: ercot, caiso, cenace, guatemala, trading';
GO
