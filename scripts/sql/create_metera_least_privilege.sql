-- Least-privilege bootstrap for Metera application access.
-- Run as a privileged Postgres role (e.g. postgres) and customize the password.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metera_user') THEN
        CREATE ROLE metera_user LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
    END IF;
END $$;

GRANT CONNECT ON DATABASE metera TO metera_user;
GRANT USAGE ON SCHEMA public TO metera_user;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO metera_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO metera_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO metera_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO metera_user;

REVOKE CREATE ON SCHEMA public FROM metera_user;

-- Intentionally no DROP/TRUNCATE privileges are granted.
