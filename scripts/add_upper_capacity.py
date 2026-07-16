#!/usr/bin/env python3
"""
上位系考慮の空き容量（空容量(上位系等考慮)）を各変電所に付与
================================================================
各社の予想潮流等一覧表（変圧器）には「空容量(上位系等考慮)（MW）」列があり、
上位系統の混雑を織り込んだ空き容量が公開されている。
= 「上位系統の空き状況」そのもの。関西も含め全CSV社で付与できる。

substations.json に upper_considered_mw を追加（名称照合・追加のみ）。
使い方: python3 scripts/add_upper_capacity.py
"""

import csv
import glob
import json
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SUBSTATIONS = BASE / "substations.json"
CSVROOT = Path("/Users/hirofumiy/Documents/Claude/substation-ocr-test/data/csv")

# 会社 → (CSVグロブ, 変電所名列を含むヘッダ判定)
COMPANIES = {
    "東北電力ネットワーク":   ["tohoku_new/*_tr_*.csv"],
    "北海道電力ネットワーク": ["hokkaido_flat/*.csv"],
    "九州電力送配電":         ["kyushu_flat/*.csv"],
    "中国電力ネットワーク":   ["chugoku_flat/*.csv"],
    "関西電力送配電":         ["kansai_new/154kv_less_trans.csv", "kansai_new/154kv_more_trans.csv"],
    "中部電力パワーグリッド": ["chubu_flat/*.csv"],
}


def sn(s):
    s = unicodedata.normalize('NFKC', str(s))
    s = (s.replace('変電所', '').replace('開閉所', '').replace("'", '')
          .replace('⾧', '長').replace('髙', '高').replace('﨑', '崎')
          .replace('ケ', 'ヶ').replace('　', '').replace(' ', '').strip())
    return s


def to_num(s):
    s = str(s).replace(',', '').replace("'", '').strip()
    if s in ('', '-', '−', 'ー', '—', '―', '－'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_rows(path):
    enc = 'utf-8-sig' if open(path, 'rb').read(3) == b'\xef\xbb\xbf' else 'cp932'
    with open(path, encoding=enc, errors='replace') as fh:
        return list(csv.reader(fh))


def build_map(globs):
    """name(sn) → 上位系考慮空容量(MW)。重複は大きい方"""
    m = {}
    for g in globs:
        for path in glob.glob(str(CSVROOT / g), recursive=True):
            rows = load_rows(path)
            hi = next((i for i, r in enumerate(rows) if any('変電所名' in c for c in r)), None)
            if hi is None:
                continue
            hdr = rows[hi]
            name_i = next((i for i, c in enumerate(hdr) if '変電所名' in c), None)
            up_i = next((i for i, c in enumerate(hdr)
                         if '空容量' in c and ('上位系' in c or '上位' in c)), None)
            if name_i is None or up_i is None:
                continue
            for r in rows[hi + 1:]:
                if len(r) <= max(name_i, up_i) or not r[name_i].strip():
                    continue
                key = sn(r[name_i])
                val = to_num(r[up_i])
                if not key or val is None:
                    continue
                if key not in m or val > m[key]:
                    m[key] = val
    return m


def main():
    print("🔗 上位系考慮空容量の付与")
    db = json.loads(SUBSTATIONS.read_text())
    total_added = 0
    for comp, globs in COMPANIES.items():
        m = build_map(globs)
        feats = [f for f in db['features'] if f['properties'].get('company') == comp]
        added = 0
        tighter = 0
        for f in feats:
            p = f['properties']
            v = m.get(sn(p['name']))
            if v is None:
                continue
            v = int(v) if float(v).is_integer() else v
            p['upper_considered_mw'] = v
            added += 1
            own = p.get('available_capacity_mw')
            if isinstance(own, (int, float)) and v < own:
                tighter += 1
        total_added += added
        print(f"  {comp}: 付与 {added}/{len(feats)}（上位系がボトルネック {tighter}件）")
    SUBSTATIONS.write_text(json.dumps(db, ensure_ascii=False, indent=1))
    print(f"\n合計付与: {total_added}件")


if __name__ == '__main__':
    main()
