-- ============================================
-- 1) Create application user
-- ============================================
CREATE USER openmuc_user WITH PASSWORD 'openmuc';

-- Allow access to the database
GRANT ALL PRIVILEGES ON DATABASE openmuc TO openmuc_user;

-- IMPORTANT: allow openmuc_user to create tables in public schema
GRANT ALL ON SCHEMA public TO openmuc_user;


-- ============================================
-- 2) Switch into the openmuc database
-- ============================================
\connect openmuc

-- Act as openmuc_user for table creation
SET ROLE openmuc_user;


-- ============================================
-- 3) Create latest_values table
-- ============================================
CREATE TABLE IF NOT EXISTS latest_values (
    channelid      VARCHAR(255) PRIMARY KEY,
    value_type     VARCHAR(1) NOT NULL,
    value_double   DOUBLE PRECISION,
    value_string   TEXT,
    value_boolean  BOOLEAN,
    updated_at     TIMESTAMP NOT NULL DEFAULT NOW()
);


-- ============================================
-- 4) Create soh_schedule table
-- ============================================
CREATE TABLE IF NOT EXISTS soh_schedule (
    id              SERIAL PRIMARY KEY,
    str_id          VARCHAR(255),
    used_q          DOUBLE PRECISION,
    soh             DOUBLE PRECISION,
    soc_before      DOUBLE PRECISION,
    soc_after       DOUBLE PRECISION,
    current         DOUBLE PRECISION,
    state           INTEGER,
    status          INTEGER,
    start_datetime  TIMESTAMP,
    update_datetime TIMESTAMP,
    end_datetime    TIMESTAMP
);


-- ============================================
-- 5) Reset role back to postgres (optional)
-- ============================================
RESET ROLE;


-- ============================================
-- 6) Default privileges for future tables
-- ============================================
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO openmuc_user;


-- ============================================
-- 7) Insert default account values
-- ============================================
INSERT INTO latest_values (channelid, value_type, value_string, updated_at)
VALUES
    ('account_1_username', 'S', 'admin', NOW()),
    ('account_1_password', 'S', 'admin', NOW())
ON CONFLICT (channelid) DO UPDATE
SET value_string = EXCLUDED.value_string,
    value_type   = EXCLUDED.value_type,
    updated_at   = EXCLUDED.updated_at;
