// Supabase Edge Function: create-checkout
// Stripe Checkout Session をサーバー側で動的生成し、URL を返す
//
// 【なぜ Payment Links でなく Checkout Session を使うか】
//   Payment Links の URL パラメータ（prefilled_quantity）は動的数量変更に対応していない。
//   Checkout Session は line_items に quantity を直接指定できるため確実。
//
// 【必要な Supabase Secrets（Dashboard → Settings → Edge Functions → Secrets）】
//   STRIPE_SECRET_KEY: sk_test_... または sk_live_...
//   （SUPABASE_URL, SUPABASE_ANON_KEY は自動注入）

import Stripe from 'npm:stripe@14.21.0'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.3'

// 商品 Price ID（テスト環境）
const PRICE_BASE     = 'price_1TPkTM9NAOR2l1VNpEmDR70k'  // 基本料金 ¥150,000/月
const PRICE_ADDON    = 'price_1TPkUL9NAOR2l1VNyvmAdm65'  // 追加電力会社 ¥50,000/月
const PRICE_INIT_FEE = 'price_1TPkZA9NAOR2l1VNPMhdhheY'  // 初回登録料 ¥50,000（一回限り）

const SUCCESS_URL = 'https://batteryland.440marketing.biz/expired.html?success=1'
const CANCEL_URL  = 'https://batteryland.440marketing.biz/expired.html'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

Deno.serve(async (req: Request) => {
  // プリフライトリクエスト（CORS）
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders })
  }

  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405, headers: corsHeaders })
  }

  try {
    // ── 1. JWT 検証（ログイン済みユーザーのみ許可） ──
    const authHeader = req.headers.get('Authorization')
    if (!authHeader?.startsWith('Bearer ')) {
      return json({ error: 'Unauthorized' }, 401)
    }

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_ANON_KEY')!,
    )

    const { data: { user }, error: authError } = await supabase.auth.getUser(
      authHeader.replace('Bearer ', ''),
    )
    if (authError || !user) {
      return json({ error: 'Unauthorized' }, 401)
    }

    // ── 2. リクエストボディのバリデーション ──
    const body = await req.json()
    const { primaryCompany, addonCompanies } = body

    if (!primaryCompany || typeof primaryCompany !== 'string') {
      return json({ error: 'primaryCompany is required' }, 400)
    }
    if (!Array.isArray(addonCompanies)) {
      return json({ error: 'addonCompanies must be an array' }, 400)
    }

    const addonCount = addonCompanies.length
    const selectedCompanies = [primaryCompany, ...addonCompanies]

    // client_reference_id: Webhook が会社コードを受け取るためのキー
    //   フォーマット: {userUUID}__{code1}_{code2}
    const clientRefId = user.id + '__' + selectedCompanies.join('_')

    // ── 3. Stripe Checkout Session 作成 ──
    const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY')!, {
      apiVersion: '2024-09-30.acacia',
      httpClient: Stripe.createFetchHttpClient(),
    })

    const lineItems: Stripe.Checkout.SessionCreateParams.LineItem[] = [
      { price: PRICE_BASE, quantity: 1 },
    ]
    if (addonCount > 0) {
      lineItems.push({ price: PRICE_ADDON, quantity: addonCount })
    }
    // 初回登録料（一回限り）: subscription mode の line_items に直接追加すると初回請求にのみ含まれる
    lineItems.push({ price: PRICE_INIT_FEE, quantity: 1 })

    const session = await stripe.checkout.sessions.create({
      mode: 'subscription',
      line_items: lineItems,
      success_url: SUCCESS_URL,
      cancel_url:  CANCEL_URL,
      client_reference_id: clientRefId,
    })

    console.log('✅ Checkout Session created:', session.id, { userId: user.id, selectedCompanies })

    return json({ url: session.url })

  } catch (err) {
    console.error('❌ create-checkout error:', err)
    return json({ error: err.message }, 500)
  }
})

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}
