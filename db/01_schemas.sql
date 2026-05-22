-- =============================================================================
-- DIA 5: Crear esquemas para organizar la BD XTS
-- Ejecutar en: XTS database
-- =============================================================================

USE XTS;
GO

-- Esquemas por mercado / función
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'ercot')
    EXEC('CREATE SCHEMA ercot');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'caiso')
    EXEC('CREATE SCHEMA caiso');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'cenace')
    EXEC('CREATE SCHEMA cenace');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'guatemala')
    EXEC('CREATE SCHEMA guatemala');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'trading')
    EXEC('CREATE SCHEMA trading');
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'backoffice')
    EXEC('CREATE SCHEMA backoffice');
GO

PRINT 'Esquemas creados: ercot, caiso, cenace, guatemala, trading, backoffice';
GO
