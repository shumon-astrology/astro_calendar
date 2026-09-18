"""natal_classical.py の定数を js/data/*.json に機械書き出しする。

    python3 scripts/export_tables.py           # 書き出す
    python3 scripts/export_tables.py --check   # 既存ファイルとの差分を報告（書かない）

JS 側で表を手打ちしないための唯一の経路（要件書 v0.3 第 II 部 II-2、Phase 2 手順 2）。
一致は tests/test_data_export.py が検証する。
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import natal_classical as nc  # noqa: E402
import astro_calendar as ac  # noqa: E402

OUT_DIR = os.path.join(ROOT, "js", "data")


def terms(table):
    """[(上限度数, 主星), ...] → [{"until": 6, "ruler": "Jupiter"}, ...]"""
    return [[{"until": limit, "ruler": ruler} for limit, ruler in row] for row in table]


def build():
    """書き出す JSON を {ファイル名: データ} で返す"""
    dignity = {
        "_source": "natal_classical.py constants, exported by scripts/export_tables.py",
        "planets": list(nc.PLANET_NAMES),
        "sign_abbrev": list(ac.SIGN_ABBREV),
        "sign_full": list(ac.SIGN_FULL),
        "elements": list(nc.ELEMENTS),
        "domicile_by_sign": list(nc.DOMICILE_BY_SIGN),
        "detriment_by_sign": list(nc.DETRIMENT_BY_SIGN),
        "exaltations": {p: {"sign": si, "degree": dg} for p, (si, dg) in nc.EXALTATIONS.items()},
        "exalt_by_sign": {str(si): {"planet": p, "degree": dg}
                          for si, (p, dg) in nc.EXALT_BY_SIGN.items()},
        "fall_by_sign": {str(si): {"planet": p, "degree": dg}
                         for si, (p, dg) in nc.FALL_BY_SIGN.items()},
        "node_exaltation": {"sign": nc.NODE_EXALTATION[0], "degree": nc.NODE_EXALTATION[1]},
        "triplicity": {
            "default": nc.DEFAULT_TRIPLICITY,
            "tables": {
                name: {el: {"day": t[0], "night": t[1], "participating": t[2]}
                       for el, t in table.items()}
                for name, table in nc.TRIPLICITY_TABLES.items()
            },
        },
        "terms": {
            "default": nc.DEFAULT_TERMS,
            "audit": nc.TERMS_AUDIT,
            "tables": {name: terms(table) for name, table in nc.TERMS_TABLES.items()},
        },
        "faces": [list(row) for row in nc.FACES],
        "chaldean_order": list(nc.CHALDEAN_ORDER),
        "dignity_scores": dict(nc.DIGNITY_SCORE),
        "angular_houses": list(nc.ANGULAR_HOUSES),
        "succedent_houses": list(nc.SUCCEDENT_HOUSES),
    }

    orbs = {
        "_source": "natal_classical.py constants, exported by scripts/export_tables.py",
        "planet_orb": dict(nc.PLANET_ORB),
        "moiety": dict(nc.MOIETY),
        "point_moiety": nc.POINT_MOIETY,
        "partile_orb": nc.PARTILE_ORB,
        "cazimi_orb": nc.CAZIMI_ORB,
        "combust_orb": nc.COMBUST_ORB,
        "under_beams_orb": nc.UNDER_BEAMS_ORB,
        "mean_motion": dict(nc.MEAN_MOTION),
        "aspects": [{"angle": a, "name": full, "abbrev": ab, "name_ja": ja}
                    for a, full, ab, ja in nc.CLASSICAL_ASPECTS],
        "cusp_threshold": 5.0,
    }

    accidental = {
        "_source": "natal_classical.py constants, exported by scripts/export_tables.py",
        "house_score": {str(k): v for k, v in nc.HOUSE_SCORE.items()},
        "benefics": list(nc.BENEFICS),
        "malefics": list(nc.MALEFICS),
        "luminaries": list(nc.LUMINARIES),
        "diurnal_planets": list(nc.DIURNAL_PLANETS),
        "nocturnal_planets": list(nc.NOCTURNAL_PLANETS),
        "weekday_rulers": list(nc.WEEKDAY_RULERS),
        "hour_order": list(nc.HOUR_ORDER),
        "fixed_stars_j2000": dict(nc.FIXED_STARS_J2000),
        "precession_per_year": nc.PRECESSION_PER_YEAR,
        "planet_ja": {k: v for k, v in nc.PLANET_JA.items()},
        "dignity_ja": dict(nc.DIGNITY_JA),
    }

    sources = {
        "_source": "natal_classical.py TABLE_SOURCES, exported by scripts/export_tables.py",
        "table_sources": nc.TABLE_SOURCES,
        "schema_version_v1": nc.SCHEMA_VERSION,
        "sect_method": nc.SECT_METHOD,
        "peregrine_score_note": nc.PEREGRINE_SCORE_NOTE,
    }

    return {
        "tables_dignity.json": dignity,
        "orbs.json": orbs,
        "accidental_points.json": accidental,
        "table_sources.json": sources,
    }


def dumps(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    changed = []
    for name, data in build().items():
        path = os.path.join(OUT_DIR, name)
        text = dumps(data)
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if old != text:
            changed.append(name)
            if not args.check:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
    print(("差分あり: " + ", ".join(changed)) if changed else "差分なし（4 ファイル一致）")


if __name__ == "__main__":
    main()
