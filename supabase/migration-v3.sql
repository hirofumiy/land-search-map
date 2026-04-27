-- =====================================================
-- BatteryLand v3 マイグレーション
-- Stripe Webhook 対応: subscribed_companies カラム追加
-- =====================================================
-- Supabase Dashboard → SQL Editor に貼り付けて実行

-- demo_users に subscribed_companies カラムを追加
-- 例: ['tepco', 'chubu', 'kepco']
ALTER TABLE demo_users
  ADD COLUMN IF NOT EXISTS subscribed_companies text[];

-- plan の値に 'standard' / 'expired' を明示的に追加（コメント）
-- 現在の plan 取りうる値:
--   'trial'    : 試用期間中
--   'standard' : 有料プラン（決済完了後）
--   'expired'  : 解約 or 試用期間終了
--   'enterprise': 個別対応プラン

-- 確認クエリ（実行後に貼り付けて確認）
-- SELECT id, email, plan, subscribed_companies, expires_at FROM demo_users LIMIT 10;
