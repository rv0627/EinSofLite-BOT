#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
until pg_isready -U postgres; do
  echo "Waiting for PostgreSQL to start..."
  sleep 2
done

# Force set the password for our application user
psql -U postgres -d "${POSTGRES_DB}" -c "
DO \$\$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = '${POSTGRES_USER}') THEN
    ALTER USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
    RAISE NOTICE 'Password updated for user: ${POSTGRES_USER}';
  ELSE
    CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};
    RAISE NOTICE 'User created: ${POSTGRES_USER}';
  END IF;
END
\$\$;
"

echo "✅ Database user '${POSTGRES_USER}' password synced successfully."
