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

  // Stripe Payment Links
  // Standardプラン: ¥150,000/月（税別・1社付属） + 初回登録料 ¥50,000
  //   追加電力会社: +¥50,000/月/社（Stripe最小数量=1制限のため2本構成）
  //
  // リンクA (追加なし): 基本料金 + 初回登録料 の2商品
  // リンクB (追加あり): 基本料金 + 追加電力会社(数量調整可) + 初回登録料 の3商品
  STRIPE_STANDARD_LINK_BASE: 'https://buy.stripe.com/4gM9ANgvfaf67Hd8Si63K06',   // リンクA
  STRIPE_STANDARD_LINK_ADDON: 'https://buy.stripe.com/9B628lbaV86Y2mT1pQ63K05',  // リンクB
  STRIPE_ADDON_PRICE_ID: 'price_1TPkUL9NAOR2l1VNyvmAdm65',                       // 追加電力会社エリア Price ID
  // 旧パラメータ互換（後方互換のため残置）
  STRIPE_STANDARD_PAYMENT_LINK: 'https://buy.stripe.com/4gM9ANgvfaf67Hd8Si63K06',
  // Enterpriseプラン: ¥500,000/月（税別）→ メール問い合わせ対応のためStripeリンク不要

  // 料金設定（税別）
  STANDARD_BASE_PRICE: 150000,   // 基本料金（1社付属）
  ADDON_COMPANY_PRICE: 50000,    // 追加電力会社1社あたり
  STANDARD_INIT_FEE: 50000,      // 初回登録料

  // 試用期間 (時間) ※7日間 = 168時間
  TRIAL_HOURS: 168,

  // アプリ名・会社名
  APP_NAME: 'BatteryLand',
  COMPANY_NAME: '合同会社440',

  // 管理者メールアドレス
  ADMIN_EMAIL: 'hirofumiy@440marketing.biz',
  ADMIN_EMAIL_2: 'hirofumiy@gmail.com',
};

// グローバルに公開
window.BATTERYLAND_CONFIG = BATTERYLAND_CONFIG;
