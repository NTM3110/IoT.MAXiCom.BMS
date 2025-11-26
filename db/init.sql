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
-- 7) Insert default account / config values
-- ============================================

-- numeric config: dev_serial_comm_number = 3
INSERT INTO latest_values (channelid, value_type, value_double, updated_at)
VALUES
    ('dev_serial_comm_number', 'D', 3, NOW())
ON CONFLICT (channelid) DO UPDATE
SET value_double = EXCLUDED.value_double,
    value_type   = EXCLUDED.value_type,
    updated_at   = EXCLUDED.updated_at;

-- string configs (accounts, serial ports, site name)
INSERT INTO latest_values (channelid, value_type, value_string, updated_at)
VALUES
    ('account_1_username', 'S', 'admin', NOW()),
    ('account_1_password', 'S', 'admin', NOW()),
    ('dev_serial_comm_0', 'S', '/dev/ttyS1:RTU:SERIAL_ENCODING_RTU:9600:DATABITS_8:PARITY_NONE:STOPBITS_1:ECHO_FALSE:FLOWCONTROL_NONE:FLOWCONTROL_NONE', NOW()),
    ('dev_serial_comm_1', 'S', '/dev/ttyS7:RTU:SERIAL_ENCODING_RTU:9600:DATABITS_8:PARITY_NONE:STOPBITS_1:ECHO_FALSE:FLOWCONTROL_NONE:FLOWCONTROL_NONE', NOW()),
    ('dev_serial_comm_2', 'S', '/dev/ttyS9:RTU:SERIAL_ENCODING_RTU:9600:DATABITS_8:PARITY_NONE:STOPBITS_1:ECHO_FALSE:FLOWCONTROL_NONE:FLOWCONTROL_NONE', NOW()),
    ('site_name_1',       'S', 'Battery Monitoring System', NOW())
ON CONFLICT (channelid) DO UPDATE
SET value_string = EXCLUDED.value_string,
    value_type   = EXCLUDED.value_type,
    updated_at   = EXCLUDED.updated_at;

-- =======================================
-- 1) Total I tables
-- =======================================
CREATE TABLE str1_total_I (
    time TIMESTAMP NOT NULL,
    flag INTEGER,
    "VALUE" DOUBLE PRECISION
);

CREATE TABLE str2_total_I (
    time TIMESTAMP NOT NULL,
    flag INTEGER,
    "VALUE" DOUBLE PRECISION
);

-- =======================================
-- 2) Ambient Temperature tables
-- =======================================
CREATE TABLE str1_ambient_T (
    time TIMESTAMP NOT NULL,
    flag INTEGER,
    "VALUE" DOUBLE PRECISION
);

CREATE TABLE str2_ambient_T (
    time TIMESTAMP NOT NULL,
    flag INTEGER,
    "VALUE" DOUBLE PRECISION
);

-- =======================================
-- 3) String SOC tables
-- =======================================
CREATE TABLE str1_string_SOC (
    time TIMESTAMP NOT NULL,
    flag INTEGER,
    "VALUE" DOUBLE PRECISION
);

CREATE TABLE str2_string_SOC (
    time TIMESTAMP NOT NULL,
    flag INTEGER,
    "VALUE" DOUBLE PRECISION
);

-- =======================================
-- 4) String SOH tables
-- =======================================
CREATE TABLE str1_string_SOH (
    time TIMESTAMP NOT NULL,
    flag INTEGER,
    "VALUE" DOUBLE PRECISION
);

CREATE TABLE str2_string_SOH (
    time TIMESTAMP NOT NULL,
    flag INTEGER,
    "VALUE" DOUBLE PRECISION
);
