"""SCHEMA v2 の vocation（I-3）と timing（I-5）ブロック"""

ASPECTS = ["conjunction", "sextile", "square", "trine", "opposition"]
CANDIDATES = ["Mars", "Venus", "Mercury"]
RULES = ["1", "2A", "2B", "3", "4", "5"]
REASONS = ["not_in_10_1_7", "no_essential_dignity", "combust", "under_beams",
           "not_mc_domicile_lord", "in_fall", "not_mc_almuten_three", "score_below_4",
           "no_partile_moon_aspect", "outside_moon_moiety", "afflicted_by_malefic",
           "ptolemy_no_candidate"]


def _condition_ref():
    return {"$ref": "#/$defs/condition"}


def _aspect_contact():
    return {"$ref": "#/$defs/aspect_contact"}


def vocation_schema(planets):
    planet_enum = {"type": "string", "enum": list(planets)}
    candidate_enum = {"type": "string", "enum": list(CANDIDATES)}
    body = {
        "type": "object",
        "description": (
            "Vocational significator (SKU 3). Steps 1-5 of the procedure are executed as a "
            "rule engine; every judgement uses only the values in candidates[], which come "
            "from the shared dignity engine. No profession words are produced here."),
        "properties": {
            "rules_version": {"type": "string"},
            "thresholds": {
                "type": "object",
                "properties": {
                    "combust_deg": {"type": "number", "const": 8.5},
                    "under_beams_deg": {"type": "number", "const": 17.0},
                    "cazimi_deg": {"type": "number"},
                    "rule4_moiety_deg": {"type": "number", "const": 6.25},
                    "rule4_citation": {"type": "string"},
                    "general_orb_note": {"type": "string"},
                },
                "required": ["combust_deg", "under_beams_deg", "cazimi_deg",
                             "rule4_moiety_deg"],
                "additionalProperties": True,
            },
            "candidates": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "description": "Mars, Venus and Mercury in that fixed order.",
                "items": {
                    "type": "object",
                    "properties": {
                        "planet": candidate_enum,
                        "position": {"type": "string"},
                        "house": {"type": ["integer", "null"]},
                        "house_raw": {"type": ["integer", "null"]},
                        "near_next_cusp": {"type": ["boolean", "null"]},
                        "essential": {
                            "type": "object",
                            "description": "Copied verbatim from the shared dignity engine (decision B).",
                            "properties": {
                                "dignities": {"type": "array", "items": {"type": "string"}},
                                "debilities": {"type": "array", "items": {"type": "string"}},
                                "score": {"type": "integer"},
                                "has_dignity": {
                                    "type": "boolean",
                                    "description": ("True when dignities[] is not empty "
                                                    "(decision A; peregrine is not used for this)."),
                                },
                                "peregrine": {"type": ["boolean", "null"]},
                                "peregrine_cancelled_by": {"type": ["string", "null"]},
                            },
                            "required": ["dignities", "debilities", "score", "has_dignity"],
                            "additionalProperties": True,
                        },
                        "solar": {
                            "type": "object",
                            "description": ("Solar condition under decision C: same_sign_as_sun "
                                            "must be true for cazimi, combust or under_beams."),
                            "properties": {
                                "distance_from_sun": {"type": "number"},
                                "same_sign_as_sun": {"type": "boolean"},
                                "cazimi": {"type": "boolean"},
                                "combust": {"type": "boolean"},
                                "under_beams": {"type": "boolean"},
                                "orientality": {"type": ["string", "null"],
                                                "enum": ["oriental", "occidental", None]},
                            },
                            "required": ["distance_from_sun", "same_sign_as_sun", "cazimi",
                                         "combust", "under_beams"],
                            "additionalProperties": True,
                        },
                        "angular": {"type": ["boolean", "null"]},
                        "in_house_10_1_7": {"type": ["boolean", "null"]},
                        "retrograde": {"type": "boolean"},
                        "malefic_afflictions": {"type": "array", "items": _aspect_contact()},
                        "moon_aspect": {
                            "oneOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "aspect": {"type": "string", "enum": ASPECTS},
                                        "orb": {"type": "number"},
                                        "partile": {"type": "boolean"},
                                        "within_moon_moiety": {
                                            "type": "boolean",
                                            "description": "Elongation from the Moon <= 6.25° (rule 4 only).",
                                        },
                                        "dissociate": {
                                            "type": "boolean",
                                            "description": ("True when the aspect holds by degree "
                                                            "but the signs do not agree."),
                                        },
                                        "direction": {"type": "string",
                                                      "enum": ["sinister", "dexter"]},
                                    },
                                    "required": ["aspect", "orb", "partile",
                                                 "within_moon_moiety", "dissociate"],
                                    "additionalProperties": True,
                                },
                                {"type": "null"},
                            ],
                            "description": "Closest Ptolemaic aspect to the Moon, or null.",
                        },
                        "eligibility": {
                            "type": "object",
                            "properties": {r if r in ("1", "3", "4", "5") else r:
                                           {"type": "boolean"}
                                           for r in ["rule1", "rule2a", "rule2b", "rule3",
                                                     "rule4", "rule5"]},
                            "required": ["rule1", "rule2a", "rule2b", "rule3", "rule4", "rule5"],
                            "additionalProperties": True,
                        },
                        "eligibility_reasons": {
                            "type": "object",
                            "additionalProperties": {"type": ["string", "null"]},
                            "description": "Why each rule failed, in words, for audit.",
                        },
                    },
                    "required": ["planet", "position", "essential", "solar", "eligibility"],
                    "additionalProperties": True,
                },
            },
            "mc_almuten_all": {
                "allOf": [{"$ref": "#/$defs/almuten_keys"}],
                "description": "Almuten of the MC degree over all seven planets (decision 4).",
            },
            "mc_almuten_three": {
                "type": "object",
                "description": ("Almuten of the MC degree restricted to Mars, Venus and "
                                "Mercury, with the rule 2B tie-break (higher dignity, then "
                                "nearer to an angle, then agreeing with the sect)."),
                "properties": {
                    "scores": {"type": "object",
                               "additionalProperties": {"type": "integer"}},
                    "winner": {"type": ["string", "null"]},
                    "tie": {"type": "boolean"},
                    "tie_break_used": {"type": ["string", "null"],
                                       "enum": ["dignity_rank", "angle_proximity", "sect", None]},
                    "winner_score": {"type": ["integer", "null"]},
                    "exaltation_or_better": {"type": "boolean"},
                },
                "required": ["scores", "winner", "tie", "tie_break_used", "winner_score"],
                "additionalProperties": True,
            },
            "significator": {
                "type": "object",
                "description": ("The chosen planet and the rule that fired. planet is null "
                                "when no rule settles it (see boundary_warnings)."),
                "properties": {
                    "planet": {"oneOf": [candidate_enum, {"type": "null"}]},
                    "rule_fired": {"type": ["string", "null"], "enum": RULES + [None]},
                    "rule_label": {"type": "string"},
                    "basis": {
                        "type": "object",
                        "properties": {
                            "has_dignity": {"type": "boolean"},
                            "dignities": {"type": "array", "items": {"type": "string"}},
                            "almuten_score": {"type": ["integer", "null"]},
                            "competitors": {"type": "object",
                                            "additionalProperties": {"type": "integer"}},
                            "tie_break_used": {"type": ["string", "null"]},
                        },
                        "additionalProperties": True,
                    },
                    "excluded": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "planet": candidate_enum,
                                "rule": {"type": "string", "enum": RULES},
                                "reason": {"type": "array",
                                           "items": {"type": "string", "enum": REASONS}},
                                "value": {"type": ["string", "number", "null"]},
                            },
                            "required": ["planet", "rule", "reason"],
                            "additionalProperties": True,
                        },
                    },
                    "multiple_qualified": {
                        "type": "array",
                        "items": candidate_enum,
                        "description": ("Candidates that also satisfied the rule that fired. "
                                        "The chosen one has the highest total_score; a "
                                        "remaining tie is flagged. Project convention."),
                    },
                    "citations": {"type": "array", "items": {"type": "string"}},
                    "extension_flag": {
                        "type": "boolean",
                        "description": "True when rule 2B fired, which is a project extension.",
                    },
                    "notes": {"type": "array", "items": {"type": "string"}},
                    "tie": {"type": "boolean"},
                },
                "required": ["planet", "rule_fired", "excluded"],
                "additionalProperties": True,
            },
            "settlement_tier": {
                "type": ["string", "null"],
                "enum": ["A", "B", "C", None],
                "description": "Rules 1 and 2A give A, rule 2B gives B, rules 3-5 give C.",
            },
            "not_excluded": {
                "type": "array",
                "items": candidate_enum,
                "description": ("Candidates other than the significator that no rule excluded; "
                                "the prompt must not dismiss them."),
            },
            "ptolemy_method": {
                "type": "object",
                "properties": {
                    "rising_before_sun": {"type": ["string", "null"]},
                    "mc_lord_or_occupant": {"type": "array", "items": planet_enum},
                    "agree": {"type": "boolean"},
                    "result": {"type": ["string", "null"]},
                },
                "required": ["rising_before_sun", "mc_lord_or_occupant", "agree", "result"],
                "additionalProperties": True,
            },
            "coley_method": {
                "type": "object",
                "properties": {
                    "h10_cusp_sign": {"type": "string"},
                    "h10_lord": planet_enum,
                    "h10_occupants": {"type": "array", "items": planet_enum},
                    "candidates_in_h10": {"type": "array", "items": candidate_enum},
                    "candidates_good_aspect_to_h10_lord": {"type": "array",
                                                           "items": candidate_enum},
                    "result": {"type": "array", "items": planet_enum},
                    "agrees_with_lilly": {"type": "boolean"},
                },
                "required": ["h10_cusp_sign", "h10_lord", "result", "agrees_with_lilly"],
                "additionalProperties": True,
            },
            "anima_124": {
                "type": "object",
                "properties": {
                    "h10_lord": planet_enum,
                    "asc_lord": planet_enum,
                    "note": {"type": "string"},
                },
                "required": ["h10_lord", "asc_lord", "note"],
                "additionalProperties": True,
            },
            "combinations": {
                "type": "array",
                "description": ("Aspects between the significator and other planets, mapped to "
                                "the rule_key of the combination table. No profession words."),
                "items": {
                    "type": "object",
                    "properties": {
                        # 手順書 §4-1 の組合せは 2〜4 天体（例：木星＋金星＋水星＋月）
                        "pair": {"type": "array", "items": planet_enum,
                                 "minItems": 2, "maxItems": 4},
                        "aspect": {"type": "string", "enum": ASPECTS},
                        "orb": {"type": "number"},
                        "applying": {"type": "boolean"},
                        "partile": {"type": "boolean"},
                        "same_sign": {"type": "boolean"},
                        "rule_key": {"type": "string"},
                        "citation": {"type": "string"},
                    },
                    "required": ["pair", "aspect", "rule_key"],
                    "additionalProperties": True,
                },
            },
            "absent_combinations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "pair": {"type": "array", "items": planet_enum,
                                 "minItems": 2, "maxItems": 4},
                        "rule_key": {"type": "string"},
                        "citation": {"type": "string"},
                    },
                    "required": ["pair", "rule_key"],
                    "additionalProperties": True,
                },
            },
            "special_conditions": {
                "type": "object",
                "properties": {
                    "mercury_yields_to_mars": {"type": "boolean"},
                    "mercury_retro_conj_venus_same_sign": {"type": "boolean"},
                    "mercury_moon_by_sign": {
                        "oneOf": [
                            {
                                "type": "object",
                                "properties": {
                                    "sign": {"type": "string", "enum": ["Virgo", "Scorpio"]},
                                    "applying": {"type": "boolean"},
                                },
                                "required": ["sign", "applying"],
                                "additionalProperties": True,
                            },
                            {"type": "null"},
                        ],
                    },
                    "venus_combust": {"type": "boolean"},
                    "venus_cazimi": {"type": "boolean"},
                    "mars_with_saturn": {"type": "boolean"},
                    "mercury_jupiter_aspect": {"type": "boolean"},
                },
                "additionalProperties": True,
            },
            "sign_attributes": {
                "type": ["object", "null"],
                "description": ("Attributes of the significator's sign from the procedure's "
                                "tables (verified: false). Attributes only, no selection."),
                "properties": {
                    "sign": {"type": "string"},
                    "element": {"type": "string",
                                "enum": ["fire", "earth", "air", "water"]},
                    "mode": {"type": "string",
                             "enum": ["cardinal", "fixed", "mutable"]},
                    "humane": {"type": "boolean"},
                    "voice": {"type": ["string", "boolean", "null"]},
                },
                "required": [],   # 主星が決まらなければ null
                "additionalProperties": True,
            },
            "success": {
                "type": ["object", "null"],
                "description": ("Four conditions of success. strong_essential means essential "
                                "score >= 3; grade is high for 4, mid for 2-3, low for 0-1. "
                                "Project convention."),
                "properties": {
                    "conditions": {
                        "type": "object",
                        "properties": {
                            "strong_essential": {"type": "boolean"},
                            "not_afflicted_partile_malefic": {"type": "boolean"},
                            "angular": {"type": "boolean"},
                            "oriental": {"type": "boolean"},
                        },
                        "required": ["strong_essential", "not_afflicted_partile_malefic",
                                     "angular", "oriental"],
                        "additionalProperties": True,
                    },
                    "conditions_met": {"type": "integer", "minimum": 0, "maximum": 4},
                    "of": {"type": "integer", "const": 4},
                    "grade": {"type": "string", "enum": ["high", "mid", "low"]},
                    "malefic_afflictions": {"type": "array", "items": _aspect_contact()},
                    "citation": {"type": "string"},
                },
                "required": [],   # 主星が決まらなければ null
                "additionalProperties": True,
            },
            "auxiliary": {
                "type": "object",
                "description": ("Conditions of the auxiliary places: houses 10, 2, 6 and 11, "
                                "the two lots, the Moon and the Sun."),
                "properties": {k: {"oneOf": [_condition_ref(), {"type": "null"}]}
                               for k in ["h10", "h2", "h6", "h11", "fortune", "spirit",
                                         "moon", "sun"]},
                "additionalProperties": True,
            },
            "dispositors": {
                "type": "array",
                "description": ("Condition of the domicile lord of each candidate's sign. "
                                "Provided instead of a warning, because \"badly placed\" is "
                                "not yet defined."),
                "items": _condition_ref(),
            },
            "fixed_stars": {
                "type": "array",
                "description": ("Contacts of the v1 fixed stars with the candidates and the "
                                "weakest planet. The wider catalogue is on hold."),
                "items": {
                    "type": "object",
                    "properties": {
                        "star": {"type": "string"},
                        "body": {"type": "string"},
                        "orb": {"type": "number"},
                        "body_is_weakest": {"type": "boolean"},
                    },
                    "required": ["star", "body", "orb"],
                    "additionalProperties": True,
                },
            },
            "warnings": {
                "type": "array",
                "description": "Only the four mechanically decidable warnings.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string",
                               "enum": ["mercury_jupiter_no_aspect", "venus_combust_no_profession",
                                        "mars_saturn_loses_rule", "mercury_yields_to_mars"]},
                        "citations": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id"],
                    "additionalProperties": True,
                },
            },
            "durability_layer": {
                "type": "object",
                "description": ("The three ordered triplicity lords of the MC sign, read only. "
                                "Never added to any score (verified: false)."),
                "properties": {
                    "verified": {"type": "boolean", "const": False},
                    "note": {"type": "string"},
                    "mc_sign": {"type": "string"},
                    "element": {"type": "string", "enum": ["fire", "earth", "air", "water"]},
                    "lords": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "rank": {"type": "integer", "minimum": 1, "maximum": 3},
                                "role": {"type": "string",
                                         "enum": ["day", "night", "participating"]},
                                "planet": planet_enum,
                                "house": {"type": ["integer", "null"]},
                                "essential_score": {"type": "integer"},
                                "accidental_score": {"type": ["integer", "null"]},
                                "retrograde": {"type": "boolean"},
                                "combust": {"type": "boolean"},
                                "malefic_afflictions": {"type": "array",
                                                        "items": _aspect_contact()},
                            },
                            "required": ["rank", "role", "planet", "essential_score"],
                            "additionalProperties": True,
                        },
                    },
                },
                "required": ["verified", "note", "mc_sign", "element", "lords"],
                "additionalProperties": True,
            },
            "system_divergence": {
                "type": "object",
                "description": ("Parallel computation with the Ptolemaic term and triplicity "
                                "audit tables. It never changes the judgement and must not be "
                                "quoted in summary."),
                "properties": {
                    "level": {"type": "integer", "minimum": 0, "maximum": 3},
                    "differences": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "operative": {},
                                "ptolemaic": {},
                                "level": {"type": "integer", "minimum": 0, "maximum": 3},
                                "note": {"type": "string"},
                            },
                            "required": ["field", "operative", "ptolemaic", "level"],
                            "additionalProperties": True,
                        },
                    },
                    "significator_ptolemaic": {"type": ["string", "null"]},
                    "settlement_tier_ptolemaic": {"type": ["string", "null"],
                                                  "enum": ["A", "B", "C", None]},
                },
                "required": ["level", "differences"],
                "additionalProperties": True,
            },
            "boundary_warnings": {
                "type": "array",
                "description": "Vocation-specific boundary warnings; same form as the top-level array.",
                "items": {"type": "object", "additionalProperties": True},
            },
            "timing_slice": {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "profection_reaches_h10_ages": {"type": "array",
                                                            "items": {"type": "integer"}},
                            "firdaria_lord_equals_significator": {"type": "array",
                                                                  "items": {"type": "object"}},
                        },
                        "additionalProperties": True,
                    },
                    {"type": "null"},
                ],
                "description": "Reserved; null in v2 rev.1 (METHOD_timing not written yet).",
            },
        },
        "required": ["rules_version", "thresholds", "candidates", "mc_almuten_three",
                     "significator", "settlement_tier", "not_excluded"],
        "additionalProperties": True,
    }
    return {
        "oneOf": [body, {"type": "null"}],
        "description": ("Vocational block (SKU 3). Null when the birth time is unknown or "
                        "when the procedure is not run; vocation_blocked_reason then says why."),
    }


def timing_schema():
    lord_period = {
        "type": "object",
        "properties": {
            "lord": {"type": "string"},
            "sub_lord": {"type": ["string", "null"]},
            "start": {"type": "string"},
            "end": {"type": "string"},
        },
        "required": ["lord", "start", "end"],
        "additionalProperties": True,
    }
    body = {
        "type": "object",
        "description": ("Time-lord block (SKU 2). Reserved: null in v2 rev.1. Only the shape "
                        "is validated; the values wait for METHOD_timing."),
        "properties": {
            "as_of": {"type": "string"},
            "valid_from": {"type": "string"},
            "valid_to": {"type": "string"},
            "firdaria": {
                "type": "object",
                "properties": {
                    "current": lord_period,
                    "sequence": {"type": "array", "items": lord_period},
                },
                "required": ["current", "sequence"],
                "additionalProperties": True,
            },
            "profection": {
                "type": "object",
                "properties": {
                    "annual": {
                        "type": "object",
                        "properties": {
                            "age": {"type": "integer"},
                            "house": {"type": "integer", "minimum": 1, "maximum": 12},
                            "sign": {"type": "string"},
                            "lord_of_year": {"type": "string"},
                            "start": {"type": "string"},
                            "end": {"type": "string"},
                        },
                        "required": ["age", "house", "sign", "lord_of_year"],
                        "additionalProperties": True,
                    },
                    "monthly": {
                        "type": "object",
                        "properties": {
                            "month_index": {"type": "integer"},
                            "house": {"type": "integer", "minimum": 1, "maximum": 12},
                            "sign": {"type": "string"},
                            "lord": {"type": "string"},
                            "start": {"type": "string"},
                            "end": {"type": "string"},
                        },
                        "required": ["month_index", "house", "sign", "lord"],
                        "additionalProperties": True,
                    },
                },
                "additionalProperties": True,
            },
            "transits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "planet": {"type": "string"},
                        "event": {"type": "string"},
                        "date": {"type": "string"},
                        "sign": {"type": "string"},
                        "dignity_at_event": {"type": "object", "additionalProperties": True},
                        "touches": {"type": "string",
                                    "enum": ["lord_of_year", "firdaria_lord",
                                             "firdaria_sub_lord"]},
                    },
                    "required": ["planet", "event", "date"],
                    "additionalProperties": True,
                },
            },
            "note": {"type": "string"},
        },
        "required": ["as_of", "valid_from", "valid_to"],
        "additionalProperties": True,
    }
    return {
        "oneOf": [body, {"type": "null"}],
        "description": ("Time-lord block (SKU 2). Null in v2 rev.1; the keys and types are "
                        "reserved so that a later revision can fill them."),
    }
