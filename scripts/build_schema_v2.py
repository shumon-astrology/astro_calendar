"""SCHEMA_chart_v1.json (rev.2) から SCHEMA_chart_v2.json を機械的に組み立てる。

    python3 scripts/build_schema_v2.py          # schema/SCHEMA_chart_v2.json を書き出す

加算原則：既存キーの型・意味・enum は触らない。
追加したキー（added）と nullable 化したパス（nullable）を記録して返し、
GT-6(b) の派生スキーマはその記録から機械的に戻して作る
（tests/test_schema_v2_additive.py）。
要件：10_schema/SCHEMA_v2_要件書_20260918.md v0.3 第 I 部。
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V1 = os.path.join(ROOT, "schema", "SCHEMA_chart_v1.json")
OUT = os.path.join(ROOT, "schema", "SCHEMA_chart_v2.json")

DRAFT_DATE = "2026-09-18"

PLANETS = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
HOUSE_CLASS = ["angular", "succedent", "cadent"]

schema = None
ADDED = []      # 新設キーのパス（派生スキーマでは削除する）
NULLABLE = []   # nullable 化したパス（派生スキーマでは v1 の定義に戻す）


def node_at(root, path):
    """'properties/planets/items/properties/house' 形式のパスでノードを取る"""
    cur = root
    for seg in path.split("/") if path else []:
        cur = cur[seg]
    return cur


def parent_and_key(root, path):
    segs = path.split("/")
    cur = root
    for seg in segs[:-1]:
        cur = cur[seg]
    return cur, segs[-1]


def add(path, subschema, required=False):
    """新設キーを追加し、記録する"""
    parent, key = parent_and_key(schema, path)
    assert key not in parent, f"already exists: {path}"
    parent[key] = subschema
    ADDED.append(path)
    if required:
        owner = node_at(schema, "/".join(path.split("/")[:-2]))
        owner.setdefault("required", []).append(key)
        ADDED.append("REQUIRED:" + path)
    return subschema


def make_nullable(path, note):
    """既存キーを oneOf [元の定義, null] にする（I-4 の time_known:false 用）"""
    parent, key = parent_and_key(schema, path)
    original = parent[key]
    parent[key] = {
        "oneOf": [original, {"type": "null"}],
        "description": (original.get("description", "").rstrip() + " "
                        if original.get("description") else "") + note,
    }
    NULLABLE.append(path)


def planet_enum(desc="Classical planet."):
    return {"type": "string", "enum": list(PLANETS), "description": desc}


def build():
    """v1 スキーマから v2 を組み立て、(schema, added, nullable) を返す"""
    global schema, ADDED, NULLABLE
    schema = json.load(open(V1, encoding="utf-8"))
    ADDED = []
    NULLABLE = []

    # ---------------------------------------------------------------- I-0 版・宣言
    schema["$id"] = "https://traditionalchart.com/schema/chart_v2.json"
    schema["title"] = ("SCHEMA_chart_v2 — Classical natal chart JSON "
                       "(AmanJyoshi / traditionalchart)")
    schema["x-schema_file_version"] = f"v2 ({DRAFT_DATE}, rev.1)"
    schema["x-method"] = ("METHOD_本質的品位表_v1.md v1.2 (+ decision C pending v1.3) / "
                          "METHOD_natal_v1.md v1.3 / "
                          "古典職業鑑定マニュアル v11 + 再基底化差分 2026-09-18")
    schema["x-sample"] = ("astro_calendar/schema/sample_chart_v1.json is the v1 sample; "
                          "a v2 sample is produced in Phase 3")
    schema["x-requirements"] = ("10_schema/SCHEMA_v2_要件書_20260918.md v0.2 "
                                "(第 I 部). Additive superset of v1 rev.2.")
    schema["description"] = (
        schema["description"].replace("SCHEMA_chart_v1", "SCHEMA_chart_v2")
        + " v2 (additive superset of v1 rev.2): every v1 key keeps its place, type and "
          "meaning; new blocks (derived, houses_summary, fixed_star_contacts, "
          "boundary_warnings, vocation, timing, summary, reading_notes, provenance) carry "
          "pre-computed judgement material so that the reading prompt never recomputes "
          "anything. Items that cannot exist when the birth time is unknown "
          "(time_known: false) are nullable. Solar conditions (cazimi / combust / under "
          "beams) additionally require the planet to be in the same sign as the Sun "
          "(decision C, 2026-09-18)."
    )
    schema["properties"]["schema_version"] = {
        "type": "string",
        "const": "v2",
        "description": ("Schema version. For prompts that accept v1 or v2 (PROMPT v0.3 and "
                        "later); a v1-only prompt rejects this file."),
    }
    schema["properties"]["generator"]["description"] = (
        "Identifier of the program that wrote this file, e.g. \"traditionalchart-js 0.1.0\".")

    # ------------------------------------------------------------- $defs（共通定義）
    schema["$defs"] = {
        "planet_name": planet_enum(),
        "house_class": {
            "type": "string",
            "enum": list(HOUSE_CLASS),
            "description": "Angular (1,4,7,10), succedent (2,5,8,11) or cadent (3,6,9,12).",
        },
        "aspect_contact": {
            "type": "object",
            "description": ("One aspect taken from aspects[]: who casts it, which aspect, "
                            "its orb, whether it is partile, and whether reception softens it."),
            "properties": {
                "by": {"$ref": "#/$defs/planet_name"},
                "aspect": {"type": "string",
                           "enum": ["conjunction", "sextile", "square", "trine", "opposition"]},
                "orb": {"type": "number"},
                "partile": {"type": "boolean"},
                "reception_softens": {"type": "boolean"},
            },
            "required": ["by", "aspect", "orb", "partile"],
            "additionalProperties": True,
        },
        "condition": {
            "type": "object",
            "description": ("Standard condition block: the state of one planet, copied from "
                            "planets[] and aspects[] so that no recomputation is needed. "
                            "classification uses the thresholds in derived.thresholds."),
            "properties": {
                "planet": {"$ref": "#/$defs/planet_name"},
                "sign": {"type": "string"},
                "position": {"type": "string",
                             "description": "Formatted position, e.g. \"Lib 04°09'\"."},
                "house": {"type": ["integer", "null"], "minimum": 1, "maximum": 12},
                "house_class": {"oneOf": [{"$ref": "#/$defs/house_class"}, {"type": "null"}]},
                "essential_score": {"type": "integer"},
                "accidental_score": {"type": ["integer", "null"]},
                "total_score": {"type": ["integer", "null"]},
                "dignities": {"type": "array", "items": {"type": "string"}},
                "debilities": {"type": "array", "items": {"type": "string"}},
                "peregrine": {"type": ["boolean", "null"]},
                "peregrine_cancelled_by": {"type": ["string", "null"]},
                "retrograde": {"type": "boolean"},
                "solar_phase": {"type": "string",
                                "enum": ["cazimi", "combust", "under_beams", "free", "sun"]},
                "in_sect": {"type": ["boolean", "null"]},
                "afflicted_by": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/aspect_contact"},
                    "description": ("Conjunction, square or opposition from Saturn or Mars, "
                                    "taken from aspects[]."),
                },
                "assisted_by": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/aspect_contact"},
                    "description": ("Conjunction, trine or sextile from Jupiter or Venus, "
                                    "taken from aspects[]."),
                },
                "classification": {
                    "type": "string",
                    "enum": ["favoured", "neutral", "effort"],
                    "description": ("favoured = essential >= threshold and accidental >= "
                                    "threshold; effort = essential <= threshold and accidental "
                                    "<= threshold; otherwise neutral. Thresholds are "
                                    "provisional (METHOD_natal_v1 decision 5)."),
                },
            },
            "required": ["planet", "sign", "position", "essential_score", "dignities",
                         "debilities", "classification"],
            "additionalProperties": True,
        },
        "source_entry": {
            "type": "object",
            "description": "Provenance label for one table or rule, as in v1 tables_used.sources.",
            "properties": {
                "table": {"type": "string"},
                "table_ja": {"type": "string"},
                "label": {"type": "string"},
                "citation": {"type": ["string", "null"]},
                "verified": {"type": "boolean"},
                "reference": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["table", "label", "citation", "verified"],
            "additionalProperties": True,
        },
        "almuten_keys": {
            "type": "object",
            "description": ("Almuten of a single degree (METHOD §10 decision 4): dignity points "
                            "of the seven planets at that degree; ties are resolved by house "
                            "position (angular > succedent > cadent) and, if still tied, "
                            "almuten is null with almuten_tie true."),
            "properties": {
                "almuten": {"type": ["string", "null"]},
                "almuten_tie": {"type": "boolean"},
                "almuten_candidates": {"type": "array", "items": {"type": "string"}},
                "almuten_tie_break": {"type": ["string", "null"],
                                      "enum": ["house_angularity", None]},
                "almuten_scores": {"type": "object", "additionalProperties": {"type": "integer"}},
            },
            "required": ["almuten", "almuten_tie", "almuten_candidates", "almuten_tie_break",
                         "almuten_scores"],
            "additionalProperties": True,
        },
    }

    # --------------------------------------------------------------- birth_data 追加
    bd = "properties/birth_data/properties"
    add(f"{bd}/place", {"type": ["string", "null"],
                        "description": "Birth place as entered by the user; informational only."})
    add(f"{bd}/timezone_id", {"type": ["string", "null"],
                              "description": ("IANA time zone id used to resolve the wall clock "
                                              "to UT (e.g. \"Asia/Tokyo\"). Null when the offset "
                                              "was supplied directly.")})
    add(f"{bd}/time_known", {"type": "boolean", "default": True,
                             "description": ("False when the birth time is unknown: positions "
                                             "are computed for local noon and the time-dependent "
                                             "blocks are null.")})
    add(f"{bd}/time_source", {"type": "string", "enum": ["entered", "noon_default"],
                              "description": "Where the time of day came from."})
    add(f"{bd}/dst_applied", {"type": ["boolean", "null"],
                              "description": ("True when the resolved offset includes daylight "
                                              "saving / summer time for that date and place.")})
    node_at(schema, "properties/birth_data/properties/tz_offset")["description"] = (
        "Offset from UT in hours, as resolved from timezone_id for this date "
        "(includes summer time when dst_applied is true).")

    # -------------------------------------------------------------- tables_used 追加
    tu = "properties/tables_used/properties"
    add(f"{tu}/scoring", {"type": "string", "const": "lilly",
                          "description": ("Scoring system for essential dignity "
                                          "(+5/+4/+3/+2/+1, -5/-4/-5). Declares the dignity "
                                          "system together with terms, triplicity and faces.")})
    add(f"{tu}/ephemeris", {
        "type": "object",
        "description": "Ephemeris actually used, for audit.",
        "properties": {
            "library": {"type": "string",
                        "description": ("e.g. \"Swiss Ephemeris (Moshier fallback)\" for the "
                                        "Python reference implementation, or \"astronomy-engine\" "
                                        "for the JavaScript port.")},
            "version": {"type": "string"},
            "frame": {"type": "string", "const": "true ecliptic of date"},
        },
        "required": ["library", "version", "frame"],
        "additionalProperties": True,
    })
    add(f"{tu}/timezone", {
        "type": "object",
        "description": "Source of the time zone rules used to resolve the birth time.",
        "properties": {
            "source": {"type": "string",
                       "description": "e.g. \"IANA tzdata via Intl\"."},
            "version": {"type": ["string", "null"]},
        },
        "required": ["source", "version"],
        "additionalProperties": True,
    })

    src = "properties/tables_used/properties/sources/properties"
    for key, desc in [
        ("lots", "Lots of Fortune and Spirit (Dorothean sect-reversed formulae)."),
        ("fixed_stars", "The three v1 fixed stars (Regulus, Spica, Algol) and how they are computed."),
        ("star_catalog", "Reserved for the forthcoming star set (royal stars + a few others); null/unused in v2 rev.1."),
        ("triplicity_order", "Ordered Dorothean triplicity rulers (1st/2nd/participating) per element and sect."),
        ("triplicity_audit", "Ptolemaic triplicity table, audit only, never scored."),
        ("vocation_rules", "Combination table and sign attributes of the vocational procedure."),
        ("derived_thresholds", "Thresholds used by derived.classification and success.grade."),
        ("planetary_hours", "Definition of sunrise/sunset used for the planetary day and hour."),
    ]:
        add(f"{src}/{key}", {"allOf": [{"$ref": "#/$defs/source_entry"}],
                             "description": desc})

    # --------------------------------------------------------------------- sect 追加
    sect = "properties/sect/properties"
    add(f"{sect}/moon_phase_quarter", {
        "type": ["string", "null"],
        "enum": ["new_to_first", "first_to_full", "full_to_last", "last_to_new", None],
        "description": ("Quarter of the lunation from the Moon-minus-Sun elongation e "
                        "(0<=e<360): 0-90 new_to_first, 90-180 first_to_full, 180-270 "
                        "full_to_last, 270-360 last_to_new."),
    })
    add(f"{sect}/season_quarter", {
        "type": ["string", "null"],
        "enum": ["spring", "summer", "autumn", "winter", None],
        "description": ("Quarter of the year from the Sun's sign_index: 0-2 spring, 3-5 "
                        "summer, 6-8 autumn, 9-11 winter. Tropical northern-hemisphere "
                        "convention; not mirrored in the southern hemisphere."),
    })
    add(f"{sect}/season_quarter_note", {
        "type": "string",
        "description": ("One-line note that season_quarter follows the quarters of the "
                        "ecliptic and is not mirrored south of the equator."),
    })
    tl = "properties/sect/properties/sect_light/properties/triplicity_lords/items/properties"
    add(f"{tl}/rank", {"type": "integer", "minimum": 1, "maximum": 3,
                       "description": "Position in the ordered Dorothean triple (1, 2 or 3)."})
    add(f"{tl}/role", {"type": "string", "enum": ["day", "night", "participating"],
                       "description": ("Role of this ruler for the element. The legacy key "
                                       "order (昼/夜/関与) is kept for compatibility.")})
    make_nullable("properties/sect",
                  "Null when the birth time is unknown (the ASC-DSC horizon is undefined).")

    # ------------------------------------------------------------------- angles 追加
    for angle in ("ascendant", "midheaven"):
        ap = f"properties/angles/properties/{angle}/properties"
        add(f"{ap}/also_known_as", {
            "type": "array", "items": {"type": "string"},
            "description": "Other names for this point, for prompts that use another vocabulary.",
        })
        add(f"{ap}/sign_change_within_minutes", {
            "type": ["integer", "null"],
            "description": ("Smallest number of minutes of birth time (searched +/-30 minutes "
                            "in one-minute steps, the smaller side) after which this point "
                            "changes sign; null when it does not change within 30 minutes."),
        })
        add(f"{ap}/minutes_to_previous_sign", {"type": ["integer", "null"],
                                               "description": "Minutes of birth time back to the previous sign; null beyond 30."})
        add(f"{ap}/minutes_to_next_sign", {"type": ["integer", "null"],
                                           "description": "Minutes of birth time forward to the next sign; null beyond 30."})

    mc = "properties/angles/properties/midheaven/properties"
    add(f"{mc}/lord", {"type": "string",
                       "description": "Domicile lord of the sign on the midheaven."})
    for key, sub in json.loads(json.dumps(schema["$defs"]["almuten_keys"]["properties"])).items():
        add(f"{mc}/{key}", sub)
    node_at(schema, f"{mc}/almuten")["description"] = (
        "Almuten of the midheaven degree (same form as the ascendant; METHOD §10 decision 4).")
    make_nullable("properties/angles",
                  "Null when the birth time is unknown.")

    # ------------------------------------------------------------------ planets 追加
    pp = "properties/planets/items/properties"
    ed = f"{pp}/essential_dignity/properties"
    add(f"{ed}/peregrine_scored", {
        "type": "boolean",
        "description": ("True when \"peregrine\" is present in debilities, i.e. the -5 was "
                        "actually counted. False when decision 3 suppressed it because the "
                        "planet is in detriment or fall."),
    })
    add(f"{ed}/peregrine_uncertain", {
        "type": "boolean",
        "default": False,
        "description": ("Only with time_known: false. True when the planet is a day or night "
                        "triplicity ruler of its sign and has no other dignity, so that "
                        "peregrine cannot be decided without the sect."),
    })
    make_nullable(f"{ed}/peregrine",
                  "Null when the birth time is unknown and the sect decides it (peregrine_uncertain).")
    make_nullable(f"{ed}/triplicity_rulers/properties/sect_ruler",
                  "Null when the sect is unknown, in which case triplicity is not scored.")
    add(f"{pp}/accidental_dignity/properties/items/items/properties/label_en",
        {"type": "string", "description": "English label of the accidental dignity item; label_ja is kept."})
    acc = node_at(schema, f"{pp}/accidental_dignity")
    acc["description"] = (
        (acc.get("description", "").rstrip() + " ") if acc.get("description") else ""
    ) + ("Solar conditions follow decision C (2026-09-18): cazimi (<=17'), combust (<=8°30') "
         "and under_beams (<=17°) all additionally require the planet to be in the same sign "
         "as the Sun; in a different sign the planet is free however close it is. "
         "Source: CA I ll.9344-9353 for combustion; the extension to cazimi and under beams "
         "is a project decision.")
    for path, note in [
        (f"{pp}/house", "Null when the birth time is unknown."),
        (f"{pp}/house_raw", "Null when the birth time is unknown."),
        (f"{pp}/near_next_cusp", "Null when the birth time is unknown."),
        (f"{pp}/above_horizon", "Null when the birth time is unknown."),
        (f"{pp}/accidental_dignity", "Null when the birth time is unknown (house points are required)."),
        (f"{pp}/sect", "Null when the birth time is unknown."),
        (f"{pp}/total_score", "Null when the birth time is unknown (no accidental score)."),
    ]:
        make_nullable(path, note)

    # -------------------------------------------------------------------- nodes 追加
    for kind in ("mean", "true"):
        np_ = f"properties/nodes/properties/{kind}/items/properties"
        add(f"{np_}/also_known_as", {"type": "array", "items": {"type": "string"},
                                     "description": "Other names for this node."})
        make_nullable(f"{np_}/house", "Null when the birth time is unknown.")

    # --------------------------------------------------------------------- lots 追加
    for lot in ("fortune", "spirit"):
        lp = f"properties/lots/properties/{lot}/properties"
        add(f"{lp}/also_known_as", {"type": "array", "items": {"type": "string"},
                                    "description": "Other names for this lot."})
        add(f"{lp}/sect_reversed", {
            "type": "boolean",
            "description": ("True in a nocturnal chart, where the Dorothean formula is "
                            "reversed (decision 6). Fortune = ASC + Moon - Sun by day and "
                            "ASC + Sun - Moon by night; Spirit is the mirror."),
        })
        add(f"{lp}/non_reversed_longitude", {
            "type": "number",
            "description": ("Longitude that the day formula would give, whatever the sect "
                            "(the Lilly practice). Provided so that a prompt never has to "
                            "reverse the lot itself."),
        })
        add(f"{lp}/non_reversed_position", {"type": "string",
                                            "description": "Formatted non_reversed_longitude."})
    make_nullable("properties/lots", "Null when the birth time is unknown (the ascendant is required).")

    # ------------------------------------------------------------------- houses 追加
    hp = "properties/houses/items/properties"
    for key, sub in json.loads(json.dumps(schema["$defs"]["almuten_keys"]["properties"])).items():
        add(f"{hp}/{key}", sub)
    node_at(schema, f"{hp}/almuten")["description"] = (
        "Almuten of this cusp degree (METHOD §10 decision 4). House 1 equals the ascendant "
        "and house 10 the midheaven.")
    make_nullable("properties/houses", "Null when the birth time is unknown.")

    # ------------------------------------------------------------------ aspects 追加
    ap_ = "properties/aspects/items/properties"
    add(f"{ap_}/reception_softens", {
        "type": "boolean",
        "description": ("For squares and oppositions: true when there is mutual reception or "
                        "one-way reception by domicile or exaltation. Project convention."),
    })
    add(f"{ap_}/reception_minor", {
        "type": "boolean",
        "description": ("True when the only reception is by term or face, which does not "
                        "count as softening. Project convention."),
    })
    add(f"{ap_}/time_unknown_caveat", {
        "type": "boolean",
        "default": False,
        "description": ("True when the birth time is unknown: applying/separating was judged "
                        "from the speeds at local noon."),
    })

    # --------------------------------------------------- almuten_figuris / prenatal
    make_nullable("properties/almuten_figuris",
                  "Null when the birth time is unknown (the ascendant and the Lot of Fortune are required).")
    # planetary_day_hour は v1 で既に oneOf [object, null]。二重に包むと null が両方に
    # 一致して oneOf が壊れるため、説明だけを補う
    pdh = node_at(schema, "properties/planetary_day_hour")
    pdh["description"] = (pdh.get("description", "").rstrip() + " "
                          + "Also null when the birth time is unknown. Sunrise and sunset are "
                            "apparent (refraction at 1013.25 hPa and 0°C), taken at the centre "
                            "of the Sun's disc, at sea level; see "
                            "tables_used.sources.planetary_hours.").strip()

    # ------------------------------------------------------------- 新設トップレベル
    add("properties/moon_range", {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "longitude_at_00_00": {"type": "number"},
                    "longitude_at_23_59": {"type": "number"},
                    "sign_at_00_00": {"type": "string"},
                    "sign_at_23_59": {"type": "string"},
                    "sign_change": {"type": "boolean"},
                },
                "required": ["longitude_at_00_00", "longitude_at_23_59", "sign_at_00_00",
                             "sign_at_23_59", "sign_change"],
                "additionalProperties": True,
            },
            {"type": "null"},
        ],
        "description": ("Only with time_known: false: the Moon's longitude at the start and "
                        "end of the local day, so that its range is explicit. Null otherwise."),
    }, required=True)

    add("properties/derived", {
        "type": "object",
        "description": ("Pre-computed reading material. Every value here is re-derivable from "
                        "planets[], houses[], aspects[] and lots; it carries no interpretation."),
        "properties": {
            "mode": {"type": "string", "enum": ["full", "time_unknown"]},
            "ranking_basis": {"type": "string", "enum": ["total_score", "essential_score"],
                              "description": ("total_score in full mode; essential_score when "
                                              "the birth time is unknown.")},
            "dignity_ranking": {
                "type": "array",
                "description": ("The seven planets by descending total_score. Ties are ordered "
                                "by house position (angular > succedent > cadent); planets that "
                                "are still tied share a rank and are marked tie: true."),
                "items": {
                    "type": "object",
                    "properties": {
                        "rank": {"type": "integer", "minimum": 1},
                        "planet": {"$ref": "#/$defs/planet_name"},
                        "total_score": {"type": ["integer", "null"]},
                        "essential_score": {"type": "integer"},
                        "accidental_score": {"type": ["integer", "null"]},
                        "house": {"type": ["integer", "null"]},
                        "house_class": {"oneOf": [{"$ref": "#/$defs/house_class"}, {"type": "null"}]},
                        "tie": {"type": "boolean"},
                    },
                    "required": ["rank", "planet", "essential_score", "tie"],
                    "additionalProperties": True,
                },
            },
            "strongest_planet": {"$ref": "#/$defs/ranking_extreme"},
            "weakest_planet": {"$ref": "#/$defs/ranking_extreme"},
            "lord_of_geniture": {
                "type": "object",
                "description": ("primary = almuten_figuris.almutens (decision 5: joint almutens "
                                "when tied); secondary = strongest_planet (decision 3)."),
                "properties": {
                    "primary": {"type": "array", "items": {"$ref": "#/$defs/planet_name"}},
                    "primary_basis": {"type": "string", "const": "almuten_figuris"},
                    "primary_tie": {"type": "boolean"},
                    "secondary": {"type": ["string", "null"]},
                    "secondary_basis": {"type": "string", "const": "total_score"},
                },
                "required": ["primary", "primary_basis", "primary_tie", "secondary",
                             "secondary_basis"],
                "additionalProperties": True,
            },
            "sect_light_condition": {"oneOf": [{"$ref": "#/$defs/condition"}, {"type": "null"}]},
            "asc_lord_condition": {
                "oneOf": [
                    {
                        "allOf": [{"$ref": "#/$defs/condition"}],
                        "type": "object",
                        "properties": {
                            "co_significator": {
                                "oneOf": [{"$ref": "#/$defs/condition"}, {"type": "null"}],
                                "description": ("Condition of the almuten of the ascendant when "
                                                "it differs from the domicile lord (decision 2); "
                                                "null when they are the same planet."),
                            },
                        },
                    },
                    {"type": "null"},
                ],
            },
            "lot_lords_condition": {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "fortune": {"$ref": "#/$defs/condition"},
                            "spirit": {"$ref": "#/$defs/condition"},
                        },
                        "required": ["fortune", "spirit"],
                        "additionalProperties": True,
                    },
                    {"type": "null"},
                ],
            },
            "out_of_sect_malefic": {
                "oneOf": [{"$ref": "#/$defs/condition"}, {"type": "null"}],
                "description": "Mars in a diurnal chart, Saturn in a nocturnal chart.",
            },
            "in_sect_benefic": {
                "oneOf": [{"$ref": "#/$defs/condition"}, {"type": "null"}],
                "description": "Jupiter in a diurnal chart, Venus in a nocturnal chart.",
            },
            "house_conditions": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "house": {"type": "integer", "minimum": 1, "maximum": 12},
                                "lord": {"$ref": "#/$defs/planet_name"},
                                "lord_house": {"type": ["integer", "null"]},
                                "essential_score": {"type": "integer"},
                                "accidental_score": {"type": ["integer", "null"]},
                                "classification": {"type": "string",
                                                   "enum": ["favoured", "neutral", "effort"]},
                                "lord_in_aversion": {
                                    "type": "boolean",
                                    "description": ("True when the difference of sign_index "
                                                    "between the lord's sign and the cusp's sign "
                                                    "is 1, 5, 7 or 11 (decision 10)."),
                                },
                            },
                            "required": ["house", "lord", "classification", "lord_in_aversion"],
                            "additionalProperties": True,
                        },
                    },
                    {"type": "null"},
                ],
            },
            "aversions_to_ascendant": {
                "oneOf": [
                    {"type": "array", "items": {"$ref": "#/$defs/planet_name"}},
                    {"type": "null"},
                ],
                "description": ("Planets whose sign_index differs from the ascendant's by "
                                "1, 5, 7 or 11."),
            },
            "reading_order": {
                "type": "array",
                "items": {"$ref": "#/$defs/planet_name"},
                "description": ("Decision 12: sect light, lord of the ascendant (then its "
                                "almuten when different), lord of the geniture, out-of-sect "
                                "malefic, then the rest in dignity_ranking order; first "
                                "occurrence wins."),
            },
            "thresholds": {
                "type": "object",
                "description": "Thresholds behind classification. Provisional operating values.",
                "properties": {
                    "favoured": {
                        "type": "object",
                        "properties": {"essential_min": {"type": "integer"},
                                       "accidental_min": {"type": "integer"}},
                        "required": ["essential_min", "accidental_min"],
                        "additionalProperties": True,
                    },
                    "effort": {
                        "type": "object",
                        "properties": {"essential_max": {"type": "integer"},
                                       "accidental_max": {"type": "integer"}},
                        "required": ["essential_max", "accidental_max"],
                        "additionalProperties": True,
                    },
                    "status": {"type": "string"},
                },
                "required": ["favoured", "effort", "status"],
                "additionalProperties": True,
            },
        },
        "required": ["mode", "ranking_basis", "dignity_ranking", "strongest_planet",
                     "weakest_planet", "lord_of_geniture", "reading_order", "thresholds"],
        "additionalProperties": True,
    }, required=True)

    schema["$defs"]["ranking_extreme"] = {
        "type": "object",
        "description": ("Head or tail of dignity_ranking. co[] lists the other planets on the "
                        "same score when tie is true."),
        "properties": {
            "planet": {"type": ["string", "null"]},
            "total_score": {"type": ["integer", "null"]},
            "essential_score": {"type": ["integer", "null"]},
            "tie": {"type": "boolean"},
            "co": {"type": "array", "items": {"$ref": "#/$defs/planet_name"}},
        },
        "required": ["planet", "tie", "co"],
        "additionalProperties": True,
    }

    add("properties/houses_summary", {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "intercepted_signs": {"type": "array", "items": {"type": "string"}},
                    "signs_on_two_cusps": {"type": "array", "items": {"type": "string"}},
                    "empty_houses": {"type": "array", "items": {"type": "integer"}},
                    "planets_by_house": {
                        "type": "object",
                        "additionalProperties": {"type": "array", "items": {"type": "string"}},
                        "description": "House number (as a string key) to the planets in it.",
                    },
                },
                "required": ["intercepted_signs", "signs_on_two_cusps", "empty_houses",
                             "planets_by_house"],
                "additionalProperties": True,
            },
            {"type": "null"},
        ],
        "description": ("Which signs are intercepted, which fall on two cusps, which houses are "
                        "empty and which planets are in each house. Null when the birth time is "
                        "unknown."),
    }, required=True)

    add("properties/fixed_star_contacts", {
        "oneOf": [
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "star": {"type": "string"},
                        "also_known_as": {"type": "array", "items": {"type": "string"}},
                        "magnitude": {"type": "number"},
                        "longitude": {"type": "number"},
                        "position": {"type": "string"},
                        "body": {"type": "string"},
                        "orb": {"type": "number"},
                        "orb_dms": {"type": "string"},
                        "grade": {"type": "string", "enum": ["judging", "reference"]},
                        "body_is_weakest": {"type": "boolean"},
                    },
                    "required": ["star", "longitude", "body", "orb", "grade"],
                    "additionalProperties": True,
                },
            },
            {"type": "null"},
        ],
        "description": ("Reserved. Contacts between the catalogue stars and the bodies, angles "
                        "and lots. Null in v2 rev.1: the star set (royal stars and a few others) "
                        "is on hold until METHOD settles it. The three v1 stars stay in "
                        "fixed_stars."),
    }, required=True)

    add("properties/boundary_warnings", {
        "type": "array",
        "description": ("Places where a small error in the birth time or a threshold changes "
                        "the chart. Level 1 informational, 2 material, 3 blocking."),
        "items": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "enum": ["asc_near_sign_boundary", "mc_near_sign_boundary", "planet_near_cusp",
                             "sect_borderline", "combust_boundary", "under_beams_boundary",
                             "rule4_boundary", "rule_margin", "system_divergence",
                             "no_significator"],
                },
                "level": {"type": "integer", "minimum": 1, "maximum": 3},
                "target": {"type": "string"},
                "value": {"type": ["number", "string", "null"]},
                "threshold": {"type": ["number", "string", "null"]},
                "message_en": {"type": "string"},
            },
            "required": ["id", "level", "target", "message_en"],
            "additionalProperties": True,
        },
    }, required=True)

    # vocation（I-3）は別ファイルに分けて可読性を保つ
    from schema_v2_vocation import vocation_schema, timing_schema  # noqa: E402

    add("properties/vocation", vocation_schema(PLANETS), required=True)
    add("properties/vocation_blocked_reason", {
        "type": ["string", "null"],
        "description": ("Why vocation is null, e.g. \"birth time unknown\". Null when vocation "
                        "is present."),
    }, required=True)
    add("properties/timing", timing_schema(), required=True)

    add("properties/summary", {
        "type": "string",
        "description": ("Eight fixed English lines (sect, ascendant, lord of the geniture, "
                        "strongest and weakest, out-of-sect malefic, lots, flags, birth time and "
                        "version). The wording is a template shared by every implementation and "
                        "contains no interpretation. Lines 1, 2, 5 and 6 read "
                        "\"n/a (birth time unknown)\" when the time is unknown."),
    }, required=True)

    add("properties/reading_notes", {
        "type": "array",
        "items": {"type": "string"},
        "description": ("Fixed English instructions for the reading prompt: everything is "
                        "already computed, raw fields win over summary and derived, audit fields "
                        "are never grounds for a judgement, boundary flags mark fragile "
                        "statements, and the rule-4 moiety is unrelated to aspect orbs. A sixth "
                        "note is added when the birth time is unknown."),
    }, required=True)

    add("properties/provenance", {
        "type": "object",
        "properties": {
            "cite_as": {"type": "string"},
            "license": {"type": ["string", "null"]},
            "method_docs": {"type": "array", "items": {"type": "string"}},
            "generated_at": {"type": "string",
                             "description": "ISO 8601 timestamp; the only value that changes between runs."},
            "generator": {"type": "string"},
            "reference_generator": {
                "type": ["string", "null"],
                "description": "e.g. \"natal_classical.py@e88df93\" when a reference implementation was used.",
            },
        },
        "required": ["cite_as", "license", "method_docs", "generated_at", "generator"],
        "additionalProperties": True,
    }, required=True)

    return schema, ADDED, NULLABLE


def dumps(schema_obj):
    """ファイルに書くときの正規形（テストと同じ文字列を作る）"""
    return json.dumps(schema_obj, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    built, added, nullable = build()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(dumps(built))
    print("wrote", OUT, os.path.getsize(OUT), "bytes")
    print("added keys:", len([a for a in added if not a.startswith("REQUIRED:")]),
          " nullable:", len(nullable))
