// =====================================================
// BatteryLand 設定ファイル
// ここに認証情報を入力してください
// =====================================================

const BATTERYLAND_CONFIG = {
  // Supabase (必須)
  // Supabase Dashboard → Settings → API → anon public
  SUPABASE_URL: 'https://wwgfpgkhgslucanwvjsl.supabase.co',
  SUPABASE_ANON_KEY: 'YOUR_SUPABASE_ANON_KEY',

  // Stripe (試用期間終了後の決済)
  // Stripe Dashboard → 開発者 → API Keys → 公開可能キー (pk_test_...)
  STRIPE_PUBLISHABLE_KEY: 'pk_test_YOUR_KEY',

  // Stripe Payment Links (Stripe Dashboard → Payment Links で作成)
  // ベーシックプラン: ¥9,800/月
  STRIPE_BASIC_PAYMENT_LINK: 'https://buy.stripe.com/test_BASIC_LINK',
  // プレミアムプラン: ¥29,800/月
  STRIPE_PREMIUM_PAYMENT_LINK: 'https://buy.stripe.com/test_PREMIUM_LINK',

  // 試用期間 (時間)
  TRIAL_HOURS: 72,

  // アプリ名・会社名
  APP_NAME: 'BatteryLand',
  COMPANY_NAME: '合同会社440',
};

// グローバルに公開
window.BATTERYLAND_CONFIG = BATTERYLAND_CONFIG;
