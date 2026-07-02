#!/usr/bin/env python3
"""
中部電力PG: 上位系統コード → 名称ルート解決
=============================================
中部のupper_gridコード（変N・送N）は、500/275kV基幹一覧表のNoを指す。
  変1  → 500/275kV変電所一覧 No.1  = 西部変電所
  送170 → 275kV以上送電線一覧 No.170 = 鈴鹿幹線
基幹表のNo→名称対応でupper_routeを構築する。
空容量は基幹表で公開されている場合のみ併記（多くは「-」非公開）。

使い方: python3 scripts/resolve_chubu_routes.py
"""

import csv
import json
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SUBSTATIONS = BASE / "substations.json"
KIKAN_DIR = Path("/Users/hirofumiy/Documents/Claude/substation-ocr-test/data/csv/chubu/KRSIH010")
COMPANY = "中部電力パワーグリッド"

SUB_CSV = KIKAN_DIR / "500／275kV変電所空容量・予想潮流一覧表.csv"
LINE_CSVS = [
    KIKAN_DIR / "275kV以上送電線空容量・予想潮流一覧表.csv",
    KIKAN_DIR / "275kV以上送電線空容量・予想潮流一覧表（フェンス）.csv",
]

MISSING = {'', '-', '−', 'ー', '—', '―', '－'}


def rd(p):
    enc = 'utf-8-sig' if open(p, 'rb').read(3) == b'\xef\xbb\xbf' else 'cp932'
    return list(csv.reader(open(p, encoding=enc, errors='replace')))


def to_num(s):
    s = str(s).replace(',', '').strip()
    if s in MISSING:
        return None
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


def clean(s):
    return unicodedata.normalize('NFKC', str(s)).strip()


def parse_sub_csv(path, typ):
    """変電所CSV → {No: {name, type, mw?, rank?}}"""
    out = {}
    rows = rd(path)
    try:
        hdr_i = next(i for i, r in enumerate(rows) if any('変電所名' in c for c in r))
    except StopIteration:
        return out
    hdr = rows[hdr_i]
    avail_i = next((i for i, c in enumerate(hdr) if '空容量' in c and '当該' in c), None)
    if avail_i is None:
        avail_i = next((i for i, c in enumerate(hdr) if '空容量' in c), None)
    v1_i = next((i for i, c in enumerate(hdr) if '一次' in c), None)
    for r in rows[hdr_i + 1:]:
        if len(r) < 2 or not r[0].strip().isdigit():
            continue
        no = r[0].strip()
        entry = {'name': clean(r[1]), 'type': typ}
        if v1_i is not None and len(r) > v1_i and r[v1_i].strip().replace('.', '').isdigit():
            entry['name'] += f"（{r[v1_i].strip()}kV）"
        mw = to_num(r[avail_i]) if avail_i is not None and len(r) > avail_i else None
        if mw is not None:
            mw = int(mw) if float(mw).is_integer() else mw
            entry['mw'] = mw
            entry['rank'] = rank_from_mw(mw)
        out.setdefault(no, entry)
    return out


def parse_line_csv(path, typ):
    out = {}
    rows = rd(path)
    try:
        hdr_i = next(i for i, r in enumerate(rows) if any('送電線名' in c for c in r))
    except StopIteration:
        return out
    for r in rows[hdr_i + 1:]:
        if len(r) < 2 or not r[0].strip().isdigit():
            continue
        out.setdefault(r[0].strip(), {'name': clean(r[1]), 'type': typ})
    return out


def build_indices():
    # 基幹（500/275kV）
    subs = parse_sub_csv(SUB_CSV, '基幹変電所')
    lines = {}
    for p in LINE_CSVS:
        if p.exists():
            lines.update(parse_line_csv(p, '基幹送電線'))
    # エリア（154kV以下）: 全エリアでNo一意（検証済み）
    import glob as _g
    for p in _g.glob(str(KIKAN_DIR.parent / 'KRSIH01[1-6]' / '*変電所*.csv')):
        for no, e in parse_sub_csv(Path(p), '変電所').items():
            subs.setdefault(no, e)
    for p in _g.glob(str(KIKAN_DIR.parent / 'KRSIH01[1-6]' / '*送電線*.csv')):
        for no, e in parse_line_csv(Path(p), '送電線').items():
            lines.setdefault(no, e)
    return subs, lines


def main():
    print("🔗 中部電力PG 上位系統ルート解決")
    subs, lines = build_indices()
    print(f"  基幹変電所索引: {len(subs)}件 / 基幹送電線索引: {len(lines)}件")

    db = json.loads(SUBSTATIONS.read_text())
    chubu = [f for f in db['features'] if f['properties'].get('company') == COMPANY]

    resolved = total = with_route = 0
    for f in chubu:
        p = f['properties']
        raw = p.get('upper_grid')
        if not raw:
            continue
        codes = [c.strip() for c in raw.split(',') if c.strip()]
        route = []
        for c in codes:
            total += 1
            node = {'code': c}
            m = re.match(r'^(変|送)(\d+)$', c)
            if m:
                idx = subs if m.group(1) == '変' else lines
                info = idx.get(m.group(2))
                if info:
                    resolved += 1
                    node.update(info)
            route.append(node)
        if route:
            p['upper_route'] = route
            with_route += 1

    SUBSTATIONS.write_text(json.dumps(db, ensure_ascii=False, indent=1))
    print(f"  ルート付与: {with_route}件 / コード解決率: {resolved}/{total} ({resolved/total*100:.1f}%)")
    for nm in ['尾鷲変電所', '岡崎変電所', '松阪変電所']:
        f = next((x for x in chubu if x['properties']['name'] == nm), None)
        if f and f['properties'].get('upper_route'):
            print(f"\n[{nm}]")
            for n in f['properties']['upper_route']:
                cap = f" 空き{n['mw']}MW/{n.get('rank')}" if 'mw' in n else ''
                print(f"   {n['code']} → {n.get('name','(未解決)')} [{n.get('type','?')}]{cap}")


if __name__ == '__main__':
    main()
