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
  // Standardプラン: ¥150,000/月（税別） = 基本料金 + 電力会社1社付属
  //   追加電力会社: +¥50,000/月（税別）/ 社
  //
  // ⚠️ Stripe側の設定（ひろさん作業）:
  //   Payment Link には以下2つの商品（Price）を紐付けてください:
  //     1. 「Standard基本料金」 ¥150,000/月（数量固定=1、電力会社1社付属）
  //     2. 「追加電力会社」    ¥50,000/月（"Let customers adjust quantity" ON）
  //   Payment Link URL を STRIPE_STANDARD_PAYMENT_LINK にセット。
  //   商品2の Price ID (price_xxx) を STRIPE_ADDON_PRICE_ID にセット。
  //   → フロント側で追加社数を URL param (prefilled_promo_code不可のためadjustable_quantity初期値経由) で渡します。
  STRIPE_STANDARD_PAYMENT_LINK: 'https://buy.stripe.com/3cI8wJa6Raf6e5B6Ka63K01',
  STRIPE_ADDON_PRICE_ID: '', // 例: 'price_1XYZ...'（空の場合は基本料金のみ送信）
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
