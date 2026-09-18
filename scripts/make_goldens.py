"""GT-2 のゴールデン JSON を Python（v1 リファレンス実装）で生成する。

    python3 scripts/make_goldens.py            # js/test/golden/*.json を書き出す
    python3 scripts/make_goldens.py --check    # 既存ファイルとの差分だけを見る

対象（要件書 v0.3 §I-6 GT-2）：sample、試験図 A・B・C、極圏 6 図。
極圏 6 図の出生データは要件書に定義がないため、本スクリプトで定義し
CHARTS に残す（白夜・極夜・地平線際・南半球の極圏・惑星時が null になる場合を含む）。
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import natal_classical as nc  # noqa: E402

OUT_DIR = os.path.join(ROOT, "js", "test", "golden")

# name: (year, month, day, hour, minute, lat, lon, tz_offset, 説明)
CHARTS = {
    "sample_tokyo_1985": (1985, 7, 21, 14, 30, 35.6895, 139.6917, 9.0,
                          "sample_chart_v1.json と同じ出生データ（東京）"),
    "chart_A_fukuoka_1996": (1996, 1, 1, 23, 7, 33.6, 130.4167, 9.0,
                             "試験図 A（福岡）。決定 C で木星が under_beams → free"),
    "chart_B_sydney_1968": (1968, 10, 12, 13, 0, -33.8667, 151.2167, 10.0,
                            "試験図 B（シドニー、南半球・UTC+10）"),
    "chart_C_stockholm_1915": (1915, 8, 29, 3, 30, 59.3333, 18.05, 1.0,
                               "試験図 C（ストックホルム、UTC+1・日の出前）"),
    # --- 極圏 6 図（本スクリプトで定義。要件書に具体値の指定がない） ---
    "polar_1_longyearbyen_midsummer_midnight": (
        2020, 6, 21, 0, 0, 78.22, 15.63, 1.0,
        "白夜の真夜中。地平線基準は夜図だが太陽高度は正 → sect.borderline"),
    "polar_2_longyearbyen_midsummer_noon": (
        2020, 6, 21, 12, 0, 78.22, 15.63, 1.0,
        "白夜の正午。planetary_day_hour は null（日出没なし）"),
    "polar_3_longyearbyen_midwinter_noon": (
        2020, 12, 21, 12, 0, 78.22, 15.63, 1.0,
        "極夜の正午。planetary_day_hour は null"),
    "polar_4_tromso_spring_morning": (
        1985, 3, 15, 9, 0, 69.6496, 18.9560, 1.0,
        "北極圏内だが日出没がある（惑星時が null にならない高緯度の例）"),
    "polar_5_utqiagvik_polar_night": (
        1975, 11, 20, 12, 0, 71.2906, -156.7887, -9.0,
        "極夜のウトキアグヴィク（西経・UTC−9）"),
    "polar_6_mcmurdo_polar_night": (
        2000, 6, 21, 12, 0, -77.8463, 166.6683, 13.0,
        "南半球の極圏（マクマード、UTC+13）。冬至の極夜"),
}


def build(name):
    y, mo, d, h, mi, lat, lon, tz, _note = CHARTS[name]
    chart = nc.calculate_classical_chart(y, mo, d, h, mi, lat, lon, tz_offset=tz)
    return json.loads(json.dumps(nc.to_json(chart), ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="書き出さずに既存ファイルとの差分だけを報告する")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = {}
    changed = []
    for name, spec in CHARTS.items():
        data = build(name)
        path = os.path.join(OUT_DIR, name + ".json")
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        old = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old = f.read()
        if old != text:
            changed.append(name)
            if not args.check:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
        manifest[name] = {
            "year": spec[0], "month": spec[1], "day": spec[2],
            "hour": spec[3], "minute": spec[4],
            "latitude": spec[5], "longitude": spec[6], "tz_offset": spec[7],
            "note": spec[8],
        }
    man_path = os.path.join(OUT_DIR, "manifest.json")
    man_text = json.dumps(
        {"generator": "natal_classical.py (v1 reference implementation)",
         "schema_version": nc.SCHEMA_VERSION,
         "charts": manifest}, ensure_ascii=False, indent=2) + "\n"
    if not args.check:
        with open(man_path, "w", encoding="utf-8") as f:
            f.write(man_text)
    print(("差分あり: " if changed else "差分なし: ")
          + (", ".join(changed) if changed else f"{len(CHARTS)} 図すべて一致"))
    print("出力先:", OUT_DIR)


if __name__ == "__main__":
    main()
