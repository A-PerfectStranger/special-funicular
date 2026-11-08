-- SYNTHETIC LOCAL ONLY. Idempotent upgrade of existing E0 development volumes.
DO $$
DECLARE item record;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='retiro_evidence_writer') THEN
    CREATE ROLE retiro_evidence_writer NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
  END IF;
  FOR item IN SELECT * FROM (VALUES
    ('retiro_school_read','synthetic-school-read-only'),
    ('retiro_system_read','synthetic-system-read-only'),
    ('retiro_importer','synthetic-importer-only'),
    ('retiro_archiver','synthetic-archiver-only'),
    ('retiro_notifier','synthetic-notifier-only')
  ) AS roles(name,password) LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=item.name) THEN
      EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE',item.name,item.password);
    END IF;
  END LOOP;
END $$;
GRANT retiro_evidence_writer TO retiro_migrator;
GRANT CONNECT ON DATABASE retiro TO retiro_school_read, retiro_system_read, retiro_importer, retiro_archiver, retiro_notifier;
GRANT USAGE ON SCHEMA public TO retiro_school_read, retiro_system_read, retiro_importer, retiro_archiver, retiro_notifier;
GRANT USAGE, CREATE ON SCHEMA public TO retiro_evidence_writer;
