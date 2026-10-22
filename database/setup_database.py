"""
setup_database.py
-----------------
Creates the `optimization_project` MySQL database, the `cropdata` and
`fielddata` tables (with the exact column names app.py expects), and loads
crop_data.csv and Field_Data.csv into them.

Put this file in the same folder as the two CSV files and run:
    python setup_database.py

It is safe to run more than once: the two tables are dropped and rebuilt
each time, so you always end up with a clean copy of the CSV data.
"""

import os
import sys

import pandas as pd
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()  # reads the .env file (looks in this folder and parent folders)

# ---- Connection settings (must match DB_CONFIG in app.py) -------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "optimization_project")
# -----------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
CROP_CSV = os.path.join(HERE, "crop_data.csv")
FIELD_CSV = os.path.join(HERE, "Field_Data.csv")


def prepare_crop_rows():
    """Read crop_data.csv and return a list of clean tuples."""
    df = pd.read_csv(CROP_CSV, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]

    rows = []
    for _, r in df.iterrows():
        rows.append((
            str(r["Crop"]).strip(),
            float(r["Yield_t_ha"]),
            int(r["Market_Price_Rs_per_ton"]),
            int(r["Fertilizer_Use_kg_ha"]),
            int(r["Water_Use_L_ha"]),
            str(r["Type"]).strip(),
        ))
    return rows


def prepare_field_rows():
    """Read Field_Data.csv and return a list of clean tuples."""
    df = pd.read_csv(FIELD_CSV, encoding="utf-8-sig")

    # The CSV headers contain stray spaces (e.g. "Annual_ rainfall (mm)"),
    # so rename the columns by position instead of by name.
    if len(df.columns) != 10:
        raise ValueError(f"Expected 10 columns in Field_Data.csv, found {len(df.columns)}")
    df.columns = [
        "Field_id", "Soil_Type", "Annual_Rainfall", "Rainfall_Index",
        "Scarcity_Index", "Alpha", "Beta", "Gamma",
        "Key_data_source", "Representative_District",
    ]

    rows = []
    for _, r in df.iterrows():
        rows.append((
            str(r["Field_id"]).strip().upper(),
            str(r["Soil_Type"]).strip(),
            int(r["Annual_Rainfall"]),
            float(r["Rainfall_Index"]),
            float(r["Scarcity_Index"]),
            float(r["Alpha"]),
            float(r["Beta"]),
            float(r["Gamma"]),
            str(r["Key_data_source"]).strip(),
            str(r["Representative_District"]).strip(),
        ))
    return rows


CREATE_CROPDATA = """
CREATE TABLE cropdata (
    Crop VARCHAR(100) NOT NULL PRIMARY KEY,
    `Yield (t/ha)` DOUBLE NOT NULL,
    `Market Price (Rs/ton)` INT NOT NULL,
    `Fertilizer Use (kg/ha)` INT NOT NULL,
    `Water Use (L/ha)` INT NOT NULL,
    `Type` VARCHAR(100)
)
"""

CREATE_FIELDDATA = """
CREATE TABLE fielddata (
    Field_id VARCHAR(20) NOT NULL PRIMARY KEY,
    Soil_Type VARCHAR(100),
    `Annual_Rainfall (mm)` INT,
    Rainfall_Index DOUBLE,
    Scarcity_Index DOUBLE,
    Alpha DOUBLE,
    Beta DOUBLE,
    Gamma DOUBLE,
    Key_data_source VARCHAR(255),
    Representative_District VARCHAR(100)
)
"""

INSERT_CROP = """
INSERT INTO cropdata
    (Crop, `Yield (t/ha)`, `Market Price (Rs/ton)`,
     `Fertilizer Use (kg/ha)`, `Water Use (L/ha)`, `Type`)
VALUES (%s, %s, %s, %s, %s, %s)
"""

INSERT_FIELD = """
INSERT INTO fielddata
    (Field_id, Soil_Type, `Annual_Rainfall (mm)`, Rainfall_Index,
     Scarcity_Index, Alpha, Beta, Gamma, Key_data_source, Representative_District)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def main():
    for path in (CROP_CSV, FIELD_CSV):
        if not os.path.exists(path):
            print(f"ERROR: cannot find {path}")
            print("Copy crop_data.csv and Field_Data.csv into the same folder as this script.")
            sys.exit(1)

    crop_rows = prepare_crop_rows()
    field_rows = prepare_field_rows()
    print(f"Read {len(crop_rows)} crops and {len(field_rows)} fields from the CSV files.")

    connection = None
    try:
        connection = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD
        )
        cursor = connection.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
        cursor.execute(f"USE `{DB_NAME}`")

        cursor.execute("DROP TABLE IF EXISTS cropdata")
        cursor.execute("DROP TABLE IF EXISTS fielddata")
        cursor.execute(CREATE_CROPDATA)
        cursor.execute(CREATE_FIELDDATA)

        cursor.executemany(INSERT_CROP, crop_rows)
        cursor.executemany(INSERT_FIELD, field_rows)
        connection.commit()

        cursor.execute("SELECT COUNT(*) FROM cropdata")
        n_crops = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM fielddata")
        n_fields = cursor.fetchone()[0]
        cursor.execute("SELECT Field_id FROM fielddata ORDER BY Field_id")
        field_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()

        print(f"\nDatabase '{DB_NAME}' is ready.")
        print(f"  cropdata  : {n_crops} rows")
        print(f"  fielddata : {n_fields} rows")
        print(f"  Field IDs : {', '.join(field_ids)}")

    except Error as e:
        print(f"\nMySQL error: {e}")
        if getattr(e, "errno", None) == 1045:
            print("-> Wrong username or password. Check DB_USER / DB_PASSWORD in your .env file.")
        elif getattr(e, "errno", None) == 2003:
            print("-> Could not reach MySQL. Check that the MySQL service is running.")
        sys.exit(1)
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()