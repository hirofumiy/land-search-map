#!/usr/bin/env python3
"""
接続検討インテリジェンス（上位系統逼迫の実事例）を構築
=========================================================
・野崎氏/日本エネルギー Excel の3案件
・接続検討継続判断メール一覧 の13案件
を座標化し、最寄り（または名指し）変電所に紐付けて congestion_intel.json を出力。
※機微情報のため、UI側で hirofumiy@gmail.com のみ表示。
"""
import json, urllib.request, urllib.parse, math, time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
subs = json.load(open(BASE / 'substations.json'))['features']

def geocode(q):
    for query in [q, q.rstrip('0123456789０-９-字ノヶ番地')]:
        try:
            url = f"https://msearch.gsi.go.jp/address-search/AddressSearch?q={urllib.parse.quote(query)}"
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'BL'}), timeout=15))
            if d:
                c = d[0]['geometry']['coordinates']
                return round(c[1], 6), round(c[0], 6)
        except Exception:
            pass
        time.sleep(0.3)
    return None, None

def find_named(name, company):
    for f in subs:
        p = f['properties']
        if p.get('company') == company and (p['name'] == name or p['name'] == name + '変電所'):
            s = f['geometry']['coordinates']
            return p, s[1], s[0]
    return None, None, None

def nearest(lat, lng, company):
    best = None; bd = 1e9
    for f in subs:
        p = f['properties']
        if p.get('company') != company: continue
        slng, slat = f['geometry']['coordinates']
        d = math.hypot((slat - lat) * 111, (slng - lng) * 91)
        if d < bd: bd = d; best = (p, slat, slng)
    return best, round(bd, 1)

# (id, source, company, title, address, upstream, work, cost, charge_limit, result, date, severity, named_sub)
CASES = [
 # ── 野崎氏/日本エネルギー Excel 3案件 ──
 ('N17','日本エネルギー(野崎)','関西電力送配電','高島市 青柳（No.17）','滋賀県高島市安曇川町青柳1334',
  '上位系統（設備名の明示なし）','4〜5年','概算負担金 約2.5億円','—','難しいと判断','2026/ー','high',None),
 ('N48','日本エネルギー(野崎)','関西電力送配電','米原市 天満（No.48）','滋賀県米原市天満280',
  '上位系統（設備名の明示なし）','8年以上','概算負担金 数十億円','—','難しいと判断','2026/ー','high',None),
 ('N38','日本エネルギー(野崎)','関西電力送配電','京丹波町 広野牧（No.38）','京都府船井郡京丹波町広野牧5',
  '上位系統（設備名の明示なし）','5年以上','—','—','難しいと判断','2026/ー','high',None),
 # ── 接続検討継続判断メール 13案件 ──
 ('H1','接続検討メール','中部電力パワーグリッド','飛騨高山蓄電池（CB-GI004）','岐阜県高山市',
  '供給元設備（別添）','別添','別添','—','詳細検討で不要の可能性','2025/12/17','medium',None),
 ('H2','接続検討メール','中部電力パワーグリッド','荘川六厩蓄電所','岐阜県高山市荘川町六厩',
  '充電（順潮流）側の上位系統','充電制限ありなら回答どおり','制限ありなら回答どおり／なしは大幅増','適用可','充電制限ありで継続→供給承諾取得','2026/4/28','resolved',None),
 ('H3','接続検討メール','中部電力パワーグリッド','シューワ様小牧','愛知県小牧市',
  '特別高圧系統（逆潮流NF）＋配電用変電所・配電塔','数年に及ぶ可能性','高額となる可能性','—','取り下げ(2026/6/11)','2026/5/28','high',None),
 ('H4','接続検討メール','関西電力送配電','カルド林田町蓄電池（KR25276）','兵庫県姫路市林田町',
  '上位系設備（設備名の明示なし）','約7年以上','高額になる虞','—','増強要否を確認中','2026/4/9','high',None),
 ('H5','接続検討メール','関西電力送配電','シューワ様滋賀（YR08057）','滋賀県東近江市',
  '上位系変電所設備（湖東・湖南）','約8年以上','数十億円規模の虞','—','継続要否を回答依頼中','2026/7/1','high',None),
 ('H6','接続検討メール','関西電力送配電','KS-WK006','和歌山県田辺市',
  '接続検討回答書ベース','—','概算 約2.8億円','—','取り下げ(2026/5/11)','2026/2/16','high',None),
 ('H7','接続検討メール','九州電力送配電','カルド和水町蓄電池（No.35326）','熊本県玉名郡和水町',
  '①66kV配電用変圧器 ②220kV主要変圧器','①4年以上 ②5年以上','①約2億円 ②10億円以上','①不可 ②可','継続意思確認','2026/5/20','high',None),
 ('H8','接続検討メール','九州電力送配電','カルド多良木植木蓄電池（No.34179）','熊本県球磨郡多良木町',
  '66kV お客さま人吉線','6年以上','20億円以上','適用不可(12h超)','辞退(2026/6/8)','2026/6/8','high',None),
 ('H10','接続検討メール','九州電力送配電','カルド大口蓄電池（No.35323）','鹿児島県伊佐市大口下殿',
  '大口変電所 3号配変（15→30MVA取替）','約2.5年','約3億円','—','継続意思確認','2026/5/21','high','大口'),
 ('H11','接続検討メール','九州電力送配電','カルド寺師蓄電池（No.34020）','鹿児島県姶良市寺師',
  '帖佐変電所 2号配変（20→30MVA取替）','約2.5年','約3億円','—','継続意思の再確認','2026/5/21','high','帖佐'),
 ('H12','接続検討メール','九州電力送配電','カルド溝辺町蓄電池（No.34018）','鹿児島県霧島市溝辺町',
  '設備名の明示なし','—','概算提示','—','辞退(2026/3/12)','2026/3/10','high',None),
 ('H13','接続検討メール','九州電力送配電','田川郡福智町蓄電池（No.28286）','福岡県田川郡福智町',
  '糸田変電所 最寄り／送電線増強＋配電対策','10年単位','数十億','適用不可','事業性判断を要請(実質NG)','2025/12/9','high','糸田'),
]

out = []
for (cid, src, comp, title, addr, upstream, work, cost, chg, result, date, sev, named) in CASES:
    p = slat = slng = None
    linked = None
    if named:
        p, slat, slng = find_named(named, comp)
    lat, lng = geocode(addr)
    if p is None and lat is not None:
        (np, nslat, nslng), d = nearest(lat, lng, comp)
        p = np; linked = {'name': np['name'], 'distance_km': d,
                          'available_mw': np.get('available_capacity_mw'),
                          'rank': np.get('estimated_cost_rank'),
                          'upper_considered_mw': np.get('upper_considered_mw'), 'relation': '最寄り'}
    elif p is not None:
        linked = {'name': p['name'], 'distance_km': 0,
                  'available_mw': p.get('available_capacity_mw'),
                  'rank': p.get('estimated_cost_rank'),
                  'upper_considered_mw': p.get('upper_considered_mw'), 'relation': '名指し'}
        if lat is None: lat, lng = slat, slng
    out.append({
        'id': cid, 'source': src, 'company': comp, 'title': title, 'address': addr,
        'lat': lat, 'lng': lng, 'upstream': upstream, 'work_years': work, 'cost': cost,
        'charge_limit': chg, 'result': result, 'date': date, 'severity': sev,
        'linked_substation': linked,
    })
    print(f"{cid} {title[:20]} → ({lat},{lng}) 紐付:{linked['name'] if linked else '—'}")

result = {
    'title': '接続検討インテリジェンス（上位系統逼迫の実事例）',
    'visibility': 'private:hirofumiy@gmail.com',
    'note': '公開空き容量が良好でも、実際の接続検討で上位系統逼迫（高額負担金・長工期）が判明した事例。用地判断の参考に。',
    'sources': ['日本エネルギー様 在庫確認Excel(2026/6/22)', '接続検討継続判断メール一覧(2026/7/2)'],
    'cases': out,
}
(BASE / 'congestion_intel.json').write_text(json.dumps(result, ensure_ascii=False, indent=1))
print(f"\n✅ {len(out)}件 → congestion_intel.json")
