-- =====================================================
-- BatteryLand v2 セットアップSQL
-- 代理店管理システム + 管理者ポリシー
-- =====================================================

-- 1. demo_usersにreferral_codeカラム追加
ALTER TABLE demo_users ADD COLUMN IF NOT EXISTS referral_code text;

-- 2. 管理者用RLSポリシー（demo_users全件参照可能）
DROP POLICY IF EXISTS "Admin full access to demo_users" ON demo_users;
CREATE POLICY "Admin full access to demo_users"
  ON demo_users FOR ALL
  USING (
    auth.email() = 'hirofumiy@440marketing.biz'
    OR auth.email() = 'hirofumiy@gmail.com'
  );

-- 3. partnersテーブル（代理店マスタ）
CREATE TABLE IF NOT EXISTS partners (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_name        TEXT NOT NULL,
  contact_name        TEXT,
  contact_email       TEXT NOT NULL UNIQUE,
  referral_code       TEXT NOT NULL UNIQUE,
  tier                INTEGER DEFAULT 1,
  active_referrals    INTEGER DEFAULT 0,
  contract_status     TEXT DEFAULT 'prospect',
  contract_signed_at  TIMESTAMPTZ,
  is_active           BOOLEAN DEFAULT true,
  bank_name           TEXT,
  bank_branch         TEXT,
  bank_account_type   TEXT DEFAULT '普通',
  bank_account_no     TEXT,
  bank_account_name   TEXT,
  notes               TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE partners ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Admin full access to partners" ON partners;
CREATE POLICY "Admin full access to partners"
  ON partners FOR ALL
  USING (
    auth.email() = 'hirofumiy@440marketing.biz'
    OR auth.email() = 'hirofumiy@gmail.com'
  );

-- 4. partner_referralsテーブル（紹介実績）
CREATE TABLE IF NOT EXISTS partner_referrals (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_id      UUID REFERENCES partners(id) ON DELETE CASCADE,
  user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  status          TEXT DEFAULT 'trial',
  plan            TEXT,
  monthly_amount  INTEGER DEFAULT 0,
  referred_at     TIMESTAMPTZ DEFAULT NOW(),
  activated_at    TIMESTAMPTZ
);

ALTER TABLE partner_referrals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Admin full access to partner_referrals" ON partner_referrals;
CREATE POLICY "Admin full access to partner_referrals"
  ON partner_referrals FOR ALL
  USING (
    auth.email() = 'hirofumiy@440marketing.biz'
    OR auth.email() = 'hirofumiy@gmail.com'
  );

-- 5. partner_paymentsテーブル（コミッション支払い記録）
CREATE TABLE IF NOT EXISTS partner_payments (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_id        UUID REFERENCES partners(id) ON DELETE CASCADE,
  year_month        TEXT NOT NULL,
  total_commission  INTEGER DEFAULT 0,
  active_referrals  INTEGER DEFAULT 0,
  tier              INTEGER DEFAULT 1,
  status            TEXT DEFAULT 'pending',
  paid_at           TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE partner_payments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Admin full access to partner_payments" ON partner_payments;
CREATE POLICY "Admin full access to partner_payments"
  ON partner_payments FOR ALL
  USING (
    auth.email() = 'hirofumiy@440marketing.biz'
    OR auth.email() = 'hirofumiy@gmail.com'
  );
