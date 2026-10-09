#!/usr/bin/env python3
"""
substations.json 東京電力PGエントリ更新（CSV版）
====================================================
東電PGが2026年9月開示から提供する「予想潮流等一覧表」CSV
（csv_yosochoryu_{県}.zip 内の *_hendensyo.csv ＝変電所）を直接読み、
空容量(当該設備)を取得して東電エントリを更新する。
※従来のPDFパース(parse_tepco_flow.py)に代わるCSV直読み方式。

CSV構造（UTF-8 BOM付・多段ヘッダ）:
  col0=変電所No「変{県} {tier} {N}」, col1=変電所名, col2=電圧,
  col3=台数, col4=設備容量, col5=運用容量値, col6=制約要因,
  col10=予想潮流, col11=空容量(当該設備)MW, col12=空容量(上位系等考慮)

ランク変換閾値（2026-06-10 ひろ社長承認）:
  S:20MW以上 / A:10〜19 / B:5〜9 / C:1〜4 / D:0以下

使い方:
  python3 scripts/update_tepco_csv.py <csv_dir>
"""

import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

SUBSTATIONS = Path(__file__).resolve().parent.parent / "substations.json"
COMPANY = "東京電力パワーグリッド"

# col0 例: 「変東京都（23区） 配電用変電所 1」「変静岡県（富士川以東） 配電用変電所」
# 県名の後に地区注記（…）が入ることがあるため括弧を許容する
ANCHOR = re.compile(r'^変(\S+?[都道府県])(?:（[^）]*）)?\s*(配電用変電所|[\d.]+kV)')
# 配電用変電所を最優先、次に 22kV、その後は電圧が低い順（配電用ほど連系点に近い）
def tier_rank(tier):
    if tier == '配電用変電所':
        return 0
    m = re.match(r'([\d.]+)kV', tier)
    return float(m.group(1)) if m else 999

def rank_from_mw(mw):
    if mw is None: return None
    if mw >= 20: return 'S'
    if mw >= 10: return 'A'
    if mw >= 5:  return 'B'
    if mw >= 1:  return 'C'
    return 'D'

def short_name(s):
    s = unicodedata.normalize('NFKC', str(s))
    s = (s.replace('変電所', '').replace('開閉所', '').replace("'", '')
          .replace('⾧', '長').replace('髙', '高').replace('﨑', '崎')
          .replace('ケ', 'ヶ').replace('　', '').replace(' ', '').strip())
    return s

def to_num(s):
    s = str(s).replace(',', '').strip()
    if s in ('', '-', '−', 'ー', '—', '―', '－'):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def load_csvs(csv_dir: Path):
    """全CSVから (県, 短縮名) → best row。配電用を優先、空容量数値を優先。"""
    lookup = {}
    data_date = None
    for path in sorted(csv_dir.glob("*.csv")):
        enc = 'utf-8-sig' if open(path, 'rb').read(3) == b'\xef\xbb\xbf' else 'cp932'
        rows = list(csv.reader(open(path, encoding=enc, errors='replace')))
        if rows and rows[0] and ('更新' in rows[0][0] or '時点' in rows[0][0]):
            m = re.search(r'20\d\d年\s*\d+月\s*\d+日', rows[0][0])
            if m and not data_date:
                data_date = m.group(0).replace(' ', '') + '時点'
        for r in rows:
            if len(r) < 12:
                continue
            am = ANCHOR.match(r[0])
            if not am:
                continue
            pref, tier = am.group(1), am.group(2)
            name = short_name(r[1])
            if not name:
                continue
            avail = to_num(r[11])
            cand = {
                'pref': pref, 'name': name, 'tier': tier,
                'voltage': r[2].strip(),
                'units': to_num(r[3]),
                'capacity_mw': to_num(r[4]),
                'op_capacity_mw': to_num(r[5]),
                'available_capacity_mw': avail,
            }
            key = (pref, name)
            cur = lookup.get(key)
            def score(x):
                # ①配電用など連系点に近い設備を優先 ②空容量が数値のものを優先
                return (-tier_rank(x['tier']),
                        1 if x['available_capacity_mw'] is not None else 0)
            if cur is None or score(cand) > score(cur):
                lookup[key] = cand
    return lookup, data_date

def main():
    csv_dir = Path(sys.argv[1])
    print("⚡ 東京電力PG 予想潮流等一覧表CSV読み込み")
    lookup, data_date = load_csvs(csv_dir)
    print(f"  (県,変電所)ユニーク数: {len(lookup)} / データ時点: {data_date}")

    db = json.loads(SUBSTATIONS.read_text())
    feats = [f for f in db["features"] if f["properties"].get("company") == COMPANY]
    print(f"対象: {len(feats)}件（{COMPANY}）")

    old_dist = Counter(f["properties"].get("estimated_cost_rank") for f in feats)
    updated, rank_changes, unmatched, no_data = 0, [], [], 0
    # 名前のみフォールバック（県をまたいで一意の場合）
    by_name = {}
    for (pref, name), row in lookup.items():
        by_name.setdefault(name, []).append(row)

    for f in feats:
        p = f["properties"]
        key = (p.get("prefecture"), short_name(p["name"]))
        row = lookup.get(key)
        if row is None:
            cands = by_name.get(short_name(p["name"]), [])
            row = cands[0] if len(cands) == 1 else None
        if row is None:
            unmatched.append(p["name"])
            continue
        new_mw = row["available_capacity_mw"]
        if new_mw is None:
            no_data += 1
            continue  # 一次変電所等（空容量"-"）は旧値維持
        new_mw = int(new_mw) if float(new_mw).is_integer() else new_mw
        old_mw, old_rank = p.get("available_capacity_mw"), p.get("estimated_cost_rank")
        new_rank = rank_from_mw(new_mw)
        p["available_capacity_mw"] = new_mw
        p["estimated_cost_rank"] = new_rank
        p["can_connect_2mw"] = new_mw >= 2
        detail = f"{row['tier']}"
        if row.get('units'): detail += f" {int(row['units'])}台"
        if row.get('capacity_mw'): detail += f" 設備{int(row['capacity_mw'])}MW 運用{int(row['op_capacity_mw'])}MW"
        p["notes"] = (f"【公式データ TEPCO {data_date or '2026年9月2日時点'}】予想潮流等一覧表（変電所）CSVより。"
                      f"{detail} 空容量(当該設備){new_mw}MW")
        updated += 1
        if old_rank != new_rank:
            rank_changes.append((p["name"], p.get("prefecture"), old_mw, old_rank, new_mw, new_rank))

    meta = db.setdefault("metadata", {})
    meta.setdefault("company_data_updates", {})[COMPANY] = {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "data_source_date": data_date,
        "source": "予想潮流等一覧表（変電所）CSV 全14都県",
        "rank_thresholds": "S>=20MW, A>=10, B>=5, C>=1, D<=0 (2026-06-10ひろ社長承認)",
    }
    meta["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    SUBSTATIONS.write_text(json.dumps(db, ensure_ascii=False, indent=1))

    new_dist = Counter(f["properties"].get("estimated_cost_rank") for f in feats)
    print(f"更新: {updated}件 / 非公開(旧値維持): {no_data}件 / 未マッチ: {len(unmatched)}件 / ランク変更: {len(rank_changes)}件")
    print("旧ランク分布:", dict(old_dist))
    print("新ランク分布:", dict(new_dist))
    print("\n--- ランク変更サンプル ---")
    for name, pref, om, orank, nm, nrank in rank_changes[:15]:
        print(f"  {pref} {name}: {om}MW/{orank} → {nm}MW/{nrank}")
    print("\n--- 未マッチサンプル ---")
    print(" ", unmatched[:15])
    log_path = Path(__file__).parent / f"update_log_tepco_csv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(json.dumps({
        "updated_at": datetime.now().isoformat(), "company": COMPANY,
        "updated": updated, "no_data": no_data, "unmatched": unmatched,
        "old_dist": dict(old_dist), "new_dist": dict(new_dist),
        "rank_changes": [{"name": n, "pref": pr, "old_mw": om, "old_rank": orank, "new_mw": nm, "new_rank": nr}
                         for n, pr, om, orank, nm, nr in rank_changes],
    }, ensure_ascii=False, indent=2))
    print(f"\n変更ログ: {log_path}")

if __name__ == "__main__":
    main()
