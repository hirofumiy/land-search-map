-- migration-v4: 登記簿謄本取得・DM送付サービス

-- demo_users にクレジット列追加（Enterprise用）
ALTER TABLE demo_users
  ADD COLUMN IF NOT EXISTS registry_credits integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS dm_credits integer NOT NULL DEFAULT 0;

-- 登記簿謄本取得依頼テーブル
CREATE TABLE IF NOT EXISTS registry_requests (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  address           text        NOT NULL,
  lat               float,
  lng               float,
  status            text        NOT NULL DEFAULT 'pending',  -- pending | processing | completed | cancelled
  paid              boolean     NOT NULL DEFAULT false,
  used_credit       boolean     NOT NULL DEFAULT false,
  stripe_session_id text,
  amount            integer     NOT NULL DEFAULT 500,
  pdf_url           text,
  admin_notes       text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE registry_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY "registry: user read own"   ON registry_requests FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "registry: user insert own" ON registry_requests FOR INSERT WITH CHECK (auth.uid() = user_id);

-- DM送付依頼テーブル
CREATE TABLE IF NOT EXISTS dm_requests (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  address           text        NOT NULL,
  lat               float,
  lng               float,
  status            text        NOT NULL DEFAULT 'pending',  -- pending | sent | failed | cancelled
  paid              boolean     NOT NULL DEFAULT false,
  used_credit       boolean     NOT NULL DEFAULT false,
  stripe_session_id text,
  amount            integer     NOT NULL DEFAULT 300,
  sent_at           timestamptz,
  admin_notes       text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE dm_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY "dm: user read own"   ON dm_requests FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "dm: user insert own" ON dm_requests FOR INSERT WITH CHECK (auth.uid() = user_id);
