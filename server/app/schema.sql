-- Personal Gateway Plus 初版建表脚本（数据结构冻结）
-- 对应 WEEK1_MVP.md 第3节「最小数据模型」与 MODULES.md 领域模型。
-- 全部使用 SQLite 原生类型；时间统一存 ISO8601 UTC 字符串。

PRAGMA foreign_keys = ON;

-- 1. 供应商
CREATE TABLE IF NOT EXISTS provider (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    protocol_type   TEXT NOT NULL DEFAULT 'OPENAI_COMPATIBLE',
    official_url    TEXT,
    pricing_url     TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- 2. 上游 API（API Key 加密保存）
CREATE TABLE IF NOT EXISTS upstream_endpoint (
    id                  TEXT PRIMARY KEY,
    provider_id         TEXT NOT NULL,
    display_name        TEXT NOT NULL,
    base_url            TEXT NOT NULL,
    encrypted_api_key   TEXT NOT NULL,           -- AES-GCM 密文（含 nonce），永不回显
    api_key_last_four   TEXT NOT NULL,           -- 明文后四位，用于界面核对
    default_model       TEXT,
    enabled             INTEGER NOT NULL DEFAULT 1,
    timeout_ms          INTEGER NOT NULL DEFAULT 15000,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY (provider_id) REFERENCES provider(id) ON DELETE CASCADE
);

-- 3. 模型目录
CREATE TABLE IF NOT EXISTS model_catalog_entry (
    id                  TEXT PRIMARY KEY,
    provider_id         TEXT NOT NULL,
    upstream_model_id   TEXT NOT NULL,           -- 供应商真实模型 ID
    display_name        TEXT NOT NULL,
    context_window      INTEGER,
    capabilities        TEXT,                    -- JSON 数组字符串，初版可选
    enabled             INTEGER NOT NULL DEFAULT 1,
    source_url          TEXT,
    verified_at         TEXT,
    FOREIGN KEY (provider_id) REFERENCES provider(id) ON DELETE CASCADE
);

-- 4. 价格快照（价格缺失应为 NULL，不得存 0）
CREATE TABLE IF NOT EXISTS price_snapshot (
    id                              TEXT PRIMARY KEY,
    provider_id                     TEXT NOT NULL,
    model_catalog_entry_id          TEXT NOT NULL,
    currency                        TEXT NOT NULL DEFAULT 'CNY',
    input_price_per_million_tokens  REAL,
    output_price_per_million_tokens REAL,
    source_url                      TEXT,
    effective_from                  TEXT,
    verified_at                     TEXT,
    is_current                      INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (provider_id) REFERENCES provider(id) ON DELETE CASCADE,
    FOREIGN KEY (model_catalog_entry_id) REFERENCES model_catalog_entry(id) ON DELETE CASCADE
);

-- 5. 活动
CREATE TABLE IF NOT EXISTS promotion (
    id          TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    title       TEXT NOT NULL,
    type        TEXT NOT NULL,                   -- discount / credit / price_change
    description TEXT,
    source_url  TEXT,
    starts_at   TEXT,
    ends_at     TEXT,
    status      TEXT NOT NULL DEFAULT 'verified', -- draft / verified / expired
    verified_at TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (provider_id) REFERENCES provider(id) ON DELETE CASCADE
);

-- 6. API 分组
CREATE TABLE IF NOT EXISTS api_group (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    route_key       TEXT NOT NULL UNIQUE,        -- 用于调用的唯一标识
    routing_policy  TEXT NOT NULL DEFAULT 'ORDERED_FAILOVER',
    max_attempts    INTEGER NOT NULL DEFAULT 3,
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- 7. 分组成员（同一分组 priority_rank 唯一）
CREATE TABLE IF NOT EXISTS api_group_member (
    id                    TEXT PRIMARY KEY,
    group_id              TEXT NOT NULL,
    upstream_endpoint_id  TEXT NOT NULL,
    upstream_model_name   TEXT NOT NULL,         -- 映射到的真实上游模型名
    priority_rank         INTEGER NOT NULL,
    enabled               INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT NOT NULL,
    FOREIGN KEY (group_id) REFERENCES api_group(id) ON DELETE CASCADE,
    FOREIGN KEY (upstream_endpoint_id) REFERENCES upstream_endpoint(id) ON DELETE CASCADE,
    UNIQUE (group_id, priority_rank)
);

-- 8. 网关请求
CREATE TABLE IF NOT EXISTS gateway_request (
    request_id               TEXT PRIMARY KEY,
    route_key                TEXT NOT NULL,
    started_at               TEXT NOT NULL,
    ended_at                 TEXT,
    final_status             TEXT,               -- success / all_failed / client_error / timeout
    final_upstream_display   TEXT,
    attempt_count            INTEGER NOT NULL DEFAULT 0
);

-- 9. 路由尝试（每次尝试一条）
CREATE TABLE IF NOT EXISTS route_attempt (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id              TEXT NOT NULL,
    attempt_index           INTEGER NOT NULL,
    upstream_endpoint_id    TEXT NOT NULL,
    upstream_display_name   TEXT,
    upstream_model_name     TEXT,
    started_at              TEXT NOT NULL,
    ended_at                TEXT,
    result_category         TEXT NOT NULL,       -- success/network_error/timeout/rate_limited/server_error/auth_error/client_error
    upstream_status_code    INTEGER,
    duration_ms             INTEGER,
    sanitized_error         TEXT,
    retryable               INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (request_id) REFERENCES gateway_request(request_id) ON DELETE CASCADE
);

-- 便于查询的索引
CREATE INDEX IF NOT EXISTS idx_upstream_provider ON upstream_endpoint(provider_id);
CREATE INDEX IF NOT EXISTS idx_model_provider ON model_catalog_entry(provider_id);
CREATE INDEX IF NOT EXISTS idx_price_model ON price_snapshot(model_catalog_entry_id);
CREATE INDEX IF NOT EXISTS idx_promo_provider ON promotion(provider_id);
CREATE INDEX IF NOT EXISTS idx_member_group ON api_group_member(group_id);
CREATE INDEX IF NOT EXISTS idx_attempt_request ON route_attempt(request_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_model_provider_upstream
    ON model_catalog_entry(provider_id, upstream_model_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_current_price_model
    ON price_snapshot(model_catalog_entry_id) WHERE is_current = 1;
