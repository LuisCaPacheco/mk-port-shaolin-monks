-- Sala MK Port: una fila por sala, vive 10 minutos.
CREATE TABLE rooms (
  code TEXT PRIMARY KEY,
  made INTEGER NOT NULL,
  version INTEGER NOT NULL,
  ip TEXT NOT NULL,
  host_key TEXT NOT NULL,
  join_key TEXT,
  host_name TEXT NOT NULL,
  join_name TEXT,
  host_addrs TEXT NOT NULL,
  join_addrs TEXT
);
CREATE TABLE used (
  ip TEXT NOT NULL,
  what TEXT NOT NULL,
  ts INTEGER NOT NULL
);
CREATE INDEX idx_used ON used (ip, what, ts);
