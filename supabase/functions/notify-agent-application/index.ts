// =====================================================
// BatteryLand Edge Function: notify-agent-application
// 代理店申込時に管理者LINEへ通知する
// =====================================================

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

serve(async (req: Request) => {
  // CORS プリフライト
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const body = await req.json();
    const {
      company_name,
      contact_name,
      contact_email,
      phone,
      message,
    } = body;

    // 必須項目チェック
    if (!company_name || !contact_email) {
      return new Response(
        JSON.stringify({ ok: false, error: "company_name and contact_email are required" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const lineToken = Deno.env.get("LINE_CHANNEL_ACCESS_TOKEN");
    const lineUserId = Deno.env.get("LINE_USER_ID");

    if (!lineToken || !lineUserId) {
      console.error("LINE secrets not configured");
      return new Response(
        JSON.stringify({ ok: false, error: "LINE not configured" }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // 日本時間での現在時刻
    const now = new Date().toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" });

    // LINEメッセージ本文
    const lineMessage = [
      "🤝【代理店申込通知】",
      `━━━━━━━━━━━━━━`,
      `📌 会社名: ${company_name}`,
      `👤 担当者: ${contact_name || "（未記入）"}`,
      `📧 メール: ${contact_email}`,
      `📞 電話: ${phone || "（未記入）"}`,
      ``,
      `💬 メッセージ:`,
      message ? message : "（なし）",
      ``,
      `⏰ 申込日時: ${now}`,
      `━━━━━━━━━━━━━━`,
      `⚡ BatteryLand 代理店プログラム`,
    ].join("\n");

    // LINE Messaging API push通知
    const lineRes = await fetch("https://api.line.me/v2/bot/message/push", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${lineToken}`,
      },
      body: JSON.stringify({
        to: lineUserId,
        messages: [
          {
            type: "text",
            text: lineMessage,
          },
        ],
      }),
    });

    const lineBody = await lineRes.json().catch(() => ({}));

    if (!lineRes.ok) {
      console.error("LINE API error:", lineRes.status, lineBody);
      return new Response(
        JSON.stringify({ ok: false, status: lineRes.status, detail: lineBody }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    console.log(`代理店申込通知送信成功: ${company_name} <${contact_email}>`);

    return new Response(
      JSON.stringify({ ok: true }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    console.error("notify-agent-application error:", err);
    return new Response(
      JSON.stringify({ ok: false, error: String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
