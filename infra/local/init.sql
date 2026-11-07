-- SYNTHETIC ONLY. Never apply this file to a cloud database.
CREATE ROLE retiro_migrator LOGIN PASSWORD 'synthetic-migrator-only' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE retiro_runtime LOGIN PASSWORD 'synthetic-runtime-only' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
REVOKE ALL ON DATABASE retiro FROM PUBLIC;
GRANT CONNECT ON DATABASE retiro TO retiro_migrator, retiro_runtime;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO retiro_migrator;
GRANT USAGE ON SCHEMA public TO retiro_runtime;
