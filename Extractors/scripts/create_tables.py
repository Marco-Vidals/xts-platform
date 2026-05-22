"""
Crea todos los schemas y tablas nuevas de la arquitectura Marco.
Idempotente: puede correrse múltiples veces.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from etl.base.db import get_connection

SCHEMAS_NEEDED = ["ercot", "caiso", "cenace", "enverus", "weather", "trading", "backoffice"]

TABLES = [
    ("dbo", "etl_log", """
        CREATE TABLE dbo.etl_log (
            id              INT IDENTITY PRIMARY KEY,
            run_date        DATETIME NOT NULL DEFAULT GETDATE(),
            source          VARCHAR(20) NOT NULL,
            extractor       VARCHAR(50) NOT NULL,
            status          VARCHAR(10) NOT NULL,
            rows_extracted  INT NULL,
            rows_inserted   INT NULL,
            rows_updated    INT NULL,
            duration_sec    FLOAT NULL,
            error_message   VARCHAR(2000) NULL,
            fecha_ini       DATE NULL,
            fecha_fin       DATE NULL
        )
    """),
    ("ercot", "prices", """
        CREATE TABLE ercot.prices (
            fecha  DATETIME NOT NULL, node VARCHAR(30) NOT NULL,
            market VARCHAR(5) NOT NULL, lmp FLOAT NULL,
            PRIMARY KEY (fecha, node, market)
        )
    """),
    ("ercot", "fuel_mix", """
        CREATE TABLE ercot.fuel_mix (
            fecha DATETIME NOT NULL, fuel_type VARCHAR(20) NOT NULL,
            gen_mw FLOAT NULL, PRIMARY KEY (fecha, fuel_type)
        )
    """),
    ("ercot", "ordc", """
        CREATE TABLE ercot.ordc (
            fecha DATETIME NOT NULL, adder_rt FLOAT NULL,
            PRIMARY KEY (fecha)
        )
    """),
    ("ercot", "ancillary", """
        CREATE TABLE ercot.ancillary (
            fecha DATETIME NOT NULL, market VARCHAR(5) NOT NULL,
            as_type VARCHAR(20) NOT NULL, price FLOAT NULL, cleared_mw FLOAT NULL,
            PRIMARY KEY (fecha, market, as_type)
        )
    """),
    ("ercot", "binding_constraints", """
        CREATE TABLE ercot.binding_constraints (
            fecha DATETIME NOT NULL, constraint_name VARCHAR(100) NOT NULL,
            shadow_price FLOAT NULL, PRIMARY KEY (fecha, constraint_name)
        )
    """),
    ("ercot", "load", """
        CREATE TABLE ercot.load (
            fecha DATETIME NOT NULL, zone VARCHAR(20) NOT NULL,
            data_type VARCHAR(10) NOT NULL, load_mw FLOAT NULL,
            PRIMARY KEY (fecha, zone, data_type)
        )
    """),
    ("ercot", "solar", """
        CREATE TABLE ercot.solar (
            fecha DATETIME NOT NULL, data_type VARCHAR(10) NOT NULL,
            gen_mw FLOAT NULL, PRIMARY KEY (fecha, data_type)
        )
    """),
    ("ercot", "wind", """
        CREATE TABLE ercot.wind (
            fecha DATETIME NOT NULL, region VARCHAR(20) NOT NULL,
            data_type VARCHAR(10) NOT NULL, gen_mw FLOAT NULL,
            PRIMARY KEY (fecha, region, data_type)
        )
    """),
    ("caiso", "prices", """
        CREATE TABLE caiso.prices (
            fecha DATETIME NOT NULL, node VARCHAR(50) NOT NULL,
            market VARCHAR(5) NOT NULL, lmp FLOAT NULL,
            energy FLOAT NULL, congestion FLOAT NULL, loss FLOAT NULL,
            PRIMARY KEY (fecha, node, market)
        )
    """),
    ("caiso", "ancillary", """
        CREATE TABLE caiso.ancillary (
            fecha DATETIME NOT NULL, market VARCHAR(5) NOT NULL,
            as_type VARCHAR(20) NOT NULL, price FLOAT NULL, cleared_mw FLOAT NULL,
            PRIMARY KEY (fecha, market, as_type)
        )
    """),
    ("cenace", "pml_zonas", """
        CREATE TABLE cenace.pml_zonas (
            fecha DATETIME NOT NULL, sistema VARCHAR(5) NOT NULL,
            zona VARCHAR(20) NOT NULL, mercado VARCHAR(5) NOT NULL,
            pml FLOAT NULL, componente_energia FLOAT NULL,
            componente_congestion FLOAT NULL, componente_perdidas FLOAT NULL,
            PRIMARY KEY (fecha, sistema, zona, mercado)
        )
    """),
    ("cenace", "pml_nodos_p", """
        CREATE TABLE cenace.pml_nodos_p (
            fecha DATETIME NOT NULL, nodo VARCHAR(20) NOT NULL,
            mercado VARCHAR(5) NOT NULL, pml FLOAT NULL,
            componente_energia FLOAT NULL, componente_congestion FLOAT NULL,
            componente_perdidas FLOAT NULL,
            PRIMARY KEY (fecha, nodo, mercado)
        )
    """),
    ("cenace", "demanda", """
        CREATE TABLE cenace.demanda (
            fecha DATETIME NOT NULL, sistema VARCHAR(5) NOT NULL,
            zona VARCHAR(20) NOT NULL, data_type VARCHAR(10) NOT NULL,
            demanda_mw FLOAT NULL, PRIMARY KEY (fecha, sistema, zona, data_type)
        )
    """),
    ("cenace", "cross_border", """
        CREATE TABLE cenace.cross_border (
            fecha DATETIME NOT NULL, enlace VARCHAR(30) NOT NULL,
            capacidad_mw FLOAT NULL, importacion_mw FLOAT NULL,
            exportacion_mw FLOAT NULL, deficit_mw FLOAT NULL, excedente_mw FLOAT NULL,
            PRIMARY KEY (fecha, enlace)
        )
    """),
    ("enverus", "renewable_forecasts", """
        CREATE TABLE enverus.renewable_forecasts (
            fecha DATETIME NOT NULL, iso VARCHAR(10) NOT NULL,
            resource_type VARCHAR(10) NOT NULL, region VARCHAR(30) NOT NULL,
            model VARCHAR(20) NOT NULL, gen_mw FLOAT NULL,
            PRIMARY KEY (fecha, iso, resource_type, region, model)
        )
    """),
    ("enverus", "synthetic_forecasts", """
        CREATE TABLE enverus.synthetic_forecasts (
            fecha DATETIME NOT NULL, dataset VARCHAR(10) NOT NULL,
            entity VARCHAR(50) NOT NULL, as_of DATETIME NOT NULL,
            p05 FLOAT NULL, p33 FLOAT NULL, p50 FLOAT NULL,
            p66 FLOAT NULL, p95 FLOAT NULL,
            PRIMARY KEY (fecha, dataset, entity, as_of)
        )
    """),
    ("enverus", "price_forecasts", """
        CREATE TABLE enverus.price_forecasts (
            fecha DATETIME NOT NULL, iso VARCHAR(10) NOT NULL,
            node VARCHAR(50) NOT NULL, market VARCHAR(5) NOT NULL,
            forecast_type VARCHAR(15) NOT NULL, lmp FLOAT NULL,
            lmp_p25 FLOAT NULL, lmp_p75 FLOAT NULL,
            PRIMARY KEY (fecha, iso, node, market, forecast_type)
        )
    """),
    ("enverus", "outages", """
        CREATE TABLE enverus.outages (
            fecha DATETIME NOT NULL, iso VARCHAR(10) NOT NULL,
            outage_type VARCHAR(20) NOT NULL, capacity_mw FLOAT NULL,
            PRIMARY KEY (fecha, iso, outage_type)
        )
    """),
    ("enverus", "grid_conditions", """
        CREATE TABLE enverus.grid_conditions (
            fecha DATETIME NOT NULL, iso VARCHAR(10) NOT NULL,
            frequency_hz FLOAT NULL, prc_mw FLOAT NULL,
            operating_reserves FLOAT NULL, dam_lambda FLOAT NULL, sced_lambda FLOAT NULL,
            PRIMARY KEY (fecha, iso)
        )
    """),
    ("enverus", "load", """
        CREATE TABLE enverus.load (
            fecha DATETIME NOT NULL, iso VARCHAR(10) NOT NULL,
            zone_type VARCHAR(15) NOT NULL, zone_name VARCHAR(30) NOT NULL,
            data_type VARCHAR(15) NOT NULL, load_mw FLOAT NULL,
            PRIMARY KEY (fecha, iso, zone_type, zone_name, data_type)
        )
    """),
    ("enverus", "tie_flows", """
        CREATE TABLE enverus.tie_flows (
            fecha DATETIME NOT NULL, iso VARCHAR(10) NOT NULL,
            interface_id VARCHAR(50) NOT NULL, flow_mw FLOAT NULL,
            PRIMARY KEY (fecha, iso, interface_id)
        )
    """),
    ("enverus", "ancillary", """
        CREATE TABLE enverus.ancillary (
            fecha DATETIME NOT NULL, iso VARCHAR(10) NOT NULL,
            market VARCHAR(5) NOT NULL, as_type VARCHAR(20) NOT NULL,
            price FLOAT NULL, cleared_mw FLOAT NULL,
            PRIMARY KEY (fecha, iso, market, as_type)
        )
    """),
    ("enverus", "cop_hsl", """
        CREATE TABLE enverus.cop_hsl (
            fecha DATETIME NOT NULL, iso VARCHAR(10) NOT NULL,
            node VARCHAR(50) NOT NULL, data_type VARCHAR(15) NOT NULL,
            value FLOAT NULL, PRIMARY KEY (fecha, iso, node, data_type)
        )
    """),
    ("weather", "observations", """
        CREATE TABLE weather.observations (
            fecha DATETIME NOT NULL, city_code VARCHAR(10) NOT NULL,
            temperature_c FLOAT NULL, windspeed_kmh FLOAT NULL,
            direct_radiation FLOAT NULL, diffuse_radiation FLOAT NULL,
            PRIMARY KEY (fecha, city_code)
        )
    """),
]


if __name__ == "__main__":
    conn   = get_connection("XTS")
    cursor = conn.cursor()

    # 1. Crear schemas faltantes
    cursor.execute("SELECT name FROM sys.schemas")
    existing_schemas = {r[0] for r in cursor.fetchall()}
    for s in SCHEMAS_NEEDED:
        if s not in existing_schemas:
            cursor.execute(f"CREATE SCHEMA [{s}]")
            conn.commit()
            print(f"Schema creado: {s}")

    # 2. Crear tablas
    created = skipped = errors = 0
    for schema, table, ddl in TABLES:
        cursor.execute(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=? AND TABLE_NAME=?",
            schema, table
        )
        if cursor.fetchone()[0]:
            skipped += 1
        else:
            try:
                cursor.execute(ddl)
                conn.commit()
                print(f"  Tabla creada: {schema}.{table}")
                created += 1
            except Exception as e:
                print(f"  ERROR {schema}.{table}: {e}")
                errors += 1

    cursor.close()
    conn.close()
    print(f"\n=== Resultado: {created} creadas, {skipped} existentes, {errors} errores ===")
