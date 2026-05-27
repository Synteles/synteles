  DROP SCHEMA IF EXISTS synteles CASCADE;
  CREATE SCHEMA synteles;
  SET search_path TO synteles;

  -- ============================================================
  -- TRIGGER FUNCTION
  -- Auto-updates updated_at on any row modification.
  -- Apply to every table that has an updated_at column.
  -- ============================================================
  CREATE OR REPLACE FUNCTION set_updated_at()
  RETURNS TRIGGER AS $$
  BEGIN
      NEW.updated_at = now();
      RETURN NEW;
  END;
  $$ LANGUAGE plpgsql;


  -- ============================================================
  -- ORGANIZATIONS
  -- ============================================================
  CREATE TABLE organizations (
      id         UUID        PRIMARY KEY,
      name       TEXT        NOT NULL,
      metadata   JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
  );


  -- ============================================================
  -- GOVERNANCE MODEL
  -- Resources fall into three tiers:
  --
  -- Tier 1 — org-wide, user-authored (agentlets, connectors)
  --   org_id NOT NULL, user_id NOT NULL
  --   Unique within the org. Any org member may use them.
  --   user_id records authorship only (not access boundary).
  --
  -- Tier 2 — user-specific, org-bounded (api_keys, executions,
  --           conversations)
  --   org_id NOT NULL, user_id NOT NULL
  --   Owned by a user but tied to a specific org context.
  --   A key or execution belongs to one user+org pair; revoking
  --   membership should invalidate it.
  --
  -- Tier 3 — purely user-specific (secrets, models)
  --   user_id NOT NULL, no org_id
  --   Personal credentials and preferences that travel with the
  --   user regardless of org membership. A user's OpenAI key or
  --   model preset is theirs — not the org's.
  -- ============================================================


  -- ============================================================
  -- USERS
  -- id = Cognito sub (set at registration).
  -- Email, name, username are owned by Cognito; query the JWT
  -- or Cognito when display data is needed.
  -- Org membership is managed via the users_orgs join table.
  -- ============================================================
  CREATE TABLE users (
      id         UUID        PRIMARY KEY,
      metadata   JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  -- ============================================================
  -- USERS_ORGS
  -- Many-to-many join: one user may belong to multiple orgs.
  -- Cascade delete ensures memberships are removed automatically
  -- when a user or org is deleted.
  -- PRIMARY KEY (user_id, org_id) covers "which orgs for user X".
  -- Index on org_id covers "which users for org Y".
  -- ============================================================
  CREATE TABLE users_orgs (
      user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      org_id     UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
      PRIMARY KEY (user_id, org_id)
  );

  CREATE INDEX ON users_orgs (org_id);

  -- ============================================================
  -- AGENTLETS
  -- ============================================================
  CREATE TABLE agentlets (
      id              UUID        PRIMARY KEY,
      org_id          UUID        REFERENCES organizations(id) NOT NULL,
      user_id         UUID        REFERENCES users(id) NOT NULL,
      name            TEXT        NOT NULL,
      description     TEXT,
      yaml_definition TEXT        NOT NULL,
      created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (org_id, name)
  );

  CREATE INDEX ON agentlets (user_id);
  CREATE INDEX ON agentlets (org_id);

  CREATE TRIGGER trg_agentlets_updated_at
      BEFORE UPDATE ON agentlets
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();


  -- ============================================================
  -- API KEYS
  -- key_hash: SHA-256 of the raw key (never store plaintext).
  -- name: user-supplied label so keys can be identified and
  --       selectively revoked (e.g. "Production", "CI/CD").
  -- revoked_at: soft-delete; NULL means active. Keeps audit
  --             trail of when a key was invalidated and by whom.
  -- ============================================================
  CREATE TABLE api_keys (
      id         UUID        PRIMARY KEY,
      org_id     UUID        REFERENCES organizations(id) NOT NULL,
      user_id    UUID        REFERENCES users(id) NOT NULL,
      name       TEXT        NOT NULL DEFAULT 'default',
      key_hash   TEXT        NOT NULL,
      last_used  TIMESTAMPTZ,
      revoked_at TIMESTAMPTZ,           -- NULL = active; set to revoke without deleting
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  CREATE INDEX ON api_keys (key_hash);
  CREATE INDEX ON api_keys (user_id);
  CREATE INDEX ON api_keys (org_id);


  -- ============================================================
  -- EXECUTIONS
  -- status: typed enum; 'deploying' and 'running' are the
  --         "active" states used by the status-monitor loop.
  -- job_ref: opaque backend reference — ECS task ARN,
  --          Docker container ID, or K8s Job name depending on
  --          EXECUTION_BACKEND env var.
  -- timeout_at: scheduler-service stops the job when
  --             now() > timeout_at regardless of status.
  -- ============================================================
  CREATE TYPE exec_status AS ENUM (
      'deploying',
      'running',
      'completed',
      'failed',
      'stopped'
  );

  CREATE TABLE executions (
      id            UUID        PRIMARY KEY,
      org_id        UUID        REFERENCES organizations(id) NOT NULL,
      user_id       UUID        REFERENCES users(id) NOT NULL,
      agentlet_id   UUID        REFERENCES agentlets(id) NOT NULL,
      agentlet_name TEXT        NOT NULL DEFAULT '',
      status        exec_status NOT NULL,
      job_ref       TEXT,
      timeout_at    TIMESTAMPTZ,
      prompt        TEXT        NOT NULL DEFAULT '',
      logs_s3_uri   TEXT,
      error         TEXT,
      completed_at  TIMESTAMPTZ,
      created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  CREATE INDEX ON executions (status, updated_at);
  CREATE INDEX ON executions (agentlet_id, created_at);
  CREATE INDEX ON executions (user_id, created_at);
  CREATE INDEX ON executions (org_id, created_at);

  -- Partial index: only active executions — used by the
  -- scheduler-service monitor loop (polls every 60 s).
  -- Stays small as completed/failed rows are excluded.
  CREATE INDEX ON executions (updated_at)
      WHERE status IN ('deploying', 'running');

  CREATE TRIGGER trg_executions_updated_at
      BEFORE UPDATE ON executions
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();


  -- ============================================================
  -- CONVERSATIONS
  -- Metadata only. Message content lives in S3 as two blobs
  -- per conversation; their paths are deterministic and derived
  -- at query time — no blob key stored here:
  --   display:     conversations/{user_id}/{conv_id}/display.json
  --   agent_state: conversations/{user_id}/{conv_id}/agent_state.json
  -- expires_at: application-enforced TTL (replaces DynamoDB TTL).
  --             scheduler-service runs a cleanup query every 24h.
  -- ============================================================
  CREATE TABLE conversations (
      id            UUID        PRIMARY KEY,
      org_id        UUID        REFERENCES organizations(id) NOT NULL,
      user_id       UUID        REFERENCES users(id) NOT NULL,
      title         TEXT,
      message_count INT         NOT NULL DEFAULT 0,
      expires_at    TIMESTAMPTZ,
      created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  );

  CREATE INDEX ON conversations (user_id, created_at);
  CREATE INDEX ON conversations (org_id, created_at);

  CREATE TRIGGER trg_conversations_updated_at
      BEFORE UPDATE ON conversations
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();


  -- ============================================================
  -- SECRETS  [Tier 3 — purely user-specific]
  -- Personal LLM API keys stored as AES-256-GCM ciphertext.
  -- No org_id: secrets belong to the user, not the org. A user's
  -- OpenAI key is theirs and travels with them across orgs.
  -- nonce: 12-byte random IV generated per encrypt call.
  -- encrypted_value: ciphertext + GCM auth tag (AESGCM appends).
  -- key_count: number of key-value pairs in the secret dict,
  --   stored at write time so list endpoints avoid decryption.
  -- key_version: incremented on SECRET_ENCRYPTION_KEY rotation
  --   to track which rows need re-encryption.
  -- ============================================================
  CREATE TABLE secrets (
      id               UUID        PRIMARY KEY,
      user_id          UUID        NOT NULL REFERENCES users(id),
      name             TEXT        NOT NULL,
      description      TEXT,
      encrypted_value  BYTEA       NOT NULL,
      nonce            BYTEA       NOT NULL,
      key_version      INT         NOT NULL DEFAULT 1,
      key_count        INT         NOT NULL DEFAULT 0,
      created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (user_id, name)
  );

  -- UNIQUE (user_id, name) covers all lookup patterns; no extra indexes needed.

  CREATE TRIGGER trg_secrets_updated_at
      BEFORE UPDATE ON secrets
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();


  -- ============================================================
  -- MODELS (model presets)  [Tier 3 — purely user-specific]
  -- Personal LLM configuration presets (provider + model_id +
  -- optional secret reference). No org_id: a preset like
  -- "my-gpt4o" is a personal preference, not an org asset.
  -- config JSONB stores: {provider, model_id, secret_name,
  --   description} — flexible for future fields without migration.
  -- ============================================================
  CREATE TABLE models (
      id         UUID        PRIMARY KEY,
      user_id    UUID        NOT NULL REFERENCES users(id),
      name       TEXT        NOT NULL,
      config     JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (user_id, name)
  );

  CREATE INDEX ON models (user_id);

  CREATE TRIGGER trg_models_updated_at
      BEFORE UPDATE ON models
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();


  -- ============================================================
  -- CONNECTORS (MCP presets)
  -- Org-scoped MCP server configurations.
  -- user_id records who created the connector for audit purposes
  -- but access is scoped to the org, not the individual user.
  -- ============================================================
  CREATE TABLE connectors (
      id         UUID        PRIMARY KEY,
      org_id     UUID        REFERENCES organizations(id) NOT NULL,
      user_id    UUID        REFERENCES users(id) NOT NULL,
      name       TEXT        NOT NULL,
      config     JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (org_id, name)
  );

  CREATE INDEX ON connectors (org_id);
  CREATE INDEX ON connectors (user_id);
  CREATE INDEX ON connectors (org_id, user_id);

  CREATE TRIGGER trg_connectors_updated_at
      BEFORE UPDATE ON connectors
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();

  -- Restore default search_path so Alembic can find its alembic_version table
  -- in the public schema after we set search_path = synteles above.
  RESET search_path;
