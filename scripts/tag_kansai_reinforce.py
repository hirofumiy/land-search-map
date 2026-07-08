#!/usr/bin/env python3
"""
関西電力『大規模な上位系統増強が必要となる地域マップ』（2026年5月時点）を
関西の変電所に参考情報として付与する。
出典: map.pdf（関西電力送配電・公式公開）。工期概ね4〜10年以上。
"""
import json, re, urllib.request, time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SUB = BASE / 'substations.json'
COMPANY = '関西電力送配電'

# 全域指定の府県
PREF_ALL = {'兵庫県': '兵庫県全域', '奈良県': '奈良県全域'}

# 市町村指定（府県ごと）→ 地域ラベル
MUNI_REGION = {}
def add(region, munis):
    for m in munis: MUNI_REGION[m] = region
add('京都府北部', ['伊根町','与謝野町','京丹後市','宮津市','福知山市','舞鶴市','綾部市'])
add('京都府南部', ['京田辺市','木津川市','精華町'])
add('大阪府北部', ['東大阪市','四條畷市','四条畷市'])
add('和歌山県北部', ['橋本市'])
add('滋賀県 湖南・湖東', ['彦根市','長浜市','東近江市','米原市','愛荘町','豊郷町','甲良町','多賀町',
                        '近江八幡市','守山市','甲賀市','野洲市','湖南市','竜王町','日野町','高島市'])

NOTE = '関西電力『大規模な上位系統増強が必要となる地域』（工期概ね4〜10年／2026年5月時点）'

def revgeo_city(lat, lng):
    """HeartRails Geo APIで市区町村名を直接取得"""
    try:
        url = f"https://geoapi.heartrails.com/api/json?method=searchByGeoLocation&x={lng}&y={lat}"
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'BL'}), timeout=15))
        loc = d.get('response', {}).get('location', [])
        return loc[0].get('city') if loc else None
    except Exception:
        return None

def strip_ward(name):
    # 「神戸市北区」→「神戸市」等、政令市の区を丸める（市単位でリスト照合）
    return re.sub(r'(市).*区$', r'\1', name)

def main():
    db = json.loads(SUB.read_text())
    feats = [f for f in db['features'] if f['properties'].get('company') == COMPANY]
    print(f'関西 変電所: {len(feats)}件')
    tagged = 0
    for i, f in enumerate(feats):
        p = f['properties']
        p.pop('kansai_reinforce', None)
        pref = p.get('prefecture', '')
        # 全域府県
        if pref in PREF_ALL:
            p['kansai_reinforce'] = {'region': PREF_ALL[pref], 'note': NOTE}
            tagged += 1
            continue
        # 市町村判定（逆ジオコード）
        lng, lat = f['geometry']['coordinates']
        mname = revgeo_city(lat, lng)
        time.sleep(0.12)
        if not mname:
            continue
        key = strip_ward(mname)
        region = MUNI_REGION.get(mname) or MUNI_REGION.get(key)
        if region:
            p['kansai_reinforce'] = {'region': region, 'note': NOTE, 'muni': mname}
            tagged += 1
        if (i + 1) % 100 == 0:
            print(f'  {i+1}/{len(feats)} … 付与 {tagged}')
    SUB.write_text(json.dumps(db, ensure_ascii=False, indent=1))
    print(f'\n✅ 参考タグ付与: {tagged}件')
    # 地域別内訳
    from collections import Counter
    c = Counter(f['properties']['kansai_reinforce']['region'] for f in feats if f['properties'].get('kansai_reinforce'))
    for r, n in c.most_common():
        print(f'   {r}: {n}')

if __name__ == '__main__':
    main()
