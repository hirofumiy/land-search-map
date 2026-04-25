// Supabase Edge Function: stripe-webhook
// Stripeの決済イベントを受信し、demo_users テーブルを自動更新する
//
// 【処理対象イベント】
// - checkout.session.completed: 決済完了 → plan='standard', subscribed_companies=[...] を保存
// - customer.subscription.deleted: 解約 → plan='trial' に戻す（任意）
//
// 【client_reference_id フォーマット】
//   {userUUID}__{code1}_{code2}_{code3}
//   例: a1b2c3d4-...-xxxx__tepco_chubu_kepco
//
// 【デプロイ方法】
// 1. Supabase CLI または Dashboard でデプロイ
// 2. Supabase Dashboard → Settings → Edge Functions → Secrets に以下を追加:
//    - STRIPE_SECRET_KEY: Stripeシークレットキー (sk_live_... or sk_test_...)
//    - STRIPE_WEBHOOK_SECRET: Stripe Webhook 署名シークレット (whsec_...)
//    - SUPABASE_URL: https://stgctzyyjfdeforjsvfx.supabase.co
//    - SUPABASE_SERVICE_ROLE_KEY: Supabase service_role キー（RLS回避用）
// 3. Stripe Dashboard → 開発者 → Webhooks → エンドポイント追加
//    URL: https://stgctzyyjfdeforjsvfx.supabase.co/functions/v1/stripe-webhook
//    送信イベント: checkout.session.completed, customer.subscription.deleted

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import Stripe from 'npm:stripe@14.21.0'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.3'

const STRIPE_SECRET_KEY = Deno.env.get('STRIPE_SECRET_KEY')!
const STRIPE_WEBHOOK_SECRET = Deno.env.get('STRIPE_WEBHOOK_SECRET')!
const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!

const stripe = new Stripe(STRIPE_SECRET_KEY, {
  apiVersion: '2024-09-30.acacia',
  httpClient: Stripe.createFetchHttpClient(),
})

// Supabase Admin Client (service_role キーで RLS バイパス)
const supabaseAdmin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

// Stripe webhook signature verification は async crypto が必要
const cryptoProvider = Stripe.createSubtleCryptoProvider()

serve(async (req: Request) => {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 })
  }

  const signature = req.headers.get('stripe-signature')
  if (!signature) {
    return new Response('Missing stripe-signature', { status: 400 })
  }

  const body = await req.text()

  // 署名検証（改ざん・なりすまし防止）
  let event: Stripe.Event
  try {
    event = await stripe.webhooks.constructEventAsync(
      body,
      signature,
      STRIPE_WEBHOOK_SECRET,
      undefined,
      cryptoProvider,
    )
  } catch (err) {
    console.error('⚠️ Webhook signature verification failed:', err.message)
    return new Response(`Webhook Error: ${err.message}`, { status: 400 })
  }

  console.log('✅ Stripe event received:', event.type, event.id)

  try {
    switch (event.type) {
      case 'checkout.session.completed': {
        await handleCheckoutCompleted(event.data.object as Stripe.Checkout.Session)
        break
      }
      case 'customer.subscription.deleted': {
        await handleSubscriptionDeleted(event.data.object as Stripe.Subscription)
        break
      }
      default:
        console.log(`(unhandled event type: ${event.type})`)
    }
    return new Response(JSON.stringify({ received: true }), {
      headers: { 'Content-Type': 'application/json' },
    })
  } catch (err) {
    console.error('❌ Handler error:', err)
    return new Response(`Handler Error: ${err.message}`, { status: 500 })
  }
})

// ───────────────────────────────────────────
// 決済完了時の処理
// ───────────────────────────────────────────
async function handleCheckoutCompleted(session: Stripe.Checkout.Session) {
  const refId = session.client_reference_id
  if (!refId || !refId.includes('__')) {
    console.warn('⚠️ client_reference_id 不正フォーマット:', refId)
    return
  }

  // {userUUID}__{code1}_{code2}_{code3} をパース
  const [userId, companiesStr] = refId.split('__')
  const companies = (companiesStr || '').split('_').filter(Boolean)

  if (!userId || companies.length === 0) {
    console.warn('⚠️ パース失敗:', { userId, companies })
    return
  }

  console.log('📝 update demo_users:', { userId, companies })

  // expires_at は1ヶ月後（サブスクの請求周期に合わせる場合は subscription を取得して period_end を使うこともできる）
  const expiresAt = new Date()
  expiresAt.setMonth(expiresAt.getMonth() + 1)

  const { error } = await supabaseAdmin
    .from('demo_users')
    .update({
      plan: 'standard',
      subscribed_companies: companies,
      stripe_customer_id: session.customer as string,
      stripe_subscription_id: session.subscription as string,
      expires_at: expiresAt.toISOString(),
    })
    .eq('id', userId)

  if (error) {
    console.error('❌ Supabase update error:', error)
    throw error
  }
  console.log('✅ demo_users 更新完了:', userId)
}

// ───────────────────────────────────────────
// サブスク解約時の処理
// ───────────────────────────────────────────
async function handleSubscriptionDeleted(subscription: Stripe.Subscription) {
  const customerId = subscription.customer as string

  const { error } = await supabaseAdmin
    .from('demo_users')
    .update({
      plan: 'expired',
      subscribed_companies: null,
      stripe_subscription_id: null,
    })
    .eq('stripe_customer_id', customerId)

  if (error) {
    console.error('❌ Supabase update (cancel) error:', error)
    throw error
  }
  console.log('✅ プラン解約処理完了:', customerId)
}
