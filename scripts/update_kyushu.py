#!/usr/bin/env python3
"""
substations.json 九州電力送配電エントリ更新スクリプト
====================================================
九州電力送配電公式CSV（予想潮流等・変圧器 地区別31ファイル）から
空容量(当該設備)を取得し、九州エントリ439件を更新する。


ランク変換閾値（2026-06-10 ひろ社長承認）:
  S: 20MW以上 / A: 10〜19 / B: 5〜9 / C: 1〜4 / D: 0以下

使い方:
  python3 scripts/update_kyushu.py <csv_dir>
"""

import csv
import json
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

SUBSTATIONS = Path(__file__).resolve().parent.parent / "substations.json"
COMPANY = "九州電力送配電"

def rank_from_mw(mw):
    if mw is None: return None
    if mw >= 20: return 'S'
    if mw >= 10: return 'A'
    if mw >= 5:  return 'B'
    if mw >= 1:  return 'C'
    return 'D'

def short_name(s):
    s = unicodedata.normalize('NFKC', s)
    s = (s.replace('変電所', '').replace('開閉所', '').replace("'", '')
          .replace('⾧', '長').replace('髙', '高').replace('﨑', '崎')
          .replace('ケ', 'ヶ').replace('　', '').replace(' ', '').strip())
    return s

def to_num(s):
    s = str(s).replace(',', '').replace("'", '').strip()
    if s in ('', '-', '−', 'ー', '—', '―'):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def load_csvs(csv_dir: Path):
    """全CSVから (短縮名) → row の辞書を構築。重複時は空容量が大きい方を採用"""
    lookup = {}
    data_date = None
    for path in sorted(csv_dir.glob("*.csv")):
        with open(path, encoding='cp932', errors='replace') as fh:
            reader = csv.reader(fh)
            rows = list(reader)
        if rows and '作成' in rows[0][0]:
            data_date = data_date or rows[0][0].strip()
        header_idx = next((i for i, r in enumerate(rows) if r and '変電所名' in ','.join(r)), None)
        if header_idx is None:
            print(f"  ⚠️ ヘッダなし: {path.name}")
            continue
        header = rows[header_idx]
        col = {name: i for i, name in enumerate(header)}
        name_i = col.get('変電所名')
        v1_i  = next((i for n, i in col.items() if '一次' in n), None)
        v2_i  = next((i for n, i in col.items() if '二次' in n or '(二' in n), None)
        units_i = col.get('台数')
        cap_i  = next((i for n, i in col.items() if '設備容量' in n), None)
        op_i   = next((i for n, i in col.items() if '運用容量値' in n), None)
        avail_i = next((i for n, i in col.items() if '空容量' in n and '当該' in n), None)
        count = 0
        for r in rows[header_idx + 1:]:
            if len(r) <= max(name_i, avail_i) or not r[name_i].strip():
                continue
            name = short_name(r[name_i])
            if not name:
                continue
            avail = to_num(r[avail_i])
            row = {
                'name': name,
                'v1': to_num(r[v1_i]) if v1_i is not None else None,
                'v2': to_num(r[v2_i]) if v2_i is not None else None,
                'units': to_num(r[units_i]) if units_i is not None else None,
                'capacity_mw': to_num(r[cap_i]) if cap_i is not None else None,
                'op_capacity_mw': to_num(r[op_i]) if op_i is not None else None,
                'available_capacity_mw': avail,
                'src': path.name,
            }
            cur = lookup.get(name)
            # 配電用(二次6.6kV)を優先、次に空容量が大きい方
            def pref_score(x):
                return ((1 if x['v2'] is not None and x['v2'] < 30 else 0),
                        x['available_capacity_mw'] if x['available_capacity_mw'] is not None else -1)
            if cur is None or pref_score(row) > pref_score(cur):
                lookup[name] = row
            count += 1
        print(f"  ✅ {path.name}: {count}行")
    return lookup, data_date

def main():
    csv_dir = Path(sys.argv[1])
    print("⚡ 九州電力送配電 変圧器CSV読み込み")
    lookup, data_date = load_csvs(csv_dir)
    print(f"  変電所ユニーク数: {len(lookup)} / データ作成日: {data_date}")

    db = json.loads(SUBSTATIONS.read_text())
    feats = [f for f in db["features"] if f["properties"].get("company") == COMPANY]
    print(f"\n対象: {len(feats)}件（{COMPANY}）")

    old_dist = Counter(f["properties"].get("estimated_cost_rank") for f in feats)
    updated, rank_changes, unmatched, no_data = 0, [], [], 0
    for f in feats:
        p = f["properties"]
        row = lookup.get(short_name(p["name"]))
        if row is None:
            unmatched.append(p["name"])
            continue
        new_mw = row["available_capacity_mw"]
        if new_mw is None:
            no_data += 1
            continue  # 非公開設備は旧値維持
        new_mw = int(new_mw) if float(new_mw).is_integer() else new_mw
        old_mw, old_rank = p.get("available_capacity_mw"), p.get("estimated_cost_rank")
        new_rank = rank_from_mw(new_mw)
        p["available_capacity_mw"] = new_mw
        p["estimated_cost_rank"] = new_rank
        p["can_connect_2mw"] = new_mw >= 2
        detail = ''
        if row.get('v1') and row.get('v2'):
            detail = f"{int(row['v1'])}/{row['v2']:.3g}kV"
        if row.get('units'): detail += f" {int(row['units'])}台"
        if row.get('capacity_mw'): detail += f" 設備{int(row['capacity_mw'])}MW 運用{int(row['op_capacity_mw'])}MW"
        p["notes"] = (f"【公式データ 九州電力送配電 {data_date or '2026年3〜5月'}】予想潮流等情報CSVより。"
                      f"{detail} 空容量(当該設備){new_mw}MW")
        updated += 1
        if old_rank != new_rank:
            rank_changes.append((p["name"], old_mw, old_rank, new_mw, new_rank))

    meta = db.setdefault("metadata", {})
    meta.setdefault("company_data_updates", {})[COMPANY] = {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "data_source_date": data_date,
        "source": "予想潮流等 変圧器CSV（30地区）",
        "rank_thresholds": "S>=20MW, A>=10, B>=5, C>=1, D<=0 (2026-06-10ひろ社長承認)",
    }
    meta["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    SUBSTATIONS.write_text(json.dumps(db, ensure_ascii=False, indent=1))

    new_dist = Counter(f["properties"].get("estimated_cost_rank") for f in feats)
    print(f"更新: {updated}件 / 非公開(旧値維持): {no_data}件 / 未マッチ: {len(unmatched)}件 / ランク変更: {len(rank_changes)}件")
    print("旧ランク分布:", dict(old_dist))
    print("新ランク分布:", dict(new_dist))
    print("\n--- ランク変更サンプル ---")
    for name, om, orank, nm, nrank in rank_changes[:15]:
        print(f"  {name}: {om}MW/{orank} → {nm}MW/{nrank}")
    print("\n--- 未マッチサンプル ---")
    print(" ", unmatched[:20])
    log_path = Path(__file__).parent / f"update_log_kyushu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(json.dumps({
        "updated_at": datetime.now().isoformat(), "company": COMPANY,
        "updated": updated, "no_data": no_data, "unmatched": unmatched,
        "old_dist": dict(old_dist), "new_dist": dict(new_dist),
        "rank_changes": [{"name": n, "old_mw": om, "old_rank": orank, "new_mw": nm, "new_rank": nr}
                         for n, om, orank, nm, nr in rank_changes],
    }, ensure_ascii=False, indent=2))
    print(f"\n変更ログ: {log_path}")

if __name__ == "__main__":
    main()
