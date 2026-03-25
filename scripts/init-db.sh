#!/bin/bash
set -e

echo "Initializing application database with dynamic credentials..."

# Get variables from environment (set by docker-compose from .env)
DB_USER=${APP_DB_USER}
DB_PASSWORD=${APP_DB_PASSWORD}
DB_NAME=${POSTGRES_DB}

echo "Database User: $DB_USER"
echo "Database Name: $DB_NAME"

# Generate and execute SQL dynamically
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" << EOSQL
-- Create user dynamically with variables
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
    CREATE ROLE "$DB_USER" WITH LOGIN ENCRYPTED PASSWORD '$DB_PASSWORD';
    ALTER ROLE "$DB_USER" CREATEDB CREATEROLE;
    RAISE NOTICE 'User $DB_USER created successfully';
  ELSE
    ALTER ROLE "$DB_USER" WITH ENCRYPTED PASSWORD '$DB_PASSWORD';
    RAISE NOTICE 'User $DB_USER already exists, password updated';
  END IF;
END
\$\$;

-- Set database ownership
ALTER DATABASE "$DB_NAME" OWNER TO "$DB_USER";

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE "$DB_NAME" TO "$DB_USER";
GRANT ALL PRIVILEGES ON SCHEMA public TO "$DB_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "$DB_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "$DB_USER";

-- Verify
SELECT 'Database initialized successfully' as status;
EOSQL

echo "✓ Database initialization complete"
