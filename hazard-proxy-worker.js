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
  landslide: '05_kyukeishachihousaigai',
  jisuberi:  '05_jisuberikeikaikuiki',
  tsunami:   '04_tsunami_newlegend_data',
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
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
