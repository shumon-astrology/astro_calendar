"""js/data/*.json が natal_classical.py の定数と一致することの検証（Phase 2 手順 2）

JS 側は表を手打ちせず、scripts/export_tables.py の書き出しだけを使う。
このテストは「書き出しが最新か」を守る。
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import natal_classical as nc  # noqa: E402
import export_tables  # noqa: E402


class TestDataExport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.expected = export_tables.build()

    def test_files_match_python_constants(self):
        """書き出し済みのファイルが Python 定数と一致する（--check と同じ判定）"""
        for name, data in self.expected.items():
            path = os.path.join(export_tables.OUT_DIR, name)
            self.assertTrue(os.path.exists(path), f"{name} が無い")
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), export_tables.dumps(data), name)

    def test_terms_roundtrip(self):
        """書き出した形から元のタプル表を復元できる"""
        with open(os.path.join(export_tables.OUT_DIR, "tables_dignity.json"),
                  encoding="utf-8") as f:
            data = json.load(f)
        for key, table in (("egyptian", nc.TERMS_EGYPTIAN),
                           ("ptolemaic_lilly", nc.TERMS_PTOLEMAIC)):
            restored = [[(c["until"], c["ruler"]) for c in row]
                        for row in data["terms"]["tables"][key]]
            self.assertEqual(restored, table, key)

    def test_faces_and_rulerships(self):
        with open(os.path.join(export_tables.OUT_DIR, "tables_dignity.json"),
                  encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["faces"], nc.FACES)
        self.assertEqual(data["domicile_by_sign"], nc.DOMICILE_BY_SIGN)
        self.assertEqual(data["detriment_by_sign"], nc.DETRIMENT_BY_SIGN)
        self.assertEqual(data["dignity_scores"], nc.DIGNITY_SCORE)
        for si, (planet, degree) in nc.EXALT_BY_SIGN.items():
            self.assertEqual(data["exalt_by_sign"][str(si)],
                             {"planet": planet, "degree": degree})

    def test_orbs_and_accidental(self):
        with open(os.path.join(export_tables.OUT_DIR, "orbs.json"), encoding="utf-8") as f:
            orbs = json.load(f)
        self.assertEqual(orbs["moiety"], nc.MOIETY)
        self.assertEqual(orbs["combust_orb"], nc.COMBUST_ORB)
        self.assertEqual(orbs["cazimi_orb"], nc.CAZIMI_ORB)
        with open(os.path.join(export_tables.OUT_DIR, "accidental_points.json"),
                  encoding="utf-8") as f:
            acc = json.load(f)
        self.assertEqual(acc["house_score"], {str(k): v for k, v in nc.HOUSE_SCORE.items()})
        self.assertEqual(acc["weekday_rulers"], nc.WEEKDAY_RULERS)
        self.assertEqual(acc["fixed_stars_j2000"], nc.FIXED_STARS_J2000)


if __name__ == "__main__":
    unittest.main()
