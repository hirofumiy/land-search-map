// Supabase Edge Function: notify-line
// BatteryLandに新規ユーザーが登録した際、ひろさんのLINEへ通知を送ります
//
// 【デプロイ方法】
// 1. Supabase Dashboard → Edge Functions → New Function
// 2. 関数名: notify-line
// 3. このコードを貼り付けてデプロイ
// 4. Settings → Edge Functions → Secrets に以下を追加:
//    - LINE_CHANNEL_ACCESS_TOKEN: LINEチャンネルアクセストークン
//    - LINE_USER_ID: ひろさんのLINE User ID

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req: Request) => {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const { name, email } = await req.json()

    const LINE_TOKEN = Deno.env.get('LINE_CHANNEL_ACCESS_TOKEN')
    const LINE_USER_ID = Deno.env.get('LINE_USER_ID')

    if (!LINE_TOKEN || !LINE_USER_ID) {
      console.error('LINE credentials not set in Edge Function secrets')
      return new Response(
        JSON.stringify({ ok: false, error: 'LINE credentials not configured' }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 500 }
      )
    }

    const now = new Date().toLocaleString('ja-JP', {
      timeZone: 'Asia/Tokyo',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })

    const message = `🔔 BatteryLand 新規登録
━━━━━━━━━━━━
👤 名前: ${name}
📧 メール: ${email}
🕐 登録日時: ${now}
━━━━━━━━━━━━
3日間の無料トライアルが開始されました。`

    const res = await fetch('https://api.line.me/v2/bot/message/push', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${LINE_TOKEN}`,
      },
      body: JSON.stringify({
        to: LINE_USER_ID,
        messages: [{ type: 'text', text: message }],
      }),
    })

    if (!res.ok) {
      const errText = await res.text()
      console.error('LINE API error:', res.status, errText)
      return new Response(
        JSON.stringify({ ok: false, error: `LINE API: ${res.status}` }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 500 }
      )
    }

    return new Response(
      JSON.stringify({ ok: true }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )
  } catch (err) {
    console.error('Edge Function error:', err)
    return new Response(
      JSON.stringify({ ok: false, error: String(err) }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 500 }
    )
  }
})
