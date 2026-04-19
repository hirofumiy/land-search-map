-- =====================================================
-- BatteryLand Supabase セットアップSQL
-- Supabase Dashboard → SQL Editor に貼り付けて実行
-- =====================================================

-- 1. demo_users テーブル（既存の場合は更新）
CREATE TABLE IF NOT EXISTS demo_users (
  id          uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email       text NOT NULL,
  display_name text,
  first_login_at timestamptz DEFAULT now(),
  expires_at  timestamptz NOT NULL DEFAULT (now() + interval '72 hours'),
  plan        text NOT NULL DEFAULT 'trial',  -- 'trial' | 'basic' | 'premium'
  stripe_customer_id    text,
  stripe_subscription_id text,
  created_at  timestamptz DEFAULT now(),
  updated_at  timestamptz DEFAULT now()
);

-- 既存テーブルへの列追加（既にある場合はエラーになるが無視してOK）
ALTER TABLE demo_users ADD COLUMN IF NOT EXISTS display_name text;
ALTER TABLE demo_users ADD COLUMN IF NOT EXISTS first_login_at timestamptz DEFAULT now();
ALTER TABLE demo_users ADD COLUMN IF NOT EXISTS plan text NOT NULL DEFAULT 'trial';
ALTER TABLE demo_users ADD COLUMN IF NOT EXISTS stripe_customer_id text;
ALTER TABLE demo_users ADD COLUMN IF NOT EXISTS stripe_subscription_id text;
-- ★ シングルセッション制限用トークン（ログインのたびに新しいUUIDを発行）
ALTER TABLE demo_users ADD COLUMN IF NOT EXISTS session_token uuid;

-- 試用期間を24時間 → 72時間に変更（既存レコードを更新）
UPDATE demo_users
  SET expires_at = first_login_at + interval '72 hours'
  WHERE plan = 'trial'
  AND expires_at < first_login_at + interval '72 hours';

-- 2. RLS (Row Level Security) を有効化
ALTER TABLE demo_users ENABLE ROW LEVEL SECURITY;

-- ポリシー: ユーザーは自分のレコードのみ読み書き可能
DROP POLICY IF EXISTS "Users can view own record" ON demo_users;
CREATE POLICY "Users can view own record"
  ON demo_users FOR SELECT
  USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can insert own record" ON demo_users;
CREATE POLICY "Users can insert own record"
  ON demo_users FOR INSERT
  WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own record" ON demo_users;
CREATE POLICY "Users can update own record"
  ON demo_users FOR UPDATE
  USING (auth.uid() = id);

-- 3. updated_at を自動更新するトリガー
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS demo_users_updated_at ON demo_users;
CREATE TRIGGER demo_users_updated_at
  BEFORE UPDATE ON demo_users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =====================================================
-- 完了！
-- 次のステップ:
-- 1. Supabase Dashboard → Authentication → Providers → Email
--    → "Confirm email" を OFF にする（デモ用）
-- 2. Edge Functions → notify-line をデプロイ
--    → Secrets に LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID を設定
-- =====================================================
