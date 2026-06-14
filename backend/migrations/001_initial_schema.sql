-- Lisa's Assets — Initial Schema
-- Issues #2: Database schema for projects, reports, payments, newsletter

-- =========================================================
-- projects: crypto assets / subnets tracked by the platform
-- =========================================================
CREATE TABLE IF NOT EXISTS projects (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  coingecko_id  TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  symbol        TEXT NOT NULL,
  logo_url      TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- =========================================================
-- reports: a Lisa Coefficient analysis run against a project
-- =========================================================
CREATE TABLE IF NOT EXISTS reports (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        UUID REFERENCES projects(id) ON DELETE CASCADE,
  lisa_coefficient  FLOAT NOT NULL,
  lisa_verdict      TEXT,
  agent_scores      JSONB NOT NULL,
  strongest_agent   TEXT,
  status            TEXT DEFAULT 'generating',
  paid_by_wallet    TEXT,
  crowdfund_pool_id UUID,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  expires_at        TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days'
);

-- =========================================================
-- payments: on-chain payment records for paid reports
-- =========================================================
CREATE TABLE IF NOT EXISTS payments (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id        UUID REFERENCES reports(id) ON DELETE CASCADE,
  wallet_address   TEXT NOT NULL,
  amount           DECIMAL NOT NULL,
  token            TEXT NOT NULL,
  chain            TEXT NOT NULL,
  tx_hash          TEXT UNIQUE,
  discount_applied BOOLEAN DEFAULT FALSE,
  verified         BOOLEAN DEFAULT FALSE,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- =========================================================
-- newsletter_subscriptions: email signups
-- =========================================================
CREATE TABLE IF NOT EXISTS newsletter_subscriptions (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email                  TEXT NOT NULL UNIQUE,
  tier                   TEXT DEFAULT 'free',
  wallet_address         TEXT,
  token_balance_verified BOOLEAN DEFAULT FALSE,
  status                 TEXT DEFAULT 'active',
  created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- =========================================================
-- Indexes for common query patterns
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_reports_project_id     ON reports (project_id);
CREATE INDEX IF NOT EXISTS idx_reports_status         ON reports (status);
CREATE INDEX IF NOT EXISTS idx_reports_created_at     ON reports (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payments_report_id     ON payments (report_id);
CREATE INDEX IF NOT EXISTS idx_payments_wallet        ON payments (wallet_address);
CREATE INDEX IF NOT EXISTS idx_projects_name          ON projects (name);
CREATE INDEX IF NOT EXISTS idx_newsletter_email       ON newsletter_subscriptions (email);

-- =========================================================
-- Row-Level Security
-- =========================================================
ALTER TABLE projects                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletter_subscriptions  ENABLE ROW LEVEL SECURITY;

-- Public can browse projects (read-only)
DROP POLICY IF EXISTS "projects_public_read" ON projects;
CREATE POLICY "projects_public_read"
  ON projects FOR SELECT
  TO anon, authenticated
  USING (true);

-- Public can read published (public) reports only
DROP POLICY IF EXISTS "reports_public_read" ON reports;
CREATE POLICY "reports_public_read"
  ON reports FOR SELECT
  TO anon, authenticated
  USING (status = 'public');

-- Payments are private — service role only (backend uses service key)
-- No anon/authenticated SELECT policy => denied by default under RLS.

-- Newsletter subscriptions are private — service role only.
