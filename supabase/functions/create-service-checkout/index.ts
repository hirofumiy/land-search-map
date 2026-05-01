// Supabase Edge Function: create-service-checkout
// 登記簿謄本取得・DM送付の依頼受付と決済処理
//
// Standard: Stripe Checkout Session (mode: payment) で都度¥500/¥300決済
// Enterprise: registry_credits / dm_credits を消費（決済不要）
//
// 【必要な Supabase Secrets】
//   STRIPE_SECRET_KEY（既存）
//   PRICE_REGISTRY: Stripe Price ID for 登記簿謄本取得 ¥500
//   PRICE_DM:       Stripe Price ID for DM送付 ¥300
//   ADMIN_EMAIL:    hirofumiy@440marketing.biz

import Stripe from 'npm:stripe@14.21.0'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.3'

const SITE_URL    = 'https://batteryland.440marketing.biz'
const ADMIN_EMAIL = Deno.env.get('ADMIN_EMAIL') || 'hirofumiy@440marketing.biz'

// ── Resend メール通知 ──
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
    console.error('❌ Resend error:', await res.text())
  } else {
    console.log('✅ 通知メール送信完了 →', userEmail)
  }
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: corsHeaders })
  if (req.method !== 'POST') return json({ error: 'Method not allowed' }, 405)

  try {
    // ── 認証 ──
    const token = req.headers.get('Authorization')?.replace('Bearer ', '')
    if (!token) return json({ error: 'Unauthorized' }, 401)

    const sbAnon = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!)
    const { data: { user }, error: authErr } = await sbAnon.auth.getUser(token)
    if (authErr || !user) return json({ error: 'Unauthorized' }, 401)

    const sbAdmin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)

    // ── リクエストボディ ──
    const { type, address, lat, lng } = await req.json()
    if (!['registry', 'dm'].includes(type)) return json({ error: 'Invalid type' }, 400)
    if (!address) return json({ error: 'address is required' }, 400)

    const table  = type === 'registry' ? 'registry_requests' : 'dm_requests'
    const amount = type === 'registry' ? 500 : 300

    // ── Enterprise クレジット確認 ──
    const { data: demoUser } = await sbAdmin
      .from('demo_users')
      .select('plan, registry_credits, dm_credits')
      .eq('id', user.id)
      .single()

    const creditField = type === 'registry' ? 'registry_credits' : 'dm_credits'
    const currentCredits: number = demoUser?.[creditField] ?? 0

    if (demoUser?.plan === 'enterprise' && currentCredits > 0) {
      // クレジット消費（Enterprise）
      await sbAdmin.from('demo_users')
        .update({ [creditField]: currentCredits - 1 })
        .eq('id', user.id)

      const { data: req_ } = await sbAdmin.from(table)
        .insert({ user_id: user.id, address, lat, lng, paid: true, used_credit: true, amount: 0, status: 'pending' })
        .select('id').single()

      console.log(`✅ Enterprise credit used: ${type} req=${req_?.id}`)

      // ── メール通知（Enterprise） ──
      try {
        await sendServiceNotification({
          userEmail: user.email ?? '不明',
          address,
          svcType: type,
          requestId: req_?.id ?? '不明',
          paymentMethod: 'credit',
        })
      } catch (e) {
        console.error('❌ 通知メール送信エラー（クレジット処理には影響なし）:', e)
      }

      return json({ success: true, used_credit: true, remaining: currentCredits - 1 })
    }

    // ── Standard: Stripe 都度決済 ──

    // 先に pending レコードを作成
    const { data: reqRecord } = await sbAdmin.from(table)
      .insert({ user_id: user.id, address, lat, lng, paid: false, amount, status: 'pending_payment' })
      .select('id').single()

    const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY')!, {
      apiVersion: '2024-09-30.acacia',
      httpClient: Stripe.createFetchHttpClient(),
    })

    const serviceName = type === 'registry' ? '登記簿謄本取得' : 'DM送付'

    const session = await stripe.checkout.sessions.create({
      mode: 'payment',
      line_items: [{
        price_data: {
          currency: 'jpy',
          unit_amount: amount,
          product_data: {
            name: `BatteryLand ${serviceName}`,
            description: `対象地: ${address}`,
          },
        },
        quantity: 1,
      }],
      success_url: `${SITE_URL}/index.html?svc_success=${type}`,
      cancel_url:  `${SITE_URL}/index.html`,
      client_reference_id: `svc_${type}__${reqRecord!.id}`,
      metadata: { type, address, request_id: reqRecord!.id, user_id: user.id },
      payment_intent_data: {
        description: `${serviceName}: ${address}`,
        metadata: { type, address, request_id: reqRecord!.id },
      },
    })

    console.log(`✅ Checkout session created: ${type} req=${reqRecord!.id}`)
    return json({ url: session.url })

  } catch (err) {
    console.error('❌ create-service-checkout error:', err)
    return json({ error: err.message }, 500)
  }
})

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}
