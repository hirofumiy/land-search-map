#!/usr/bin/env python3
"""
substations.json 東京電力PGエントリ更新スクリプト
====================================================
parse_tepco_flow.py の出力（予想潮流等一覧表 2026/4/30作成）を
substations.json の東電エントリに反映する。

ランク変換閾値（2026-06-10 ひろ社長承認）:
  S: 20MW以上 / A: 10〜19 / B: 5〜9 / C: 1〜4 / D: 0以下
  ※UI凡例「S（20MW以上）が最も接続しやすい」と整合

使い方:
  python3 scripts/update_tepco.py <tepco_flow_xxx.json>
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

SUBSTATIONS = Path(__file__).resolve().parent.parent / "substations.json"
COMPANY = "東京電力パワーグリッド"
DATA_DATE = "2026/4/30"

def rank_from_mw(mw):
    if mw is None: return None
    if mw >= 20: return 'S'
    if mw >= 10: return 'A'
    if mw >= 5:  return 'B'
    if mw >= 1:  return 'C'
    return 'D'

import unicodedata

def short_name(s):
    s = unicodedata.normalize('NFKC', s)  # 半角カナ→全角等
    s = (s.replace('変電所', '').replace('開閉所', '')
          .replace('⾧', '長').replace('髙', '高').replace('﨑', '崎')
          .replace('ケ', 'ヶ').replace('　', '').replace(' ', '').strip())
    return s

def main():
    flow_path = Path(sys.argv[1])
    flow = json.loads(flow_path.read_text())

    # PDF側ルックアップ: (pref, name) → row。配電用変電所を最優先
    lookup = {}
    PREF_ALIAS = {"東京都23区": "東京都", "東京都多摩": "東京都"}
    for row in flow["substations"]:
        if row["available_capacity_mw"] is None:
            continue
        pref = PREF_ALIAS.get(row["prefecture"], row["prefecture"])
        key = (pref, short_name(row["name"]))
        cur = lookup.get(key)
        if cur is None or (row["tier"] == "配電用変電所" and cur["tier"] != "配電用変電所"):
            lookup[key] = row
    # 名前のみのフォールバック（県をまたいで一意の場合のみ）
    by_name = {}
    for (pref, name), row in lookup.items():
        by_name.setdefault(name, []).append(row)

    db = json.loads(SUBSTATIONS.read_text())
    feats = [f for f in db["features"] if f["properties"].get("company") == COMPANY]
    print(f"対象: {len(feats)}件（{COMPANY}）")

    updated, rank_changes, unmatched = 0, [], []
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

        old_mw, old_rank = p.get("available_capacity_mw"), p.get("estimated_cost_rank")
        new_mw = row["available_capacity_mw"]
        new_mw = int(new_mw) if float(new_mw).is_integer() else new_mw
        new_rank = rank_from_mw(new_mw)

        p["available_capacity_mw"] = new_mw
        p["estimated_cost_rank"] = new_rank
        p["can_connect_2mw"] = new_mw >= 2
        detail = f"{row['tier']}"
        if row.get("units"): detail += f" {row['units']}台"
        if row.get("capacity_mw"): detail += f" 設備{int(row['capacity_mw'])}MW 運用{int(row['op_capacity_mw'])}MW"
        p["notes"] = (f"【公式データ TEPCO {DATA_DATE}時点】予想潮流等一覧表（変電所）より。"
                      f"{detail} 空容量(当該設備){new_mw}MW")
        updated += 1
        if old_rank != new_rank:
            rank_changes.append((p["name"], p.get("prefecture"), old_mw, old_rank, new_mw, new_rank))

    # metadata更新
    meta = db.setdefault("metadata", {})
    meta.setdefault("company_data_updates", {})[COMPANY] = {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "data_source_date": DATA_DATE,
        "source": "予想潮流等一覧表（変電所）2026年6月2日公開再開版",
        "rank_thresholds": "S>=20MW, A>=10, B>=5, C>=1, D<=0 (2026-06-10ひろ社長承認)",
    }
    meta["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    SUBSTATIONS.write_text(json.dumps(db, ensure_ascii=False, indent=1))

    print(f"更新: {updated}件 / 未マッチ: {len(unmatched)}件 / ランク変更: {len(rank_changes)}件")
    new_dist = Counter(f["properties"].get("estimated_cost_rank") for f in feats)
    print("更新後ランク分布:", dict(new_dist))
    print("\n--- ランク変更サンプル（最大15件） ---")
    for name, pref, om, orank, nm, nrank in rank_changes[:15]:
        print(f"  {pref} {name}: {om}MW/{orank} → {nm}MW/{nrank}")
    print("\n--- 未マッチサンプル ---")
    print(" ", unmatched[:20])
    # 変更ログ保存
    log = {
        "updated_at": datetime.now().isoformat(),
        "company": COMPANY,
        "updated": updated, "unmatched": unmatched,
        "rank_changes": [
            {"name": n, "pref": pr, "old_mw": om, "old_rank": orank, "new_mw": nm, "new_rank": nr}
            for n, pr, om, orank, nm, nr in rank_changes
        ],
    }
    log_path = Path(__file__).parent / f"update_log_tepco_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2))
    print(f"\n変更ログ: {log_path}")

if __name__ == "__main__":
    main()
