-- SQL schema for server metadata table

CREATE TABLE IF NOT EXISTS servers (
    id SERIAL PRIMARY KEY,
    ip VARCHAR(45) NOT NULL,
    port INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    region VARCHAR(16) NOT NULL,
    UNIQUE (ip, port)
);
