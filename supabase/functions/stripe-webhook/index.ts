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
// 決済完了時の処理（サブスク・サービス共通）
// ───────────────────────────────────────────
async function handleCheckoutCompleted(session: Stripe.Checkout.Session) {
  const refId = session.client_reference_id
  if (!refId || !refId.includes('__')) {
    console.warn('⚠️ client_reference_id 不正フォーマット:', refId)
    return
  }

  // サービス決済: svc_registry__{requestId} or svc_dm__{requestId}
  if (refId.startsWith('svc_')) {
    await handleServicePaymentCompleted(session, refId)
    return
  }

  // サブスク決済: {userUUID}__{code1}_{code2}_{code3}
  const [userId, companiesStr] = refId.split('__')
  const companies = (companiesStr || '').split('_').filter(Boolean)

  if (!userId || companies.length === 0) {
    console.warn('⚠️ パース失敗:', { userId, companies })
    return
  }

  console.log('📝 update demo_users:', { userId, companies })

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
// メール通知（Resend）
// ───────────────────────────────────────────
async function sendServiceNotification({
  userEmail, address, svcType, requestId, paymentMethod,
}: {
  userEmail: string
  address: string
  svcType: string
  requestId: string
  paymentMethod: 'stripe' | 'credit'
}) {
  const resendKey = Deno.env.get('RESEND_API_KEY')
  if (!resendKey) { console.warn('⚠️ RESEND_API_KEY 未設定'); return }

  const label   = svcType === 'registry' ? '登記簿謄本取得' : 'DM送付'
  const payNote = paymentMethod === 'credit' ? 'クレジット利用（Enterprise）' : 'Stripe決済完了'

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${resendKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      from: 'BatteryLand <onboarding@resend.dev>',
      to: ['hirofumiy@gmail.com'],  // ドメイン未認証中はgmailのみ受信可
      subject: `【BatteryLand】${label}依頼が入りました`,
      html: `
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px;border:1px solid #e2e8f0;border-radius:8px;">
          <h2 style="color:#1e293b;margin-bottom:16px;">📋 ${label}依頼</h2>
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr style="border-bottom:1px solid #f1f5f9;">
              <td style="padding:10px 8px;color:#64748b;width:140px;white-space:nowrap;">📧 送付先メール</td>
              <td style="padding:10px 8px;font-weight:600;color:#0f172a;">
                <a href="mailto:${userEmail}" style="color:#2563eb;">${userEmail}</a>
              </td>
            </tr>
            <tr style="border-bottom:1px solid #f1f5f9;">
              <td style="padding:10px 8px;color:#64748b;">📍 対象地</td>
              <td style="padding:10px 8px;color:#0f172a;">${address}</td>
            </tr>
            <tr style="border-bottom:1px solid #f1f5f9;">
              <td style="padding:10px 8px;color:#64748b;">💳 決済</td>
              <td style="padding:10px 8px;color:#0f172a;">${payNote}</td>
            </tr>
            <tr>
              <td style="padding:10px 8px;color:#64748b;">🆔 依頼ID</td>
              <td style="padding:10px 8px;font-family:monospace;font-size:12px;color:#475569;">${requestId}</td>
            </tr>
          </table>
          <p style="margin-top:20px;font-size:12px;color:#94a3b8;">このメールはBatteryLandシステムから自動送信されています。</p>
        </div>
      `,
    }),
  })
  if (!res.ok) {
    const err = await res.text()
    console.error('❌ Resend error:', err)
  } else {
    console.log('✅ 通知メール送信完了 →', userEmail)
  }
}

// ───────────────────────────────────────────
// サービス決済完了（謄本取得・DM送付）
// ───────────────────────────────────────────
async function handleServicePaymentCompleted(session: Stripe.Checkout.Session, refId: string) {
  // svc_registry__{requestId} → type=registry, id=requestId
  const [svcType, requestId] = refId.replace('svc_', '').split('__')
  if (!svcType || !requestId) {
    console.warn('⚠️ サービス決済 refId パース失敗:', refId)
    return
  }

  const table = svcType === 'registry' ? 'registry_requests' : 'dm_requests'
  console.log(`📝 ${table} 決済完了:`, requestId)

  const { error } = await supabaseAdmin
    .from(table)
    .update({
      paid: true,
      status: 'pending',
      stripe_session_id: session.id,
    })
    .eq('id', requestId)

  if (error) {
    console.error(`❌ ${table} update error:`, error)
    throw error
  }
  console.log(`✅ ${table} 決済確認完了:`, requestId)

  // ── メール通知 ──
  try {
    const { data: reqData } = await supabaseAdmin
      .from(table).select('address, user_id').eq('id', requestId).single()
    const { data: { user: authUser } } = await supabaseAdmin.auth.admin.getUserById(reqData?.user_id)
    await sendServiceNotification({
      userEmail: authUser?.email || '不明',
      address: reqData?.address || '不明',
      svcType,
      requestId,
      paymentMethod: 'stripe',
    })
  } catch (e) {
    console.error('❌ 通知メール送信エラー（決済処理には影響なし）:', e)
  }
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
