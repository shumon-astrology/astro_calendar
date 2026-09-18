"""SCHEMA_chart_v2.json が v1 rev.2 の加算的スーパーセットであることの検証（GT-6）

- 委員会の判断（要件書 v0.3 I-0）：新設 11 ブロックはすべて required。
  うち 6 つ（houses_summary, fixed_star_contacts, vocation, vocation_blocked_reason,
  moon_range, timing）は nullable で、該当しないときは null を書く。
- (a) sample_chart_v1.json を v2 スキーマにかけると、失敗は schema_version の const と
  新設 required 11 件の欠落だけ。
- (b) v2 から新設キーと nullable 化を機械的に外した派生スキーマでは sample が通る。
"""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_schema_v2 as builder  # noqa: E402

NEW_REQUIRED = ["moon_range", "derived", "houses_summary", "fixed_star_contacts",
                "boundary_warnings", "vocation", "vocation_blocked_reason", "timing",
                "summary", "reading_notes", "provenance"]


def _parent_and_key(root, path):
    """パスを解決する。途中が nullable 化（oneOf [本体, null]）されていれば本体に降りる"""
    segs = path.split("/")
    cur = root
    for seg in segs[:-1]:
        if seg not in cur and "oneOf" in cur:
            cur = cur["oneOf"][0]
        cur = cur[seg]
    if segs[-1] not in cur and "oneOf" in cur:
        cur = cur["oneOf"][0]
    return cur, segs[-1]


def strip_to_v1(v2, v1, added, nullable):
    """v2 から新設キーと nullable 化を機械的に外し、版の宣言を v1 に戻す"""
    derived = copy.deepcopy(v2)
    for path in added:
        if path.startswith("REQUIRED:"):
            p = path[len("REQUIRED:"):]
            owner_path = "/".join(p.split("/")[:-2])
            owner = derived
            for seg in owner_path.split("/") if owner_path else []:
                owner = owner[seg]
            owner["required"] = [k for k in owner["required"] if k != p.split("/")[-1]]
            continue
        parent, key = _parent_and_key(derived, path)
        parent.pop(key, None)
    for path in sorted(nullable, key=lambda p: p.count("/")):
        parent, key = _parent_and_key(derived, path)
        v1_parent, v1_key = _parent_and_key(v1, path)
        parent[key] = copy.deepcopy(v1_parent[v1_key])
    for k in ("$id", "title", "description", "x-schema_file_version", "x-sample", "x-method"):
        derived[k] = v1[k]
    derived.pop("x-requirements", None)
    derived.pop("$defs", None)
    for k in ("schema_version", "generator"):
        derived["properties"][k] = copy.deepcopy(v1["properties"][k])
    return derived


def without_descriptions(node):
    if isinstance(node, dict):
        return {k: without_descriptions(v) for k, v in sorted(node.items())
                if k != "description"}
    if isinstance(node, list):
        return [without_descriptions(x) for x in node]
    return node


class TestSchemaV2Additive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from jsonschema import Draft202012Validator
        cls.D = Draft202012Validator
        with open(os.path.join(ROOT, "schema", "SCHEMA_chart_v1.json"), encoding="utf-8") as f:
            cls.v1 = json.load(f)
        with open(os.path.join(ROOT, "schema", "SCHEMA_chart_v2.json"), encoding="utf-8") as f:
            cls.v2 = json.load(f)
        with open(os.path.join(ROOT, "schema", "sample_chart_v1.json"), encoding="utf-8") as f:
            cls.sample = json.load(f)
        cls.built, cls.added, cls.nullable = builder.build()

    def test_committed_schema_is_reproducible(self):
        """schema/SCHEMA_chart_v2.json は scripts/build_schema_v2.py の出力と一致する"""
        path = os.path.join(ROOT, "schema", "SCHEMA_chart_v2.json")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), builder.dumps(self.built))

    def test_schema_is_valid_draft_2020_12(self):
        self.D.check_schema(self.v2)

    def test_version_declarations(self):
        self.assertEqual(self.v2["$id"], "https://traditionalchart.com/schema/chart_v2.json")
        self.assertEqual(self.v2["properties"]["schema_version"]["const"], "v2")
        self.assertTrue(self.v2["x-schema_file_version"].startswith("v2 "))

    def test_new_blocks_are_required(self):
        for key in NEW_REQUIRED:
            self.assertIn(key, self.v2["required"], key)

    def test_nullable_new_blocks_accept_null(self):
        """該当しないときは null を書く（キーは常に存在する）"""
        for key in ("houses_summary", "fixed_star_contacts", "vocation",
                    "vocation_blocked_reason", "moon_range", "timing"):
            sub = self.v2["properties"][key]
            self.assertTrue(
                any(b.get("type") == "null" for b in sub.get("oneOf", []))
                or "null" in (sub.get("type") or []), key)

    def test_a_sample_v1_fails_only_on_version_and_new_required(self):
        errors = list(self.D(self.v2).iter_errors(self.sample))
        missing = sorted(e.message.split("'")[1] for e in errors
                         if e.validator == "required")
        others = [e for e in errors if e.validator != "required"]
        self.assertEqual(missing, sorted(NEW_REQUIRED))
        self.assertEqual(len(others), 1)
        self.assertEqual(list(others[0].absolute_path), ["schema_version"])
        self.assertEqual(others[0].validator, "const")
        self.assertEqual(len(errors), len(NEW_REQUIRED) + 1)

    def test_b_derived_schema_accepts_sample_v1(self):
        derived = strip_to_v1(self.v2, self.v1, self.added, self.nullable)
        self.D.check_schema(derived)
        errors = list(self.D(derived).iter_errors(self.sample))
        self.assertEqual([f"{'/'.join(map(str, e.absolute_path))}: {e.message}"
                          for e in errors], [])

    def test_b_derived_schema_equals_v1(self):
        """派生スキーマは description を除いて v1 と構造が一致する"""
        derived = strip_to_v1(self.v2, self.v1, self.added, self.nullable)
        self.assertEqual(without_descriptions(derived), without_descriptions(self.v1))


if __name__ == "__main__":
    unittest.main()
