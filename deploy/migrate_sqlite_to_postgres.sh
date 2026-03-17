#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   SQLITE_PATH=/var/www/care4u/instance/site.db \
#   PG_URI=postgresql://care4u_user:password@db-endpoint:5432/care4u \
#   bash deploy/migrate_sqlite_to_postgres.sh

if [[ -z "${SQLITE_PATH:-}" || -z "${PG_URI:-}" ]]; then
  echo "ERROR: SQLITE_PATH and PG_URI are required"
  exit 1
fi

sudo apt update -y
sudo apt install -y pgloader

echo "Migrating ${SQLITE_PATH} -> ${PG_URI}"
pgloader "sqlite://${SQLITE_PATH}" "${PG_URI}"

echo "Migration complete. Validate data before switching production traffic."
