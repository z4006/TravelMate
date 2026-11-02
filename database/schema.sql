-- 当前阶段只建立 SQLite 初始化入口，不创建成员业务表。
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    username_key TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT,
    nickname TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'disabled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    session_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    action TEXT NOT NULL,
    target_user_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (actor_user_id) REFERENCES users (id) ON DELETE SET NULL,
    FOREIGN KEY (target_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username_key TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    failed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_login_attempts_lookup
ON login_attempts (username_key, ip_address, failed_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_actor ON audit_logs (actor_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_target ON audit_logs (target_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created ON audit_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_users_status ON users (status);
