-- 002_crowdfund_pools.sql
-- Crowdfunding pools: community-pooled USDC toward a project's report.
-- Once current_amount reaches target_amount the pool is marked 'funded'.

CREATE TABLE IF NOT EXISTS crowdfund_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    coingecko_id TEXT,
    target_amount DECIMAL(10,2) NOT NULL DEFAULT 9.99,
    current_amount DECIMAL(10,2) NOT NULL DEFAULT 0.0,
    contributors_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',  -- open, funded, expired
    report_id UUID REFERENCES reports(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    funded_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS crowdfund_contributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id UUID NOT NULL REFERENCES crowdfund_pools(id),
    wallet_address TEXT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    tx_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
