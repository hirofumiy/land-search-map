#!/usr/bin/env python3
"""
九州送配電: 上位系統コード → 名称ルート解決
============================================
九州の upper_grid は「変電所No.N, 送電線No.N」形式で、各地区CSVの
変電所No/送電線No を参照する（地区スコープ）。
各変電所が属する地区CSVで No→名称 を引いてルート化する。

使い方: python3 scripts/resolve_kyushu_routes.py
"""

import csv
import glob
import json
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SUBSTATIONS = BASE / "substations.json"
KYUSHU_DIR = Path("/Users/hirofumiy/Documents/Claude/substation-ocr-test/data/csv/kyushu")
COMPANY = "九州電力送配電"


def sn(s):
    s = unicodedata.normalize('NFKC', str(s))
    return (s.replace('変電所', '').replace('開閉所', '').replace("'", '')
            .replace('ケ', 'ヶ').replace('　', '').replace(' ', '').strip())


def to_num(s):
    s = str(s).replace(',', '').replace("'", '').strip()
    if s in ('', '-', '−', 'ー', '—', '―', '－'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def rank_from_mw(mw):
    if mw is None: return None
    if mw >= 20: return 'S'
    if mw >= 10: return 'A'
    if mw >= 5: return 'B'
    if mw >= 1: return 'C'
    return 'D'


def load_rows(path):
    enc = 'utf-8-sig' if open(path, 'rb').read(3) == b'\xef\xbb\xbf' else 'cp932'
    return list(csv.reader(open(path, encoding=enc, errors='replace')))


def area_key(path):
    m = re.search(r'★\s*(\d+)', Path(path).name)
    return m.group(1) if m else Path(path).parent.name


def build_areas():
    """地区 → {sub_no→{name,mw,rank}, line_no→name, subnames:set}"""
    areas = {}
    # 変圧器CSV
    for f in glob.glob(str(KYUSHU_DIR / '**/変圧器CSV/*.csv'), recursive=True):
        ak = area_key(f)
        a = areas.setdefault(ak, {'sub': {}, 'line': {}, 'subnames': set()})
        rows = load_rows(f)
        hi = next((i for i, r in enumerate(rows) if any('変電所名' in c for c in r)), None)
        if hi is None: continue
        h = rows[hi]
        no_i = next((i for i, c in enumerate(h) if c.strip().replace(' ', '') in ('変電所No', '変電所 No') or ('変電所' in c and 'No' in c)), 0)
        nm_i = next((i for i, c in enumerate(h) if '変電所名' in c), 1)
        up_i = next((i for i, c in enumerate(h) if '空容量' in c and '上位' in c), None)
        cur_i = next((i for i, c in enumerate(h) if '空容量' in c and '当該' in c), None)
        for r in rows[hi + 1:]:
            if len(r) <= max(no_i, nm_i) or not r[nm_i].strip():
                continue
            raw_no = r[no_i].replace("'", '').strip()
            base_no = re.match(r'^(\d+)', raw_no)
            if not base_no:
                continue
            no = base_no.group(1)
            name = unicodedata.normalize('NFKC', r[nm_i]).strip()
            mw = None
            for ci in (cur_i, up_i):
                if ci is not None and len(r) > ci:
                    mw = to_num(r[ci])
                    if mw is not None: break
            if no not in a['sub']:
                a['sub'][no] = {'name': name, 'mw': mw}
            a['subnames'].add(sn(name))
    # 送電線CSV
    for f in glob.glob(str(KYUSHU_DIR / '**/送電線CSV/*.csv'), recursive=True):
        ak = area_key(f)
        a = areas.setdefault(ak, {'sub': {}, 'line': {}, 'subnames': set()})
        rows = load_rows(f)
        hi = next((i for i, r in enumerate(rows) if any('送電線名' in c for c in r)), None)
        if hi is None: continue
        h = rows[hi]
        no_i = next((i for i, c in enumerate(h) if '送電線' in c and 'No' in c), 0)
        nm_i = next((i for i, c in enumerate(h) if '送電線名' in c), 1)
        for r in rows[hi + 1:]:
            if len(r) <= max(no_i, nm_i) or not r[nm_i].strip():
                continue
            raw_no = r[no_i].replace("'", '').strip()
            base_no = re.match(r'^(\d+)', raw_no)
            if not base_no: continue
            a['line'].setdefault(base_no.group(1), unicodedata.normalize('NFKC', r[nm_i]).strip())
    return areas


def main():
    print("🔗 九州送配電 上位系統ルート解決")
    areas = build_areas()
    # 変電所名(sn) → 地区
    name2area = {}
    for ak, a in areas.items():
        for nm in a['subnames']:
            name2area.setdefault(nm, ak)
    print(f"  地区数: {len(areas)} / 変電所名索引: {len(name2area)}")

    db = json.loads(SUBSTATIONS.read_text())
    feats = [f for f in db['features'] if f['properties'].get('company') == COMPANY]
    subs_with_route = 0
    resolved = 0
    total = 0
    for f in feats:
        p = f['properties']
        raw = p.get('upper_grid')
        if not raw:
            continue
        ak = name2area.get(sn(p['name']))
        if not ak or ak not in areas:
            continue
        a = areas[ak]
        route = []
        for code in [c.strip() for c in raw.split(',') if c.strip()]:
            total += 1
            node = {'code': code}
            m_sub = re.match(r'変電所No\.?\s*(\d+)', code)
            m_line = re.match(r'送電線No\.?\s*(\d+)', code)
            if m_sub and m_sub.group(1) in a['sub']:
                info = a['sub'][m_sub.group(1)]
                node['name'] = info['name']; node['type'] = '変電所'
                if info['mw'] is not None:
                    mw = int(info['mw']) if float(info['mw']).is_integer() else info['mw']
                    node['mw'] = mw; node['rank'] = rank_from_mw(mw)
                resolved += 1
            elif m_line and m_line.group(1) in a['line']:
                node['name'] = a['line'][m_line.group(1)]; node['type'] = '送電線'
                resolved += 1
            route.append(node)
        if route:
            p['upper_route'] = route
            subs_with_route += 1

    SUBSTATIONS.write_text(json.dumps(db, ensure_ascii=False, indent=1))
    print(f"  ルート付与: {subs_with_route}件 / コード解決率: {resolved}/{total} "
          f"({resolved/total*100:.1f}%)" if total else "0")
    for nm in ['加来変電所', '金の手変電所', '延岡変電所']:
        f = next((x for x in feats if x['properties']['name'] == nm), None)
        if f and f['properties'].get('upper_route'):
            print(f"\n[{nm}]")
            for n in f['properties']['upper_route']:
                cap = f" 空き{n['mw']}MW/{n.get('rank')}" if 'mw' in n else ''
                print(f"   {n['code']} → {n.get('name','(未解決)')} [{n.get('type','?')}]{cap}")


if __name__ == '__main__':
    main()
