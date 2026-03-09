#!/bin/sh
set -e

# Run Alembic migrations before starting the API.
# In development this is optional (create_all still runs on startup),
# but in production the migration step ensures the schema is versioned.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] Running Alembic migrations ..."
    alembic upgrade head
fi

exec "$@"
