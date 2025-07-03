#!/bin/bash

# --- Configuration ---
SQLITE_DB="backend/data/webui.db"
PSQL_CONN_STRING="postgresql://openwebui:password@localhost:5171/openwebui"
DUMP_DIR="pg_dump"

# --- Stop on error ---
set -e

# --- 1. Create Schema in PostgreSQL ---
# This assumes your Open-WebUI backend can create the schema on an empty DB.
# Make sure your target DB is empty and then start the backend once to do this.
echo "IMPORTANT: Ensure your PostgreSQL database is created, empty, and that you have run the Open-WebUI backend at least once to create the table schema."
read -p "Press enter to continue once the schema is ready..."

# --- 2. Export data from SQLite to CSV files ---
echo "Exporting data from SQLite to CSV files in ./${DUMP_DIR}/"
rm -rf "${DUMP_DIR}"
mkdir -p "${DUMP_DIR}"

# Get table list, excluding sqlite internal tables, alembic, and migratehistory
TABLES=$(sqlite3 "${SQLITE_DB}" "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic_version' AND name NOT LIKE 'migratehistory';")

for T in $TABLES; do
    echo "  - Exporting table: ${T}"
    # Quote the table name "${T}" to handle reserved keywords like "group"
    sqlite3 -header -csv "${SQLITE_DB}" "SELECT * FROM \"${T}\";" > "${DUMP_DIR}/${T}.csv"
done

echo "SQLite export complete."


# --- 3. Import data from CSV into PostgreSQL ---
echo "Importing data into PostgreSQL..."

for T in $TABLES; do
    echo "  - Importing table: ${T}"
    psql "${PSQL_CONN_STRING}" -c "\copy \"${T}\" FROM '${DUMP_DIR}/${T}.csv' WITH (FORMAT csv, HEADER true);"
done

# Handle alembic version separately
echo "  - Setting alembic version..."
ALEMBIC_VERSION=$(sqlite3 "${SQLITE_DB}" "SELECT version_num FROM alembic_version;")
psql "${PSQL_CONN_STRING}" -c "TRUNCATE alembic_version; INSERT INTO alembic_version (version_num) VALUES ('${ALEMBIC_VERSION}');"


echo "Migration complete."
echo "IMPORTANT: You may need to manually update sequences for primary keys if you encounter issues with new records."