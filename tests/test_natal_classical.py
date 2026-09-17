"""
natal_classical.py のテスト（METHOD_本質的品位表_v1.md v1.1 準拠）

実行: python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import natal_classical as nc  # noqa: E402

SIGN = {n: i for i, n in enumerate(
    ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"])}


def lon(sign, deg):
    return SIGN[sign] * 30.0 + deg


# METHOD §4.1 エジプト式ターム（転記）
METHOD_TERMS_EGYPTIAN = {
    "Ari": [("Jupiter", 6), ("Venus", 12), ("Mercury", 20), ("Mars", 25), ("Saturn", 30)],
    "Tau": [("Venus", 8), ("Mercury", 14), ("Jupiter", 22), ("Saturn", 27), ("Mars", 30)],
    "Gem": [("Mercury", 6), ("Jupiter", 12), ("Venus", 17), ("Mars", 24), ("Saturn", 30)],
    "Can": [("Mars", 7), ("Venus", 13), ("Mercury", 19), ("Jupiter", 26), ("Saturn", 30)],
    "Leo": [("Jupiter", 6), ("Venus", 11), ("Saturn", 18), ("Mercury", 24), ("Mars", 30)],
    "Vir": [("Mercury", 7), ("Venus", 17), ("Jupiter", 21), ("Mars", 28), ("Saturn", 30)],
    "Lib": [("Saturn", 6), ("Mercury", 14), ("Jupiter", 21), ("Venus", 28), ("Mars", 30)],
    "Sco": [("Mars", 7), ("Venus", 11), ("Mercury", 19), ("Jupiter", 24), ("Saturn", 30)],
    "Sag": [("Jupiter", 12), ("Venus", 17), ("Mercury", 21), ("Saturn", 26), ("Mars", 30)],
    "Cap": [("Mercury", 7), ("Jupiter", 14), ("Venus", 22), ("Saturn", 26), ("Mars", 30)],
    "Aqu": [("Mercury", 7), ("Venus", 13), ("Jupiter", 20), ("Mars", 25), ("Saturn", 30)],
    "Pis": [("Venus", 12), ("Jupiter", 16), ("Mercury", 19), ("Mars", 28), ("Saturn", 30)],
}


class TestTermTables(unittest.TestCase):

    def test_egyptian_matches_method_4_1(self):
        for sign, row in METHOD_TERMS_EGYPTIAN.items():
            expected = [(end, planet) for planet, end in row]
            self.assertEqual(nc.TERMS_EGYPTIAN[SIGN[sign]], expected, sign)

    def test_tables_are_well_formed(self):
        for table in (nc.TERMS_EGYPTIAN, nc.TERMS_PTOLEMAIC):
            for row in table:
                self.assertEqual(row[-1][0], 30)
                self.assertIn(row[-1][1], ("Mars", "Saturn"))
                ends = [e for e, _ in row]
                self.assertEqual(ends, sorted(ends))
                self.assertEqual(sorted(p for _, p in row),
                                 sorted(["Saturn", "Jupiter", "Mars", "Venus", "Mercury"]))

    def test_boundary_is_end_of_term(self):
        # 牡羊 6° はちょうど金星ターム（0–6 は木星）
        self.assertEqual(nc.term_ruler(lon("Ari", 5.99)), "Jupiter")
        self.assertEqual(nc.term_ruler(lon("Ari", 6.0)), "Venus")
        self.assertEqual(nc.term_ruler(lon("Ari", 29.99)), "Saturn")

    def test_case003_examples(self):
        # 出生図鑑定_Case003_20260901.md のターム差2例
        mercury = lon("Sco", 15 + 41 / 60)
        mars = lon("Cap", 28 + 30 / 60)
        self.assertEqual(nc.term_ruler(mercury), "Mercury")
        self.assertEqual(nc.term_ruler(mercury, nc.TERMS_PTOLEMAIC), "Venus")
        self.assertEqual(nc.term_ruler(mars), "Mars")
        self.assertEqual(nc.term_ruler(mars, nc.TERMS_PTOLEMAIC), "Saturn")

    def test_ptolemaic_is_audit_only(self):
        # ♏15°41′ の水星：プトレマイオス式ならペレグリン（Case003）だが得点はエジプト式
        ed = nc.essential_dignity(lon("Sco", 15 + 41 / 60), "Mercury", is_day=True)
        self.assertIn("term", ed["labels"])
        self.assertEqual(ed["score"], 2)
        self.assertEqual(ed["term_audit"],
                         {"table": "ptolemaic_lilly", "ruler": "Venus",
                          "differs": True, "has_term": False})
        # 牡羊 13° の金星：プトレマイオス式では自ターム、エジプト式では水星ターム
        ed = nc.essential_dignity(lon("Ari", 13), "Venus", is_day=True)
        self.assertNotIn("term", ed["labels"])
        self.assertTrue(ed["term_audit"]["has_term"])


class TestTriplicity(unittest.TestCase):

    def test_participating_ruler_gets_no_points(self):
        # 昼図・風サインの木星（関与星）は +3 を受けない。水瓶 26° は ♄ターム・☽フェイス
        ed = nc.essential_dignity(lon("Aqu", 26), "Jupiter", is_day=True)
        self.assertNotIn("triplicity", ed["labels"])
        self.assertEqual(ed["score"], -5)
        self.assertEqual(ed["triplicity_rulers"],
                         {"day": "Saturn", "night": "Mercury",
                          "participating": "Jupiter", "sect_ruler": "Saturn"})
        # 夜図でも同じ
        ed = nc.essential_dignity(lon("Aqu", 26), "Jupiter", is_day=False)
        self.assertNotIn("triplicity", ed["labels"])
        self.assertEqual(ed["triplicity_rulers"]["sect_ruler"], "Mercury")

    def test_only_sect_ruler_scores(self):
        # 天秤 20° の水星（14–21 は木星ターム、20–30 は木星フェイス）
        day = nc.essential_dignity(lon("Lib", 20), "Mercury", is_day=True)
        night = nc.essential_dignity(lon("Lib", 20), "Mercury", is_day=False)
        self.assertEqual(day["labels"], [])
        self.assertEqual(night["labels"], ["triplicity"])
        self.assertEqual(night["score"], 3)
        # 昼図の土星は昼主星として +3
        sat = nc.essential_dignity(lon("Lib", 20), "Saturn", is_day=True)
        self.assertIn("triplicity", sat["labels"])
        sat_n = nc.essential_dignity(lon("Lib", 20), "Saturn", is_day=False)
        self.assertNotIn("triplicity", sat_n["labels"])

    def test_sun_in_leo_example(self):
        # METHOD §8.1 の例：昼図の太陽＠獅子＝+5+3＝+8
        self.assertEqual(nc.essential_dignity(lon("Leo", 2), "Sun", True)["score"], 8)
        self.assertEqual(nc.essential_dignity(lon("Leo", 2), "Sun", False)["score"], 5)

    def test_almuten_ignores_participating_ruler(self):
        # 水瓶 26°（昼）：木星は関与星のみ → アルムテン得点に含まれない
        res = nc.almuten_of_degree(lon("Aqu", 26), is_day=True)
        self.assertNotIn("Jupiter", res["scores"])
        self.assertEqual(res["scores"]["Saturn"], 5 + 3 + 2)

    def test_reception_still_uses_participating_ruler(self):
        # レセプション判定には関与星も用いる（METHOD §3）
        rec = nc.reception_between("Jupiter", 0, "Mercury", lon("Aqu", 26), True)
        self.assertEqual(rec, ["triplicity"])


class TestPeregrine(unittest.TestCase):

    def test_decision1_peregrine_is_minus5(self):
        ed = nc.essential_dignity(lon("Aqu", 26), "Jupiter", is_day=True)
        self.assertTrue(ed["peregrine"])
        self.assertEqual(ed["debilities"], ["peregrine"])
        self.assertIsNone(ed["peregrine_cancelled_by"])
        self.assertEqual(ed["score"], -5)

    def test_decision2_mutual_reception_by_sign_cancels(self):
        # 木星＠牡羊 25.5°（昼・品位なし）と火星＠魚：サインのミューチュアル・レセプション
        positions = {"Jupiter": lon("Ari", 25.5), "Mars": lon("Pis", 10)}
        mr = nc.mutual_receptions("Jupiter", positions)
        self.assertEqual(mr, [{"with": "Mars", "type": "mutual_reception_sign"}])
        ed = nc.essential_dignity(positions["Jupiter"], "Jupiter", True, receptions=mr)
        self.assertFalse(ed["peregrine"])
        self.assertEqual(ed["peregrine_cancelled_by"], "mutual_reception_sign")
        self.assertEqual(ed["debilities"], [])
        self.assertEqual(ed["score"], 0)
        # レセプションがなければ −5
        ed0 = nc.essential_dignity(positions["Jupiter"], "Jupiter", True)
        self.assertEqual(ed0["score"], -5)

    def test_decision2_mutual_reception_by_exaltation_cancels(self):
        # 水星＠牡牛 25°（♄ターム・♄フェイス）と月＠乙女：高揚どうしの受容
        positions = {"Mercury": lon("Tau", 25), "Moon": lon("Vir", 25)}
        mr = nc.mutual_receptions("Mercury", positions)
        self.assertEqual(mr, [{"with": "Moon", "type": "mutual_reception_exaltation"}])
        ed = nc.essential_dignity(positions["Mercury"], "Mercury", True, receptions=mr)
        self.assertFalse(ed["peregrine"])
        self.assertEqual(ed["peregrine_cancelled_by"], "mutual_reception_exaltation")
        self.assertEqual(ed["score"], 0)

    def test_decision2_mixed_sign_exaltation(self):
        # 太陽＠山羊（火星の高揚）と火星＠獅子（太陽のサイン）
        positions = {"Sun": lon("Cap", 20), "Mars": lon("Leo", 20)}
        self.assertEqual(nc.mutual_receptions("Sun", positions),
                         [{"with": "Mars", "type": "mutual_reception_mixed"}])

    def test_decision2_term_reception_does_not_cancel(self):
        # 木星＠牡羊 25.5°（土星ターム）と土星＠射手 5°（木星ターム）：
        # タームの相互受容は解除条件にならない（射手は木星のサインだが片側のみ）
        positions = {"Jupiter": lon("Ari", 25.5), "Saturn": lon("Sag", 5)}
        mr = nc.mutual_receptions("Jupiter", positions)
        self.assertEqual(mr, [])
        ed = nc.essential_dignity(positions["Jupiter"], "Jupiter", True, receptions=mr)
        self.assertTrue(ed["peregrine"])
        self.assertEqual(ed["score"], -5)

    def test_decision3_detriment_not_double_counted(self):
        # 火星＠天秤 16°（昼）：品位なし＋デトリメント → −5 のみ（−10 ではない）
        ed = nc.essential_dignity(lon("Lib", 16), "Mars", is_day=True)
        self.assertTrue(ed["peregrine"])
        self.assertEqual(ed["debilities"], ["detriment"])
        self.assertEqual(ed["score"], -5)
        self.assertEqual(ed["score_note"], nc.PEREGRINE_SCORE_NOTE)

    def test_decision3_fall_not_double_counted(self):
        # 火星＠蟹 28°（昼）：品位なし＋フォール → −4 のみ
        ed = nc.essential_dignity(lon("Can", 28), "Mars", is_day=True)
        self.assertTrue(ed["peregrine"])
        self.assertEqual(ed["debilities"], ["fall"])
        self.assertEqual(ed["score"], -4)
        # 夜図では夜主星 +3 を得るのでペレグリンではない：−4＋3
        ed_n = nc.essential_dignity(lon("Can", 28), "Mars", is_day=False)
        self.assertFalse(ed_n["peregrine"])
        self.assertIsNone(ed_n["score_note"])
        self.assertEqual(ed_n["score"], -1)

    def test_decision2_and_3_combined(self):
        # 火星＠天秤と金星＠牡羊：解除されてもデトリメント −5 は残る
        positions = {"Mars": lon("Lib", 16), "Venus": lon("Ari", 16)}
        mr = nc.mutual_receptions("Mars", positions)
        ed = nc.essential_dignity(positions["Mars"], "Mars", True, receptions=mr)
        self.assertFalse(ed["peregrine"])
        self.assertEqual(ed["peregrine_cancelled_by"], "mutual_reception_sign")
        self.assertEqual(ed["debilities"], ["detriment"])
        self.assertIsNone(ed["score_note"])
        self.assertEqual(ed["score"], -5)

    def test_debilitated_planet_with_term_is_not_peregrine(self):
        # 火星＠天秤 29°（火星ターム）：デトリメントでもペレグリンではない
        ed = nc.essential_dignity(lon("Lib", 29), "Mars", is_day=True)
        self.assertFalse(ed["peregrine"])
        self.assertEqual(ed["score"], -5 + 2)


class TestAlmutenTie(unittest.TestCase):

    def test_single_winner(self):
        res = nc.resolve_almuten({"Venus": 5, "Mars": 3})
        self.assertEqual(res["almuten"], "Venus")
        self.assertFalse(res["almuten_tie"])
        self.assertIsNone(res["tie_break"])

    def test_tie_broken_by_angularity(self):
        res = nc.resolve_almuten({"Jupiter": 6, "Moon": 6, "Venus": 3},
                                 {"Jupiter": 3, "Moon": 10, "Venus": 1})
        self.assertEqual(res["almuten"], "Moon")
        self.assertFalse(res["almuten_tie"])
        self.assertEqual(res["candidates"], ["Jupiter", "Moon"])
        self.assertEqual(res["tie_break"], "house_angularity")

    def test_succedent_beats_cadent(self):
        res = nc.resolve_almuten({"Saturn": 4, "Mars": 4},
                                 {"Saturn": 12, "Mars": 11})
        self.assertEqual(res["almuten"], "Mars")

    def test_unresolved_tie(self):
        res = nc.resolve_almuten({"Saturn": 4, "Mars": 4, "Sun": 4},
                                 {"Saturn": 1, "Mars": 7, "Sun": 3})
        self.assertIsNone(res["almuten"])
        self.assertTrue(res["almuten_tie"])
        self.assertEqual(res["candidates"], ["Saturn", "Mars"])

    def test_tie_without_house_info(self):
        res = nc.resolve_almuten({"Saturn": 4, "Mars": 4})
        self.assertTrue(res["almuten_tie"])
        self.assertIsNone(res["almuten"])

    def test_almuten_of_degree_uses_house_position(self):
        # 蟹 25°19′（昼）：木星 高揚4＋ターム2＝6、月 支配5＋フェイス1＝6
        res = nc.almuten_of_degree(lon("Can", 25 + 19 / 60), True,
                                   house_of={"Jupiter": 3, "Moon": 10})
        self.assertEqual(res["scores"]["Jupiter"], 6)
        self.assertEqual(res["scores"]["Moon"], 6)
        self.assertEqual(res["almuten"], "Moon")

    def test_figuris_tie(self):
        # 決定⑤：フィギュリスの同点はハウス位置で決着させず、両方を共同アルムテンとする
        # （蟹 25°19′：木星6・月6。月がアングル、木星がケーデントでも決着しない）
        places = {"asc": lon("Can", 25 + 19 / 60)}
        res = nc.almuten_figuris(places, True, {"Jupiter": 99},
                                 house_of={"Jupiter": 3, "Moon": 10})
        self.assertTrue(res["almuten_tie"])
        self.assertEqual(res["almutens"], ["Jupiter", "Moon"])
        self.assertIsNone(res["almuten"])
        self.assertNotIn("tie_break", res)

    def test_figuris_single_winner(self):
        places = {"asc": lon("Leo", 2), "sun": lon("Leo", 2)}
        res = nc.almuten_figuris(places, True, house_of={"Sun": 12})
        self.assertFalse(res["almuten_tie"])
        self.assertEqual(res["almutens"], ["Sun"])
        self.assertEqual(res["almuten"], "Sun")


class TestSect(unittest.TestCase):

    def test_horizon_method(self):
        asc = lon("Sco", 28)
        self.assertTrue(nc.is_day_chart(lon("Can", 28), asc))    # 第9ハウス側
        self.assertFalse(nc.is_day_chart(lon("Sag", 10), asc))   # 第1ハウス側

    def test_tokyo_sample_not_borderline(self):
        c = nc.calculate_classical_chart(1985, 7, 21, 14, 30, 35.6895, 139.6917)
        s = c["sect"]
        self.assertEqual(s["method"], "horizon_asc_dsc")
        self.assertTrue(s["is_day"])
        self.assertGreater(s["sun_altitude"], 0)
        self.assertFalse(s["borderline"])

    def test_polar_borderline(self):
        # ロングイェールビーン 夏至の真夜中：太陽は高度 +11°だが ASC–DSC 基準では夜図
        c = nc.calculate_classical_chart(2020, 6, 21, 0, 0, 78.2, 15.6, tz_offset=1.0)
        s = c["sect"]
        self.assertFalse(s["is_day"])
        self.assertGreater(s["sun_altitude"], 10)
        self.assertTrue(s["altitude_is_day"])
        self.assertTrue(s["borderline"])
        self.assertEqual(nc.to_json(c)["sect"]["borderline"], True)


class TestSampleChart(unittest.TestCase):

    def test_sample_v1_is_current(self):
        path = os.path.join(ROOT, "schema", "sample_chart_v1.json")
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        c = nc.calculate_classical_chart(1985, 7, 21, 14, 30, 35.6895, 139.6917)
        current = json.loads(json.dumps(nc.to_json(c), ensure_ascii=False))
        self.assertEqual(current, saved)

    def test_json_fields(self):
        c = nc.calculate_classical_chart(1985, 7, 21, 14, 30, 35.6895, 139.6917)
        d = nc.to_json(c)
        self.assertEqual(d["schema_version"], "v1")
        self.assertEqual(d["tables_used"]["terms"], "egyptian")
        self.assertEqual(d["tables_used"]["terms_audit"], "ptolemaic_lilly")
        src = d["tables_used"]["sources"]
        for key, sec in (("terms", "4.1"), ("triplicity", "3"), ("faces", "5"),
                         ("domicile", "1"), ("exaltation", "2"),
                         ("detriment", "6"), ("fall", "7")):
            self.assertTrue(src[key]["verified"], key)
            self.assertEqual(src[key]["citation"], f"METHOD_本質的品位表_v1.md §{sec}")
        self.assertFalse(src["terms_audit"]["verified"])
        self.assertIn("Case003", src["terms_audit"]["note"])
        for p in d["planets"]:
            ed = p["essential_dignity"]
            for k in ("triplicity_rulers", "peregrine_cancelled_by",
                      "score_note", "term_audit"):
                self.assertIn(k, ed)
        self.assertIn("almuten_tie", d["almuten_figuris"])
        self.assertIn("almutens", d["almuten_figuris"])
        self.assertIn("METHOD §8.2（v1.2）で確定", src["peregrine"]["note"])
        self.assertIn("almuten_tie", d["angles"]["ascendant"])


class TestSchemaV1(unittest.TestCase):
    """schema/SCHEMA_chart_v1.json（draft 2020-12、正本は デジタル販売/10_schema の参照コピー）"""

    @classmethod
    def setUpClass(cls):
        from jsonschema import Draft202012Validator
        with open(os.path.join(ROOT, "schema", "SCHEMA_chart_v1.json"), encoding="utf-8") as f:
            schema = json.load(f)
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)

    def assertValid(self, instance):
        errors = sorted(self.validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
        detail = "\n".join(f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
                           for e in errors)
        self.assertEqual(len(errors), 0, detail)

    def test_sample_chart_v1_conforms(self):
        with open(os.path.join(ROOT, "schema", "sample_chart_v1.json"), encoding="utf-8") as f:
            self.assertValid(json.load(f))

    def test_other_birth_data_conforms(self):
        # 2000-01-01 00:00 UTC+0、緯度 51.5 経度 −0.1（ロンドン）。
        # CLI の --json は UTC+9 固定のため、同じ処理（json.dumps(to_json(chart))）を直接呼ぶ
        c = nc.calculate_classical_chart(2000, 1, 1, 0, 0, 51.5, -0.1, tz_offset=0.0)
        out = json.loads(json.dumps(nc.to_json(c), ensure_ascii=False))
        self.assertEqual(out["birth_data"]["tz_offset"], 0.0)
        self.assertValid(out)

    def test_polar_chart_without_planetary_hour_conforms(self):
        # 2020-06-21 00:00 UTC+1、78.22N 15.63E（ロングイェールビーン）：白夜で日の出・日の入が
        # 求まらず planetary_day_hour は null（スキーマ rev.2 で許容）
        c = nc.calculate_classical_chart(2020, 6, 21, 0, 0, 78.22, 15.63, tz_offset=1.0)
        out = json.loads(json.dumps(nc.to_json(c), ensure_ascii=False))
        self.assertIsNone(out["planetary_day_hour"])
        self.assertValid(out)


if __name__ == "__main__":
    unittest.main()
