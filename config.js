// =====================================================
// BatteryLand 設定ファイル
// ここに認証情報を入力してください
// =====================================================

const BATTERYLAND_CONFIG = {
  // Supabase (必須)
  // Supabase Dashboard → Settings → API → anon public
  SUPABASE_URL: 'https://stgctzyyjfdeforjsvfx.supabase.co',
  SUPABASE_ANON_KEY: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0Z2N0enl5amZkZWZvcmpzdmZ4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY1MTc1MDAsImV4cCI6MjA5MjA5MzUwMH0.0nNZClP547Br6G4GK0TAZPhPG0UXPaMPWu0B80NwvRo',

  // Stripe (試用期間終了後の決済)
  // Stripe Dashboard → 開発者 → API Keys → 公開可能キー (pk_test_...)
  STRIPE_PUBLISHABLE_KEY: 'pk_test_YOUR_KEY',

  // Stripe Payment Links (Stripe Dashboard → Payment Links で作成)
  // Liteプラン: ¥98,000/月（税別）
  STRIPE_LITE_PAYMENT_LINK: 'https://buy.stripe.com/test_LITE_LINK',
  // Standardプラン: ¥198,000/月（税別）
  STRIPE_STANDARD_PAYMENT_LINK: 'https://buy.stripe.com/test_STANDARD_LINK',
  // Enterpriseプラン: ¥500,000/月（税別）→ メール問い合わせ対応のためStripeリンク不要

  // 試用期間 (時間)
  TRIAL_HOURS: 72,

  // アプリ名・会社名
  APP_NAME: 'BatteryLand',
  COMPANY_NAME: '合同会社440',

  // 管理者メールアドレス
  ADMIN_EMAIL: 'hirofumiy@440marketing.biz',
  ADMIN_EMAIL_2: 'hirofumiy@gmail.com',
};

// グローバルに公開
window.BATTERYLAND_CONFIG = BATTERYLAND_CONFIG;
