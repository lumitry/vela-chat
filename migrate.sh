#!/bin/bash

# --- Configuration ---
SQLITE_DB="backend/data/webui.db"
PSQL_CONN_STRING="postgresql://openwebui:password@localhost:5171/openwebui"
DUMP_DIR="pg_dump"

# --- Stop on error ---
set -e

# --- 1. Create Schema in PostgreSQL ---
echo "IMPORTANT: Ensure your PostgreSQL database is created, empty, and that you have run the Open-WebUI backend at least once to create the table schema."
read -p "Press enter to continue once the schema is ready..."

# --- 2. Export data from SQLite to CSV files ---
echo "Exporting data from SQLite to CSV files in ./${DUMP_DIR}/"
rm -rf "${DUMP_DIR}"
mkdir -p "${DUMP_DIR}"

# Get table list, excluding special-cased tables and metadata tables
TABLES=$(sqlite3 "${SQLITE_DB}" "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('chat', 'user', 'feedback', 'sqlite_sequence', 'alembic_version', 'migratehistory');")

# Export regular tables with a simple SELECT *
for T in $TABLES; do
    # Check if table exists in PostgreSQL before exporting
    if psql "${PSQL_CONN_STRING}" -c "\d \"${T}\"" > /dev/null 2>&1; then
        echo "  - Exporting table: ${T}"
        sqlite3 -header -csv "${SQLITE_DB}" "SELECT * FROM \"${T}\";" > "${DUMP_DIR}/${T}.csv"
    else
        echo "  - Skipping table ${T}: does not exist in destination."
    fi
done

# --- Handle tables with timestamps as special cases ---

echo "  - Exporting table: chat (with timestamp conversion)"
sqlite3 -header -csv "${SQLITE_DB}" \
"SELECT id, user_id, title, chat,
       CASE WHEN created_at IS NOT NULL AND created_at != '' THEN datetime(created_at, 'unixepoch') ELSE NULL END AS created_at,
       CASE WHEN updated_at IS NOT NULL AND updated_at != '' THEN datetime(updated_at, 'unixepoch') ELSE NULL END AS updated_at,
       share_id, archived
 FROM chat;" > "${DUMP_DIR}/chat.csv"

echo "  - Exporting table: user (with timestamp conversion)"
sqlite3 -header -csv "${SQLITE_DB}" \
"SELECT id, name, email, role, profile_image_url,
       CASE WHEN created_at IS NOT NULL AND created_at != '' THEN datetime(created_at, 'unixepoch') ELSE NULL END AS created_at,
       CASE WHEN updated_at IS NOT NULL AND updated_at != '' THEN datetime(updated_at, 'unixepoch') ELSE NULL END AS updated_at,
       CASE WHEN last_active_at IS NOT NULL AND last_active_at != '' THEN datetime(last_active_at, 'unixepoch') ELSE NULL END AS last_active_at,
       api_key, settings, info, oauth_sub
 FROM \"user\";" > "${DUMP_DIR}/user.csv"

echo "  - Exporting table: feedback (with timestamp conversion)"
sqlite3 -header -csv "${SQLITE_DB}" \
"SELECT id, user_id, chat_id, message_id, model, rating,
       CASE WHEN timestamp IS NOT NULL AND timestamp != '' THEN datetime(timestamp, 'unixepoch') ELSE NULL END AS timestamp,
       comment, meta
 FROM feedback;" > "${DUMP_DIR}/feedback.csv"

echo "SQLite export complete."


# --- 3. Import data from CSV into PostgreSQL ---
echo "Importing data into PostgreSQL..."

# Rebuild the list of all tables that were actually exported
ALL_TABLES=$(ls -1 "${DUMP_DIR}" | sed 's/\.csv$//')

for T in $ALL_TABLES; do
    echo "  - Importing table: ${T}"
    psql "${PSQL_CONN_STRING}" -c "\copy \"${T}\" FROM '${DUMP_DIR}/${T}.csv' WITH (FORMAT csv, HEADER true);"
done

# Handle alembic version separately
echo "  - Setting alembic version..."
ALEMBIC_VERSION=$(sqlite3 "${SQLITE_DB}" "SELECT version_num FROM alembic_version;")
psql "${PSQL_CONN_STRING}" -c "TRUNCATE alembic_version; INSERT INTO alembic_version (version_num) VALUES ('${ALEMBIC_VERSION}');"


echo "Migration complete."
echo "IMPORTANT: You may need to manually update sequences for primary keys if you encounter issues with new records."