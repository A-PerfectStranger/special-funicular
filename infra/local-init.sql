-- Exclusivamente sintetico. El superusuario solo inicializa roles y bases locales.
CREATE ROLE app_migrator LOGIN PASSWORD 'synthetic-migrator' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE app_runtime LOGIN PASSWORD 'synthetic-runtime' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE DATABASE retiro_synthetic OWNER app_migrator;
CREATE DATABASE test_retiro_synthetic OWNER app_migrator;
\connect retiro_synthetic
REVOKE ALL ON DATABASE retiro_synthetic FROM PUBLIC;
GRANT CONNECT ON DATABASE retiro_synthetic TO app_runtime;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_runtime;
-- E0 solo contiene tablas operativas de sesiones. En E1, grants por tabla/funcion;
-- NO crear evidencia bajo estos default privileges.
\connect test_retiro_synthetic
REVOKE ALL ON DATABASE test_retiro_synthetic FROM PUBLIC;
GRANT CONNECT ON DATABASE test_retiro_synthetic TO app_runtime;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_runtime;
