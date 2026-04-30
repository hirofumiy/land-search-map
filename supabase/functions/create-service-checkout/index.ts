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
