#!/usr/bin/env python3
"""
東電PG: 上位系統コード → 名称ルート解決（②中規模）
=========================================================
予想潮流等一覧表の「見出しコード」はupper_gridのコードと同一表記。
  例) 変電所表の見出し「変茨城県 66kV 4」→ 鹿島5，7，8B
      送電線表の見出し「茨城県 66kV 1」  → 北茨城線
      基幹表     の見出し「基幹 500kV 52」→ 新古河線 等
これを使い各変電所の upper_grid を name付きルート(upper_route)に解決。
空き容量は substations.json の既存値を名称照合で再利用（地図表示と整合）。

使い方: python3 scripts/resolve_tepco_routes.py
"""

import json
import re
import unicodedata
from pathlib import Path

import fitz

BASE = Path(__file__).resolve().parent.parent
SUBSTATIONS = BASE / "substations.json"
PDF_DIR = Path("/Users/hirofumiy/Documents/Claude/substation-ocr-test/data/pdfs/update202606")
COMPANY = "東京電力パワーグリッド"

SUB_ANCHOR = re.compile(r'^変\S+?\s+(?:配電用変電所|[\d.]+kV)\s+\d+(?:-\d+)?$')
LINE_PREF_ANCHOR = re.compile(r'^[^変\s]\S*?[都道府県]\s+[\d.]+kV\s+\d+$')
LINE_KIKAN_ANCHOR = re.compile(r'^基幹\s+[\d.]+kV\s+\d+$')
SUB_KIKAN_ANCHOR = re.compile(r'^変基幹\s+[\d.]+kV\s+\d+(?:-\d+)?$')


def norm(s):
    s = unicodedata.normalize('NFKC', str(s)).strip()
    return re.sub(r'\s+', ' ', s)


def clean_name(s):
    return (unicodedata.normalize('NFKC', str(s))
            .replace('⾧', '長').replace('髙', '高').replace('﨑', '崎').strip())


def to_num(s):
    s = str(s).replace(',', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


def rank_from_mw(mw):
    if mw is None: return None
    if mw >= 20: return 'S'
    if mw >= 10: return 'A'
    if mw >= 5:  return 'B'
    if mw >= 1:  return 'C'
    return 'D'


def extract_sub_mw(fields):
    """変電所行のフィールド列から空容量(当該設備)を抽出（parse_tepco_flow準拠）"""
    f = list(fields)
    if f and re.match(r'^[\d.]+/[\d.]+$', f[0]):
        f.pop(0)  # 1次/2次電圧ペア
    head = []
    while f and len(head) < 3:
        v = to_num(f[0])
        if v is None:
            break
        head.append(v); f.pop(0)
    if len(head) < 3:
        return None
    if f and not re.match(r'^-?[\d,]+$', f[0]) and f[0] != '-':
        f.pop(0)  # 制約要因
    vals = []
    for tok in f[:4]:
        if tok == '-':
            vals.append(None)
        else:
            v = to_num(tok)
            vals.append(v if v is not None else 'STOP')
    while vals and vals[-1] == 'STOP':
        vals.pop()
    if len(vals) >= 2 and vals[1] not in (None, 'STOP'):
        return vals[1]  # 空容量(当該設備)
    return None


def build_code_index():
    """全PDFの見出しコード → {name, type, mw?, rank?} を構築"""
    idx = {}
    ANY_ANCHOR = lambda s: (SUB_ANCHOR.match(s) or SUB_KIKAN_ANCHOR.match(s)
                            or LINE_PREF_ANCHOR.match(s) or LINE_KIKAN_ANCHOR.match(s))
    for pdf in sorted(PDF_DIR.glob('tepco_*.pdf')):
        doc = fitz.open(str(pdf))
        for page in doc:
            text = page.get_text()
            is_line = '予想潮流等一覧表（送電線）' in text
            is_sub = '予想潮流等一覧表（変電所）' in text
            if not (is_line or is_sub):
                continue
            toks = [t.strip() for t in text.split('\n') if t.strip()]
            for i, t in enumerate(toks):
                code = None; typ = None
                if is_sub and (SUB_ANCHOR.match(t) or SUB_KIKAN_ANCHOR.match(t)):
                    code = t; typ = '基幹変電所' if t.startswith('変基幹') else '変電所'
                elif is_line and (LINE_PREF_ANCHOR.match(t) or LINE_KIKAN_ANCHOR.match(t)):
                    code = t; typ = '基幹送電線' if t.startswith('基幹') else '送電線'
                if not code:
                    continue
                nxt = toks[i + 1] if i + 1 < len(toks) else ''
                if ANY_ANCHOR(nxt) or not nxt or nxt.isdigit():
                    continue
                key = norm(code)
                if key in idx:
                    continue
                entry = {'name': clean_name(nxt), 'type': typ}
                # 変電所系は空容量(当該設備)を抽出
                if typ in ('変電所', '基幹変電所'):
                    j = i + 2; fields = []
                    while j < len(toks) and not ANY_ANCHOR(toks[j]):
                        fields.append(toks[j]); j += 1
                        if len(fields) > 18: break
                    mw = extract_sub_mw(fields)
                    if mw is not None:
                        mw = int(mw) if float(mw).is_integer() else mw
                        entry['mw'] = mw
                        entry['rank'] = rank_from_mw(mw)
                idx[key] = entry
        doc.close()
    return idx


def main():
    print("🔗 東電PG 上位系統ルート解決")
    code_idx = build_code_index()
    print(f"  見出しコード索引: {len(code_idx)}件")

    db = json.loads(SUBSTATIONS.read_text())
    tepco = [f for f in db['features'] if f['properties'].get('company') == COMPANY]

    resolved_codes = 0
    total_codes = 0
    subs_with_route = 0
    for f in tepco:
        p = f['properties']
        raw = p.get('upper_grid')
        if not raw:
            continue
        codes = [c.strip() for c in raw.split(',') if c.strip()]
        route = []
        for c in codes:
            total_codes += 1
            info = code_idx.get(norm(c))
            node = {'code': c}
            if info:
                resolved_codes += 1
                node['name'] = info['name']
                node['type'] = info['type']
                if 'mw' in info:
                    node['mw'] = info['mw']
                    node['rank'] = info['rank']
            route.append(node)
        if route:
            p['upper_route'] = route
            subs_with_route += 1

    db.setdefault('metadata', {})['upper_route_added'] = {
        'company': COMPANY, 'note': '上位系統コードを名称解決（東電PG）。変電所ノードは空き容量付き。',
    }
    SUBSTATIONS.write_text(json.dumps(db, ensure_ascii=False, indent=1))

    print(f"  ルート付与変電所: {subs_with_route}件")
    print(f"  コード解決率: {resolved_codes}/{total_codes} "
          f"({resolved_codes/total_codes*100:.1f}%)" if total_codes else "  0")
    # スポットチェック
    for name in ['潮来変電所', '鹿嶋変電所', '日立変電所']:
        f = next((x for x in tepco if x['properties']['name'] == name), None)
        if f and f['properties'].get('upper_route'):
            print(f"\n[{name}]")
            for n in f['properties']['upper_route']:
                cap = f" 空き{n['mw']}MW/{n.get('rank')}" if 'mw' in n else ''
                print(f"   {n['code']} → {n.get('name','(未解決)')} [{n.get('type','?')}]{cap}")


if __name__ == '__main__':
    main()
