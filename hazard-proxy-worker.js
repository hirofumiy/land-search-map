/**
 * BatteryLand – Hazard Tile Proxy Worker
 * deploy先: Cloudflare Workers
 * Worker名: hazard-proxy（→ hazard-proxy.440marketing.workers.dev）
 *
 * リクエストURL形式:
 *   /{type}/{z}/{x}/{y}.png
 *   例) /flood/14/14508/6453.png
 */

const TYPE_MAP = {
  flood:     '01_flood_l2_shinsuishin_data',
  sediment:  '05_dosekiryukeikaikuiki',
  landslide: '05_kyukeishakeikaikuiki',   // 旧: 05_kyukeishachihousaigai（危険箇所）→ 新: 警戒区域（重ねるハザードマップ準拠）
  jisuberi:  '05_jisuberikeikaikuiki',
  tsunami:   '04_tsunami_newlegend_data',
};

// Google Maps 短縮URLの展開を許可するホスト（オープンリダイレクト/SSRF防止）
const RESOLVE_ALLOWED_HOSTS = ['maps.app.goo.gl', 'goo.gl', 'g.co', 'maps.google.com'];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // ── /resolve?u=<短縮URL> : リダイレクト先の最終URLを返す ──
    if (url.pathname === '/resolve') {
      const cors = { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json' };
      const target = url.searchParams.get('u');
      if (!target) return new Response(JSON.stringify({ error: 'missing u' }), { status: 400, headers: cors });
      let host;
      try { host = new URL(target).hostname; } catch { return new Response(JSON.stringify({ error: 'bad url' }), { status: 400, headers: cors }); }
      if (!RESOLVE_ALLOWED_HOSTS.some(h => host === h || host.endsWith('.' + h))) {
        return new Response(JSON.stringify({ error: 'host not allowed' }), { status: 403, headers: cors });
      }
      const reqHeaders = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept-Language': 'ja,en;q=0.8',
      };
      try {
        // ① まず最初のリダイレクト先（Locationヘッダ）だけ読む。
        //    最終のmapsページを取得しないことでGoogleのbot検知(/sorry)を回避。
        const r1 = await fetch(target, { redirect: 'manual', headers: reqHeaders });
        let loc = r1.headers.get('Location');
        if (loc) {
          try { loc = new URL(loc, target).href; } catch (e) {}
          if (!/\/sorry\/|consent\.google|accounts\.google/i.test(loc)) {
            return new Response(JSON.stringify({ url: loc }), { status: 200, headers: cors });
          }
        }
        // ② Locationが無い/bot検知 → bodyからmaps URLか座標を探す（Firebase Dynamic Links対策）
        const r2 = (r1.status >= 200 && r1.status < 300) ? r1
                 : await fetch(target, { redirect: 'follow', headers: reqHeaders });
        const body = await r2.text();
        const mUrl = body.match(/https?:\/\/(?:www\.)?google\.[a-z.]+\/maps\/[^"'<>\\\s]+/i);
        if (mUrl) return new Response(JSON.stringify({ url: mUrl[0] }), { status: 200, headers: cors });
        const mAt = body.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/) || body.match(/[?&]center=(-?\d+\.\d+)(?:%2C|,)(-?\d+\.\d+)/i);
        if (mAt) return new Response(JSON.stringify({ url: `@${mAt[1]},${mAt[2]}` }), { status: 200, headers: cors });
        return new Response(JSON.stringify({ error: 'no coords' }), { status: 422, headers: cors });
      } catch (e) {
        return new Response(JSON.stringify({ error: 'fetch failed' }), { status: 502, headers: cors });
      }
    }

    const parts = url.pathname.split('/').filter(Boolean); // ['flood','14','14508','6453.png']

    if (parts.length !== 4) {
      return new Response('Bad Request', { status: 400 });
    }

    const [type, z, x, yPng] = parts;
    const upstreamPath = TYPE_MAP[type];

    if (!upstreamPath) {
      return new Response('Unknown hazard type', { status: 404 });
    }

    // キャッシュキーを正規化（Workerのリクエストそのもの）
    const cache = caches.default;
    const cacheKey = new Request(request.url);

    // キャッシュヒット確認
    let response = await cache.match(cacheKey);
    if (response) {
      return response;
    }

    // 政府サーバーから取得
    const upstream = `https://disaportaldata.gsi.go.jp/raster/${upstreamPath}/${z}/${x}/${yPng}`;

    let fetched;
    try {
      fetched = await fetch(upstream, {
        headers: { 'User-Agent': 'BatteryLand-HazardProxy/1.0' },
      });
    } catch {
      return new Response('Upstream fetch failed', { status: 502 });
    }

    // 404（ハザード指定なしエリア）は透明1pxを返してキャッシュ
    if (fetched.status === 404) {
      const emptyPng = new Uint8Array([
        137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,
        0,0,0,1,0,0,0,1,8,6,0,0,0,31,21,196,137,
        0,0,0,11,73,68,65,84,120,156,98,0,1,0,0,5,0,1,
        13,10,45,180,0,0,0,0,73,69,78,68,174,66,96,130
      ]);
      response = new Response(emptyPng, {
        status: 200,
        headers: {
          'Content-Type': 'image/png',
          'Cache-Control': 'public, max-age=3600',
          'Access-Control-Allow-Origin': '*',
        },
      });
      ctx.waitUntil(cache.put(cacheKey, response.clone()));
      return response;
    }

    if (!fetched.ok) {
      return new Response('Upstream error', { status: fetched.status });
    }

    // 正常取得 → 24時間キャッシュして返す
    const headers = new Headers(fetched.headers);
    headers.set('Cache-Control', 'public, max-age=86400');
    headers.set('Access-Control-Allow-Origin', '*');
    headers.delete('Set-Cookie');

    response = new Response(fetched.body, {
      status: 200,
      headers,
    });

    ctx.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  },
};
