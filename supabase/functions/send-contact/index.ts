// Supabase Edge Function: send-contact
// お問い合わせフォームの送信処理
// - 管理者（info@440marketing.biz）に通知メール
// - 送信者に受付確認メール
//
// 【必要な Supabase Secrets】
//   RESEND_API_KEY: Resend API キー

const ADMIN_EMAIL = 'info@440marketing.biz'
const FROM_EMAIL  = 'BatteryLand <onboarding@resend.dev>'

const CATEGORY_LABELS: Record<string, string> = {
  plan:     'プラン・料金について',
  function: '機能・操作について',
  trial:    'トライアルについて',
  billing:  '請求・決済について',
  data:     '変電所・データについて',
  other:    'その他',
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: corsHeaders })
  if (req.method !== 'POST') return json({ error: 'Method not allowed' }, 405)

  const resendKey = Deno.env.get('RESEND_API_KEY')
  if (!resendKey) return json({ error: 'RESEND_API_KEY not configured' }, 500)

  try {
    const { name, email, category, message, company } = await req.json()

    // バリデーション
    if (!name || !email || !category || !message) {
      return json({ error: '必須項目が不足しています' }, 400)
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return json({ error: 'メールアドレスの形式が正しくありません' }, 400)
    }

    const categoryLabel = CATEGORY_LABELS[category] ?? category
    const companyLine   = company ? `<tr><td style="padding:8px;color:#64748b;width:130px;">会社名</td><td style="padding:8px;">${company}</td></tr>` : ''

    // ── 管理者への通知メール ──
    const adminHtml = `
      <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px;border:1px solid #e2e8f0;border-radius:8px;">
        <h2 style="color:#1e293b;margin-bottom:16px;">📩 お問い合わせが届きました</h2>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          ${companyLine}
          <tr style="border-bottom:1px solid #f1f5f9;">
            <td style="padding:8px;color:#64748b;width:130px;">お名前</td>
            <td style="padding:8px;font-weight:600;">${name}</td>
          </tr>
          <tr style="border-bottom:1px solid #f1f5f9;">
            <td style="padding:8px;color:#64748b;">メール</td>
            <td style="padding:8px;"><a href="mailto:${email}" style="color:#2563eb;">${email}</a></td>
          </tr>
          <tr style="border-bottom:1px solid #f1f5f9;">
            <td style="padding:8px;color:#64748b;">種別</td>
            <td style="padding:8px;">${categoryLabel}</td>
          </tr>
          <tr>
            <td style="padding:8px;color:#64748b;vertical-align:top;">内容</td>
            <td style="padding:8px;white-space:pre-wrap;">${message.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</td>
          </tr>
        </table>
        <p style="margin-top:20px;font-size:12px;color:#94a3b8;">このメールはBatteryLandのお問い合わせフォームから自動送信されています。</p>
      </div>
    `

    // ── 送信者への受付確認メール ──
    const userHtml = `
      <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px;border:1px solid #e2e8f0;border-radius:8px;">
        <h2 style="color:#1e293b;margin-bottom:8px;">⚡ BatteryLand お問い合わせ受付確認</h2>
        <p style="font-size:14px;color:#475569;margin-bottom:20px;">${name} 様、お問い合わせありがとうございます。<br>以下の内容で受け付けました。通常2営業日以内にご返信いたします。</p>
        <table style="width:100%;border-collapse:collapse;font-size:13px;background:#f8fafc;border-radius:6px;overflow:hidden;">
          <tr style="border-bottom:1px solid #e2e8f0;">
            <td style="padding:8px 12px;color:#64748b;width:110px;">種別</td>
            <td style="padding:8px 12px;">${categoryLabel}</td>
          </tr>
          <tr>
            <td style="padding:8px 12px;color:#64748b;vertical-align:top;">内容</td>
            <td style="padding:8px 12px;white-space:pre-wrap;">${message.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</td>
          </tr>
        </table>
        <p style="margin-top:20px;font-size:13px;color:#475569;">
          お急ぎの場合は <a href="mailto:${ADMIN_EMAIL}" style="color:#2563eb;">${ADMIN_EMAIL}</a> までご連絡ください。
        </p>
        <p style="margin-top:16px;font-size:12px;color:#94a3b8;">
          合同会社440 / BatteryLand<br>
          〒558-0041 大阪府大阪市住吉区万代4-12-15-1F
        </p>
      </div>
    `

    // 2通並列送信
    const [adminRes, userRes] = await Promise.all([
      sendMail(resendKey, FROM_EMAIL, ADMIN_EMAIL,
        `【BatteryLand お問い合わせ】${categoryLabel}（${name}）`, adminHtml),
      sendMail(resendKey, FROM_EMAIL, email,
        '【BatteryLand】お問い合わせを受け付けました', userHtml),
    ])

    if (!adminRes.ok) {
      const err = await adminRes.text()
      console.error('❌ Admin mail error:', err)
      throw new Error('管理者への通知メール送信に失敗しました')
    }
    if (!userRes.ok) {
      const err = await userRes.text()
      console.warn('⚠️ User confirmation mail error:', err) // 確認メール失敗は警告のみ
    }

    console.log(`✅ お問い合わせ受付: ${name} <${email}> [${categoryLabel}]`)
    return json({ success: true })

  } catch (err) {
    console.error('❌ send-contact error:', err)
    return json({ error: err.message }, 500)
  }
})

async function sendMail(apiKey: string, from: string, to: string, subject: string, html: string) {
  return fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ from, to, subject, html }),
  })
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}
