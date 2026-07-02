#!/usr/bin/env python3
"""
substations.json に上位系統コード（upper_grid）を付与
======================================================
各社公式「予想潮流等一覧表」の「上位系設備」欄の設備コードを
そのまま各変電所の properties.upper_grid に保持する（①軽い方式）。

ソース:
  - 東電PG: 予想潮流PDF（行末尾の上位系等リスト）
  - 東北/北海道/九州/関西/中国/中部: 変電所（変圧器）CSVの上位系設備列

使い方:
  python3 scripts/add_upper_grid.py
"""

import csv
import glob
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SUBSTATIONS = BASE / "substations.json"
CSV_BASE = Path("/Users/hirofumiy/Documents/Claude/substation-ocr-test/data/csv")
PDF_DIR = Path("/Users/hirofumiy/Documents/Claude/substation-ocr-test/data/pdfs/update202606")

MISSING = {'', '-', '−', 'ー', '—', '―', '－', '？', 'なし'}


def short_name(s):
    s = unicodedata.normalize('NFKC', str(s))
    s = (s.replace('変電所', '').replace('開閉所', '').replace("'", '')
          .replace('⾧', '長').replace('髙', '高').replace('﨑', '崎')
          .replace('ケ', 'ヶ').replace('　', '').replace(' ', '').strip())
    return s


def to_num(s):
    s = str(s).replace(',', '').replace("'", '').strip()
    if s in MISSING:
        return None
    try:
        return float(s)
    except ValueError:
        return None


FLAG_ONLY = {'対象', '有', '有り', '無', '無し', '○', '△', '×', '要', '否'}

def clean_ref(s):
    """上位系参照文字列の整形（全角読点等を正規化・余分な空白除去）。
    設備コードではなくフラグ値（対象/有り等）のみの場合は None を返す。"""
    s = unicodedata.normalize('NFKC', str(s)).strip()
    s = re.sub(r'\s+', ' ', s)
    s = s.replace('、', ',').replace('，', ',').replace(' ,', ',').replace(', ', ',')
    s = re.sub(r',+', ', ', s).strip(' ,')
    if s in FLAG_ONLY:
        return None
    return s


# ─── CSV系（6社）───────────────────────────────────────────────────────────

def detect_encoding(path):
    return 'utf-8-sig' if open(path, 'rb').read(3) == b'\xef\xbb\xbf' else 'cp932'


def load_company_csv(paths):
    """CSV群から 短縮名 → {upper, v2, avail} を構築。
    容量更新と同じ優先規則（二次電圧<30kVを優先、次に空容量最大）で行を選ぶ。"""
    lookup = {}
    for path in paths:
        with open(path, encoding=detect_encoding(path), errors='replace') as fh:
            rows = list(csv.reader(fh))
        hdr_i = next((i for i, r in enumerate(rows) if any('変電所名' in c for c in r)), None)
        if hdr_i is None:
            continue
        hdr = rows[hdr_i]
        col = {c: i for i, c in enumerate(hdr)}
        name_i = next((i for c, i in col.items() if '変電所名' in c), None)
        v2_i = next((i for c, i in col.items() if '二次' in c or '(二' in c), None)
        avail_i = next((i for c, i in col.items() if '空容量' in c and '当該' in c), None)
        upper_i = next((i for c, i in col.items()
                        if '上位系' in c and '空容量' not in c), None)
        if name_i is None or upper_i is None:
            continue
        for r in rows[hdr_i + 1:]:
            if len(r) <= max(name_i, upper_i) or not r[name_i].strip():
                continue
            name = short_name(r[name_i])
            if not name:
                continue
            upper_raw = r[upper_i].strip()
            upper = clean_ref(upper_raw) if upper_raw not in MISSING else None
            row = {
                'upper': upper,
                'v2': to_num(r[v2_i]) if v2_i is not None and v2_i < len(r) else None,
                'avail': to_num(r[avail_i]) if avail_i is not None and avail_i < len(r) else None,
            }
            cur = lookup.get(name)

            def score(x):
                return ((1 if x['v2'] is not None and x['v2'] < 30 else 0),
                        x['avail'] if x['avail'] is not None else -1)
            if cur is None or score(row) > score(cur):
                lookup[name] = row
    return {k: v['upper'] for k, v in lookup.items() if v['upper']}


# ─── 東電PG（PDF）────────────────────────────────────────────────────────────

TEPCO_ROW = re.compile(r'^変\S*?\s*(配電用変電所|[\d.]+kV)\s*(\d+(?:-\d+)?)(?:\s*(\D.*))?$')
REF_PAT = re.compile(r'\d+\s*kV|基幹|ﾌｪﾝｽ|フェンス')


def load_tepco_pdf():
    """PDF行末尾の上位系等リストを抽出。配電用変電所行を優先。"""
    import fitz
    lookup = {}
    for pdf in sorted(PDF_DIR.glob('tepco_*.pdf')):
        doc = fitz.open(str(pdf))
        for page in doc:
            text = page.get_text()
            if '予想潮流等一覧表（変電所）' not in text:
                continue
            tokens = [t.strip() for t in text.split('\n') if t.strip()]
            i = 0
            while i < len(tokens):
                m = TEPCO_ROW.match(tokens[i])
                if not m:
                    i += 1
                    continue
                tier, inline_name = m.group(1), m.group(3)
                j = i + 1
                if inline_name:
                    name = inline_name
                else:
                    if j < len(tokens) and TEPCO_ROW.match(tokens[j]):
                        i = j
                        continue
                    name = tokens[j] if j < len(tokens) else ''
                    j += 1
                fields = []
                while j < len(tokens) and not TEPCO_ROW.match(tokens[j]):
                    fields.append(tokens[j])
                    j += 1
                    if len(fields) > 20:
                        break
                name = short_name(name)
                refs = [t for t in fields if REF_PAT.search(t)]
                # 「対象」等が先頭に連結しているケースを除去
                refs = [re.sub(r'^(対象|有り|無し)\s*', '', t) for t in refs]
                upper = clean_ref(' '.join(refs)) if refs else None
                if name and upper:
                    cur = lookup.get(name)
                    # 配電用変電所行を優先
                    if cur is None or (tier == '配電用変電所' and cur[0] != '配電用変電所'):
                        lookup[name] = (tier, upper)
                i = j if j > i else i + 1
        doc.close()
    return {k: v[1] for k, v in lookup.items()}


# ─── メイン ──────────────────────────────────────────────────────────────────

def main():
    print("🔌 上位系統コード付与")
    sources = {
        '東京電力パワーグリッド': load_tepco_pdf(),
        '東北電力ネットワーク': load_company_csv(glob.glob(str(CSV_BASE / 'tohoku' / '*.csv'))),
        '北海道電力ネットワーク': load_company_csv(glob.glob(str(CSV_BASE / 'hokkaido' / '**' / '*Tr*.csv'), recursive=True)),
        '九州電力送配電': load_company_csv(glob.glob(str(CSV_BASE / 'kyushu' / '**' / '*変圧器*.csv'), recursive=True)),
        '関西電力送配電': load_company_csv(glob.glob(str(CSV_BASE / 'kansai' / '*trans*.csv'))),
        '中国電力ネットワーク': load_company_csv(glob.glob(str(CSV_BASE / 'chugoku' / '**' / '*_tr_*.csv'), recursive=True)),
        '中部電力パワーグリッド': load_company_csv(glob.glob(str(CSV_BASE / 'chubu' / '**' / '*変電所*.csv'), recursive=True)),
    }
    for c, lk in sources.items():
        print(f"  {c}: 上位系あり {len(lk)}件")

    db = json.loads(SUBSTATIONS.read_text())
    stats = Counter()
    for f in db['features']:
        p = f['properties']
        lk = sources.get(p.get('company'))
        if not lk:
            stats['対象外会社'] += 1
            continue
        upper = lk.get(short_name(p['name']))
        if upper:
            p['upper_grid'] = upper[:300]  # 念のため上限
            stats['付与'] += 1
        else:
            stats['未マッチ'] += 1

    meta = db.setdefault('metadata', {})
    meta['upper_grid_added'] = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'note': '各社予想潮流等一覧表の上位系設備コードをそのまま保持（設備No表記）',
    }
    SUBSTATIONS.write_text(json.dumps(db, ensure_ascii=False, indent=1))
    print(f"\n結果: {dict(stats)}")
    total = stats['付与'] + stats['未マッチ']
    if total:
        print(f"付与率: {stats['付与']}/{total} ({stats['付与']/total*100:.1f}%)")


if __name__ == '__main__':
    main()
