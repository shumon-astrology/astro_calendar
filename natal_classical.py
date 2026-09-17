"""
古典占星術ネイタルチャート計算モジュール
Classical (Traditional) Natal Chart Calculator

William Lilly "Christian Astrology" の体系に基づき、出生図の
本質的品位（Essential Dignities）・偶発的品位（Accidental Dignities）・
セクト・アラビックパーツ・アルムテンなどを算出する。

natal.py（モダン）との違い:
  - 天体は伝統的7惑星（♄♃♂☉♀☿☽）＋ドラゴンヘッド／テイルのみ
  - ノードは Mean Node（古典の慣行）
  - ハウスはレジオモンタナス（Lilly 準拠）を既定とし、
    プラシーダス／ホールサインも選択可
  - アスペクトはプトレマイオス的5種のみ、オーブは Lilly の
    「惑星のオーブ（moiety＝その半分）」表に従う
  - アプライング／セパレーティング、パーティル／プラティック、
    レセプション（受容）を明示

出典ラベルの方針（ホラリー正本プロジェクトの規約に準拠）:
  「リリー本文」＝ Christian Astrology に明記のある規則
  「プロジェクト慣行」＝ 実装上の補い（近似・簡略化を含む）
各表・各関数の docstring に出所を記す。

使い方:
    import natal_classical as nc
    chart = nc.calculate_classical_chart(1985, 7, 21, 14, 30, 35.6895, 139.6917)
    print(nc.generate_classical_text(chart))
"""

import swisseph as swe

import astro_calendar as ac
from natal import SIGN_JA, SIGN_SYMBOLS, ASPECT_SYMBOLS, determine_house


# ==============================================================================
# 定数：天体
# ==============================================================================

# 伝統的7惑星。カルデア順（土星→月）で保持する（Lilly の図表の並び）
TRAD_PLANETS = [
    (swe.SATURN,  "Saturn",  "土星", "♄"),
    (swe.JUPITER, "Jupiter", "木星", "♃"),
    (swe.MARS,    "Mars",    "火星", "♂︎"),
    (swe.SUN,     "Sun",     "太陽", "☉"),
    (swe.VENUS,   "Venus",   "金星", "♀︎"),
    (swe.MERCURY, "Mercury", "水星", "☿"),
    (swe.MOON,    "Moon",    "月",   "☽"),
]

PLANET_NAMES = [p[1] for p in TRAD_PLANETS]

PLANET_SYMBOLS = {p[1]: p[3] for p in TRAD_PLANETS}
PLANET_SYMBOLS.update({
    "Node": "☊", "SouthNode": "☋",
    "ASC": "", "MC": "", "Fortune": "⊕", "Spirit": "",
})

PLANET_JA = {p[1]: p[2] for p in TRAD_PLANETS}
PLANET_JA.update({
    "Node": "ドラゴンヘッド",
    "SouthNode": "ドラゴンテイル",
})

BENEFICS = ("Jupiter", "Venus")
MALEFICS = ("Saturn", "Mars")
LUMINARIES = ("Sun", "Moon")

# 平均日運動（度/日）。Lilly の「平均運動」表に合わせ、
# 内惑星（☿♀）と☉は 59'08" を用いる ＝ リリー本文
MEAN_MOTION = {
    "Saturn":  0.0334,    # 2'00"
    "Jupiter": 0.0831,    # 4'59"
    "Mars":    0.5242,    # 31'27"
    "Sun":     0.9856,    # 59'08"
    "Venus":   0.9856,    # 59'08"
    "Mercury": 0.9856,    # 59'08"
    "Moon":    13.1764,   # 13°10'35"
}

# Lilly「惑星のオーブ」表（度）＝ リリー本文。moiety はこの半分
PLANET_ORB = {
    "Saturn": 9.0, "Jupiter": 9.0, "Mars": 7.0, "Sun": 15.0,
    "Venus": 7.0, "Mercury": 7.0, "Moon": 12.0,
}
MOIETY = {k: v / 2.0 for k, v in PLANET_ORB.items()}

# 感受点（ASC/MC/パーツ等）のオーブ ＝ プロジェクト慣行（片側5°）
POINT_MOIETY = 5.0

# プトレマイオス的アスペクトのみ（マイナーアスペクトは古典では採らない）
CLASSICAL_ASPECTS = [
    (0.0,   "conjunction", "Con", "合"),
    (60.0,  "sextile",     "Sex", "六分"),
    (90.0,  "square",      "Squ", "矩"),
    (120.0, "trine",       "Tri", "三分"),
    (180.0, "opposition",  "Opp", "衝"),
]

# パーティル（同度数＝1°以内）の閾値 ＝ リリー本文
PARTILE_ORB = 1.0

# 太陽光線の状態（度）＝ リリー本文
CAZIMI_ORB = 17.0 / 60.0   # 17分
COMBUST_ORB = 8.5          # 8°30'
UNDER_BEAMS_ORB = 17.0


# ==============================================================================
# 定数：サインの性質
# ==============================================================================

ELEMENTS = ["fire", "earth", "air", "water"]
ELEMENT_JA = {"fire": "火", "earth": "地", "air": "風", "water": "水"}
MODALITY_JA = ["活動", "不動", "柔軟"]   # 活動・不動・柔軟
GENDER_JA = ["男性", "女性"]


def sign_of(lon):
    """黄経 → サインインデックス（0=牡羊）"""
    return int((lon % 360.0) // 30.0)


def deg_in_sign(lon):
    """黄経 → サイン内度数（0.0〜30.0）"""
    return (lon % 360.0) - sign_of(lon) * 30.0


def element_of(si):
    return ELEMENTS[si % 4]


def modality_of(si):
    return MODALITY_JA[si % 3]


def is_masculine_sign(si):
    """牡羊・双子・獅子…（奇数サイン）が男性サイン ＝ リリー本文"""
    return si % 2 == 0


# ==============================================================================
# 定数：本質的品位（Essential Dignities）＝ リリー本文（CA 表）
# ==============================================================================

# ドミサイル（サインの主星）
DOMICILE_BY_SIGN = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]

# デトリメント＝ドミサイルの対向サイン
DETRIMENT_BY_SIGN = [DOMICILE_BY_SIGN[(i + 6) % 12] for i in range(12)]

# イグザルテーション（惑星 → (サイン, 度数)）
EXALTATIONS = {
    "Sun": (0, 19), "Moon": (1, 3), "Jupiter": (3, 15), "Mercury": (5, 15),
    "Saturn": (6, 21), "Mars": (9, 28), "Venus": (11, 27),
}
# ドラゴンヘッド 双子3°／テイル 射手3°（Lilly の表に併記。得点計算には用いない）
NODE_EXALTATION = (2, 3)

EXALT_BY_SIGN = {si: (pl, dg) for pl, (si, dg) in EXALTATIONS.items()}
FALL_BY_SIGN = {(si + 6) % 12: (pl, dg) for pl, (si, dg) in EXALTATIONS.items()}

# トリプリシティ
# 既定はドロセウス式（参加星を含む3主星）。ホラリー実務（ケースNo002 の
# ラディカリティ判定・Collection の受容判定）が参加星を用いているため
# ＝ プロジェクト慣行。Lilly 表は triplicity="lilly" で選択できる
#
# Lilly 版：昼／夜の2主星のみ（水は昼夜とも火星）＝ リリー本文（要照合）
TRIPLICITY_LILLY = {
    "fire":  ("Sun", "Jupiter", None),
    "earth": ("Venus", "Moon", None),
    "air":   ("Saturn", "Mercury", None),
    "water": ("Mars", "Mars", None),
}
# ドロセウス式（昼・夜・参加の3主星）＝ 既定
TRIPLICITY_DOROTHEAN = {
    "fire":  ("Sun", "Jupiter", "Saturn"),
    "earth": ("Venus", "Moon", "Mars"),
    "air":   ("Saturn", "Mercury", "Jupiter"),
    "water": ("Venus", "Mars", "Moon"),
}

TRIPLICITY_TABLES = {
    "dorothean": TRIPLICITY_DOROTHEAN,
    "lilly": TRIPLICITY_LILLY,
}
DEFAULT_TRIPLICITY = "dorothean"

# エジプト式ターム（ドロテウス版）＝ 運用値 ＝ TABLE_SOURCES["terms"]
# METHOD_本質的品位表_v1.md §4.1 と全12行一致（2026-09-17 照合）。
# 初版は Ari〜Can が Lilly 値、Leo が混成だったため置き換えた
# 各サイン [(上限度数, 主星), ...]
TERMS_EGYPTIAN = [
    [(6, "Jupiter"), (12, "Venus"), (20, "Mercury"), (25, "Mars"), (30, "Saturn")],      # Ari
    [(8, "Venus"), (14, "Mercury"), (22, "Jupiter"), (27, "Saturn"), (30, "Mars")],      # Tau
    [(6, "Mercury"), (12, "Jupiter"), (17, "Venus"), (24, "Mars"), (30, "Saturn")],      # Gem
    [(7, "Mars"), (13, "Venus"), (19, "Mercury"), (26, "Jupiter"), (30, "Saturn")],      # Can
    [(6, "Jupiter"), (11, "Venus"), (18, "Saturn"), (24, "Mercury"), (30, "Mars")],      # Leo
    [(7, "Mercury"), (17, "Venus"), (21, "Jupiter"), (28, "Mars"), (30, "Saturn")],      # Vir
    [(6, "Saturn"), (14, "Mercury"), (21, "Jupiter"), (28, "Venus"), (30, "Mars")],      # Lib
    [(7, "Mars"), (11, "Venus"), (19, "Mercury"), (24, "Jupiter"), (30, "Saturn")],      # Sco
    [(12, "Jupiter"), (17, "Venus"), (21, "Mercury"), (26, "Saturn"), (30, "Mars")],     # Sag
    [(7, "Mercury"), (14, "Jupiter"), (22, "Venus"), (26, "Saturn"), (30, "Mars")],      # Cap
    [(7, "Mercury"), (13, "Venus"), (20, "Jupiter"), (25, "Mars"), (30, "Saturn")],      # Aqu
    [(12, "Venus"), (16, "Jupiter"), (19, "Mercury"), (28, "Mars"), (30, "Saturn")],     # Pis
]

# プトレマイオス式ターム（Lilly 版）＝ 監査専用。得点・アルムテン・レセプションには使わない
# ＝ TABLE_SOURCES["terms_audit"]（METHOD §4.2 の値。CA Book I と未照合）
TERMS_PTOLEMAIC = [
    [(6, "Jupiter"), (14, "Venus"), (21, "Mercury"), (26, "Mars"), (30, "Saturn")],      # Ari
    [(8, "Venus"), (15, "Mercury"), (22, "Jupiter"), (26, "Saturn"), (30, "Mars")],      # Tau
    [(7, "Mercury"), (14, "Jupiter"), (21, "Venus"), (25, "Mars"), (30, "Saturn")],      # Gem
    [(6, "Mars"), (13, "Jupiter"), (20, "Mercury"), (27, "Venus"), (30, "Saturn")],      # Can
    [(6, "Saturn"), (13, "Mercury"), (19, "Venus"), (25, "Jupiter"), (30, "Mars")],      # Leo
    [(7, "Mercury"), (13, "Venus"), (18, "Jupiter"), (24, "Mars"), (30, "Saturn")],      # Vir
    [(6, "Saturn"), (11, "Mercury"), (19, "Jupiter"), (24, "Venus"), (30, "Mars")],      # Lib
    [(6, "Mars"), (14, "Jupiter"), (21, "Venus"), (27, "Mercury"), (30, "Saturn")],      # Sco
    [(8, "Jupiter"), (14, "Venus"), (19, "Mercury"), (25, "Saturn"), (30, "Mars")],      # Sag
    [(6, "Venus"), (12, "Mercury"), (19, "Jupiter"), (25, "Mars"), (30, "Saturn")],      # Cap
    [(6, "Saturn"), (12, "Mercury"), (20, "Venus"), (25, "Jupiter"), (30, "Mars")],      # Aqu
    [(8, "Venus"), (14, "Jupiter"), (20, "Mercury"), (26, "Mars"), (30, "Saturn")],      # Pis
]

TERMS_TABLES = {
    "egyptian": TERMS_EGYPTIAN,
    "ptolemaic_lilly": TERMS_PTOLEMAIC,
}
DEFAULT_TERMS = "egyptian"
TERMS_AUDIT = "ptolemaic_lilly"

# フェイス（デカン）＝ カルデア順の循環 ＝ TABLE_SOURCES["faces"]
CHALDEAN_ORDER = ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"]
FACES = [
    [CHALDEAN_ORDER[(si * 3 + k) % 7] for k in range(3)]
    for si in range(12)
]

# 品位の得点 ＝ TABLE_SOURCES["dignity_scores"]
# トリプリシティはセクト主星のみ、ペレグリンはデトリメント／フォールと重複加算しない
DIGNITY_SCORE = {
    "domicile": 5, "exaltation": 4, "triplicity": 3, "term": 2, "face": 1,
    "detriment": -5, "fall": -4, "peregrine": -5,
}

DIGNITY_JA = {
    "domicile": "ドミサイル",
    "exaltation": "イグザルテーション",
    "triplicity": "トリプリシティ",
    "term": "ターム",
    "face": "フェイス",
    "detriment": "デトリメント",
    "fall": "フォール",
    "peregrine": "ペレグリン",
}


# ==============================================================================
# 出所ラベル（ホラリー正本プロジェクト規約）
# ==============================================================================
# 引用標準：Reprint ページ＋1647年版ページの併記 ＝「Reprint p.N［1647: p.M］」
# citation が None のものは未照合。照合の底本は
#   CA_BookI_II_fulltext.md（古典占星術プロジェクトKB）
# 確定後に citation を記入し verified を True にすること。

UNVERIFIED_NOTE = (
    "CA Book I 品位表（KB索引では CA_DH pp.45–47）と未照合。"
    "値は一般に流布する Lilly 版の表に基づく"
)

# 品位表の照合先（正本）。§番号は METHOD 文書の節
METHOD_DOC = "METHOD_本質的品位表_v1.md"
METHOD_REFERENCE = "~/Documents/デジタル販売/20_method/METHOD_本質的品位表_v1.md (v1.2)"
METHOD_VERIFIED_NOTE = f"{METHOD_DOC}（v1.2）と機械照合し全行一致（2026-09-17）"


def _method_source(table, table_ja, label, section, note=None):
    """METHOD 文書と照合済みの表の出所ラベル"""
    return {
        "table": table,
        "table_ja": table_ja,
        "label": label,
        "citation": f"{METHOD_DOC} §{section}",
        "verified": True,
        "reference": METHOD_REFERENCE,
        "note": note or METHOD_VERIFIED_NOTE,
    }


TABLE_SOURCES = {
    "terms": _method_source(
        "Egyptian (Dorothean) terms", "エジプト式ターム（ドロテウス版）",
        "プロジェクト慣行", "4.1",
        METHOD_VERIFIED_NOTE + "。初版の Ari〜Leo の5行（Lilly 値の混入）を置換済み。"
        "鑑定実務（鑑定依頼人台帳/出生図鑑定_Case003_20260901.md）がエジプト式のため運用値とする"),
    "terms_audit": {
        "table": "Ptolemaic terms (Lilly) — audit only, not scored",
        "table_ja": "プトレマイオス式ターム（Lilly 版）— 監査専用・得点に不使用",
        "label": "リリー本文",
        "citation": None,
        "verified": False,
        "reference": f"{METHOD_REFERENCE} §4.2",
        "note": ("値は METHOD §4.2 に一致。CA Book I 品位表（KB索引 CA_DH pp.45–47）との"
                 "照合が済むまで verified=false。"
                 "Case003（出生図鑑定_Case003_20260901.md §ターム）の2例で本表の判定と一致："
                 "M の☿♏15°41′（エジプト式＝☿自ターム／本表＝♀ターム→ペレグリン）、"
                 "M の♂♑28°30′（エジプト式＝♂自ターム／本表＝♄ターム）"),
    },
    "triplicity": _method_source(
        "Dorothean triplicity rulers (day / night / participating)",
        "ドロセウス式トリプリシティ（昼・夜・関与）", "プロジェクト慣行", "3",
        METHOD_VERIFIED_NOTE + "。得点はセクト主星のみ +3、関与星は加点なし"
        "（3主星は triplicity_rulers に出力）。"
        "関与星はホラリー実務のレセプション判定で用いる"
        "（ケースNo002_失せ物_バイオリン弓_20260827.md §ラディカリティ①・§Collection）。"
        "Lilly 版2主星表は triplicity='lilly' で選択可（こちらは未照合）"),
    "faces": _method_source("Faces (Chaldean order)", "フェイス（カルデア順）",
                            "リリー本文", "5"),
    "domicile": _method_source("Domicile (rulership)", "ルーラーシップ",
                               "リリー本文", "1"),
    "exaltation": _method_source(
        "Exaltation (with degrees)", "イグザルテーション（度数つき）", "リリー本文", "2",
        METHOD_VERIFIED_NOTE + "（7天体・度数を含む）。ノードの高揚は得点に用いない"),
    "detriment": _method_source("Detriment", "デトリメント", "リリー本文", "6"),
    "fall": _method_source("Fall", "フォール", "リリー本文", "7",
                           METHOD_VERIFIED_NOTE + "（7天体のみ）"),
    "dignity_scores": _method_source(
        "Essential dignity scores (5/4/3/2/1, -5/-4/-5)", "本質的品位の得点",
        "リリー本文", "8.1",
        METHOD_VERIFIED_NOTE + "。ペレグリンの扱いは §8.2 の決定①〜③に従う"),
    "peregrine": {
        "table": "Peregrine rule (Lilly + Lehman)",
        "table_ja": "ペレグリンの定義（Lilly＋Lehman）",
        "label": "プロジェクト慣行",
        "citation": f"{METHOD_DOC} §8.2",
        "verified": True,
        "reference": METHOD_REFERENCE,
        "note": ("決定①〜③（2026-09-17）：−5／サインまたはイグザルテーションの"
                 "ミューチュアル・レセプションで解除／デトリメント・フォールと重複加算しない。"
                 "サイン×イグザルテーションの mixed レセプション（mutual_reception_mixed）による"
                 "解除も含める：METHOD §8.2（v1.2）で確定"),
    },
    "almuten_tie": {
        "table": "Almuten ties (house position for single degrees / joint almutens for figuris)",
        "table_ja": "アルムテン同点時の扱い（単一度数＝ハウス位置／フィギュリス＝共同アルムテン）",
        "label": "プロジェクト慣行",
        "citation": f"{METHOD_DOC} §10",
        "verified": True,
        "reference": METHOD_REFERENCE,
        "note": ("決定④（2026-09-17）：単一度数のアルムテン（ASC・シジジー等）の同点は"
                 "アングル＞サクシーデント＞ケーデント（カスプ手前5°の繰り上げ適用）で決め、"
                 "なお同点なら almuten_tie=true で候補を列挙。"
                 "決定⑤（2026-09-17、METHOD §10 v1.2）：アルムテン・フィギュリスの同点は"
                 "ハウス位置で決着させず、同点の全天体を almutens に列挙して共同アルムテンとする"),
    },
    "sect": {
        "table": "Sect by horizon (ASC–DSC)",
        "table_ja": "昼夜判定（ASC–DSC 地平線基準）",
        "label": "プロジェクト慣行",
        "citation": f"{METHOD_DOC} §9",
        "verified": True,
        "reference": METHOD_REFERENCE,
        "note": ("太陽が ASC–DSC 軸より上（第7〜12ハウス側）なら昼図。"
                 "太陽の実高度は sun_altitude に併記し、判定が食い違えば borderline=true"),
    },
    "orbs": {
        "table": "Planetary orbs and moieties",
        "table_ja": "惑星のオーブとモイエティ",
        "label": "リリー本文",
        "citation": None,
        "verified": False,
        "note": ("ケースNo002 のモイエティ運用（§月・§Collection）と整合。"
                 "CA Book I 本文とは未照合"),
    },
    "accidental": {
        "table": "Accidental fortitudes and debilities",
        "table_ja": "偶発的品位・偶発的debility の表",
        "label": "リリー本文",
        "citation": None,
        "verified": False,
        "note": UNVERIFIED_NOTE,
    },
    "house_system": {
        "table": "Regiomontanus houses",
        "table_ja": "レジオモンタナス式ハウス",
        "label": "プロジェクト慣行",
        "citation": None,
        "verified": True,
        "note": ("Lilly が CA の全図で用いた方式。プロジェクト運用文書でも必須指定"
                 "（鑑定受付フォーム_v1.md 必須4／ケースファイル雛形_ホラリー.md）"),
    },
    "node": {
        "table": "Mean Node (true node reported for reference)",
        "table_ja": "平均ノード（トゥルーノードは参考値として併記）",
        "label": "プロジェクト慣行",
        "citation": None,
        "verified": True,
        "note": ("古典のエフェメリスは平均値を掲載するため mean を既定とする。"
                 "natal.py（モダン）は True Node を用いる"),
    },
}


# ==============================================================================
# 定数：偶発的品位（Accidental Dignities）＝ リリー本文（CA 表）
# ==============================================================================

HOUSE_SCORE = {1: 5, 10: 5, 7: 4, 4: 4, 11: 4, 2: 3, 5: 3, 9: 2, 3: 1,
               6: -2, 8: -2, 12: -5}

# 恒星（J2000 黄経）＝ プロジェクト慣行
# sefstars.txt がある環境では swe.fixstar2_ut を優先、無ければ
# J2000 値＋歳差 50.29"/年 の近似で算出する
FIXED_STARS_J2000 = {
    "Regulus": 149.847,   # 29Leo50
    "Spica":   203.833,   # 23Lib50
    "Algol":    56.167,   # 26Tau10
}
PRECESSION_PER_YEAR = 50.29 / 3600.0   # 度/年

# 曜日主星（0=月曜 … 6=日曜／datetime.weekday() 準拠）
WEEKDAY_RULERS = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]
# プラネタリーアワーの循環順（カルデア順・降順）
HOUR_ORDER = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

# セクト（昼夜の党派）＝ リリー本文
DIURNAL_PLANETS = ("Sun", "Jupiter", "Saturn")
NOCTURNAL_PLANETS = ("Moon", "Venus", "Mars")


# ==============================================================================
# 本質的品位の判定
# ==============================================================================

def term_ruler(lon, table=None):
    """
    タームの主星を返す。既定はエジプト式（TABLE_SOURCES["terms"]）。
    table に TERMS_PTOLEMAIC を渡すと監査用のプトレマイオス式で判定する
    """
    table = table or TERMS_TABLES[DEFAULT_TERMS]
    si = sign_of(lon)
    d = deg_in_sign(lon)
    for limit, ruler in table[si]:
        if d < limit:
            return ruler
    return table[si][-1][1]


def face_ruler(lon):
    """フェイス（デカン）の主星を返す ＝ リリー本文（カルデア順）"""
    si = sign_of(lon)
    return FACES[si][int(deg_in_sign(lon) // 10)]


def triplicity_rulers(si, table=None):
    """サインのトリプリシティ主星 (昼, 夜, 関与) を返す。既定はドロセウス式"""
    table = table or TRIPLICITY_TABLES[DEFAULT_TRIPLICITY]
    return table[element_of(si)]


def sign_dignity_kinds(planet, si):
    """planet がサイン si に対して持つ「サイン」「イグザルテーション」の品位"""
    kinds = []
    if DOMICILE_BY_SIGN[si] == planet:
        kinds.append("sign")
    if si in EXALT_BY_SIGN and EXALT_BY_SIGN[si][0] == planet:
        kinds.append("exaltation")
    return kinds


_MR_ORDER = ["mutual_reception_sign", "mutual_reception_exaltation",
             "mutual_reception_mixed"]


def mutual_receptions(planet, positions):
    """
    planet と他の古典6天体との、サインまたはイグザルテーションによる
    ミューチュアル・レセプションを列挙する（ペレグリン解除の判定用）
    ＝ METHOD §8.2 決定②（Lehman）。トリプリシティ・ターム・フェイスによるものは含めない。
    アスペクトの有無は問わない ＝ プロジェクト慣行

    Parameters:
        positions: {惑星名: 黄経}（7天体）
    Returns:
        [{"with": 相手, "type": "mutual_reception_sign"|"..._exaltation"|"..._mixed"}]
        （type は sign＝双方がサイン、exaltation＝双方が高揚、mixed＝サインと高揚）
    """
    my_si = sign_of(positions[planet])
    found = []
    for other, o_lon in positions.items():
        if other == planet:
            continue
        o_si = sign_of(o_lon)
        mine = sign_dignity_kinds(planet, o_si)     # planet が相手を受容
        theirs = sign_dignity_kinds(other, my_si)   # 相手が planet を受容
        types = set()
        for a in mine:
            for b in theirs:
                types.add("mutual_reception_" + (a if a == b else "mixed"))
        if types:
            found.append({"with": other,
                          "type": min(types, key=_MR_ORDER.index)})
    found.sort(key=lambda r: (_MR_ORDER.index(r["type"]), PLANET_NAMES.index(r["with"])))
    return found


PEREGRINE_SCORE_NOTE = (
    "peregrine but not scored: detriment/fall already counted "
    "(no double penalty, METHOD §8.2 decision 3)"
)


def essential_dignity(lon, planet, is_day, trip_table=None, receptions=None):
    """
    ある黄経における惑星の本質的品位を判定する ＝ METHOD §1〜§8

    - トリプリシティはセクト主星（昼図＝昼主星、夜図＝夜主星）にのみ +3。
      関与星は加点しない（3主星は triplicity_rulers に出す）
    - ペレグリン＝品位（上記基準）なし、かつサイン／イグザルテーションの
      ミューチュアル・レセプションなし。−5。
      レセプションがあれば解除（peregrine_cancelled_by に理由）。
      デトリメント／フォールがある場合は −5 を重ねない（score_note に注記）

    Parameters:
        receptions: mutual_receptions() の結果。None ならレセプションなしとして扱う
    Returns:
        dict: labels（成立した品位）, debilities, peregrine, peregrine_cancelled_by,
              score, score_note, rulers, triplicity_rulers, term_audit ほか
    """
    trip_table = trip_table or TRIPLICITY_TABLES[DEFAULT_TRIPLICITY]
    receptions = receptions or []
    si = sign_of(lon)
    d = deg_in_sign(lon)

    day_l, night_l, part_l = triplicity_rulers(si, trip_table)
    trip_ruler = day_l if is_day else night_l
    term_l = term_ruler(lon)
    term_audit_l = term_ruler(lon, TERMS_TABLES[TERMS_AUDIT])

    labels = []
    if DOMICILE_BY_SIGN[si] == planet:
        labels.append("domicile")
    if si in EXALT_BY_SIGN and EXALT_BY_SIGN[si][0] == planet:
        labels.append("exaltation")
    if planet == trip_ruler:
        labels.append("triplicity")
    if term_l == planet:
        labels.append("term")
    if face_ruler(lon) == planet:
        labels.append("face")

    debilities = []
    if DETRIMENT_BY_SIGN[si] == planet:
        debilities.append("detriment")
    if si in FALL_BY_SIGN and FALL_BY_SIGN[si][0] == planet:
        debilities.append("fall")

    peregrine = not labels
    cancelled_by = None
    score_note = None
    if peregrine and receptions:
        peregrine = False
        cancelled_by = receptions[0]["type"]
    if peregrine:
        if debilities:
            score_note = PEREGRINE_SCORE_NOTE
        else:
            debilities.append("peregrine")

    score = sum(DIGNITY_SCORE[l] for l in labels + debilities)

    return {
        "sign": si,
        "degree": d,
        "labels": labels,
        "debilities": debilities,
        "peregrine": peregrine,
        "peregrine_cancelled_by": cancelled_by,
        "mutual_receptions": receptions,
        "score": score,
        "score_note": score_note,
        "rulers": {
            "domicile": DOMICILE_BY_SIGN[si],
            "exaltation": EXALT_BY_SIGN.get(si, (None, None))[0],
            "triplicity": trip_ruler,
            "term": term_l,
            "face": face_ruler(lon),
        },
        "triplicity_rulers": {
            "day": day_l,
            "night": night_l,
            "participating": part_l,
            "sect_ruler": trip_ruler,   # +3 を受けるのはこの星のみ
        },
        "term_audit": {
            "table": TERMS_AUDIT,
            "ruler": term_audit_l,
            "differs": term_audit_l != term_l,
            "has_term": term_audit_l == planet,
        },
    }


def dignity_points(lon, planet, is_day, trip_table=None):
    """アルムテン用の品位点（+5/+4/+3/+2/+1 の合計。デビリティは含めない）"""
    ed = essential_dignity(lon, planet, is_day, trip_table)
    return sum(DIGNITY_SCORE[l] for l in ed["labels"])


# ハウス位置の強さ（アルムテン同点の決定用）＝ METHOD §10 決定④
ANGULAR_HOUSES = (1, 4, 7, 10)
SUCCEDENT_HOUSES = (2, 5, 8, 11)


def house_angularity(house):
    """アングル＝3、サクシーデント＝2、ケーデント＝1（house が None なら 0）"""
    if house in ANGULAR_HOUSES:
        return 3
    if house in SUCCEDENT_HOUSES:
        return 2
    return 1 if house else 0


def resolve_almuten(scores, house_of=None):
    """
    単一度数のアルムテンの勝者を決める ＝ METHOD §10 決定④
    （アルムテン・フィギュリスには用いない。決定⑤）
    最高点が複数ならハウス位置（アングル＞サクシーデント＞ケーデント）で決め、
    それでも同点なら almuten=None, almuten_tie=True とし候補を列挙する
    （機械的にそれ以上は細分しない）

    Parameters:
        scores:   {惑星名: 点}（0 点の惑星は含めなくてよい）
        house_of: {惑星名: ハウス番号（カスプ手前5°の繰り上げ適用済み）}
    """
    if not scores or max(scores.values()) <= 0:
        return {"almuten": None, "almuten_tie": False, "candidates": [],
                "tie_break": None}
    top = max(scores.values())
    cands = [n for n in PLANET_NAMES if scores.get(n) == top]
    if len(cands) == 1:
        return {"almuten": cands[0], "almuten_tie": False, "candidates": cands,
                "tie_break": None}

    house_of = house_of or {}
    best = max(house_angularity(house_of.get(n)) for n in cands)
    finalists = [n for n in cands if house_angularity(house_of.get(n)) == best]
    if len(finalists) == 1 and best > 0:
        return {"almuten": finalists[0], "almuten_tie": False, "candidates": cands,
                "tie_break": "house_angularity"}
    return {"almuten": None, "almuten_tie": True, "candidates": finalists,
            "tie_break": "house_angularity" if best > 0 else None}


def almuten_of_degree(lon, is_day, trip_table=None, house_of=None):
    """
    ある度数のアルムテン（最も品位の高い惑星）を求める ＝ METHOD §10
    各惑星の本質的品位得点（プラスのみ）を合算し、同点は resolve_almuten() で決める

    Returns:
        dict: almuten, almuten_tie, candidates, tie_break, scores
    """
    scores = {}
    for name in PLANET_NAMES:
        s = dignity_points(lon, name, is_day, trip_table)
        if s:
            scores[name] = s
    result = resolve_almuten(scores, house_of)
    result["scores"] = scores
    return result


# ==============================================================================
# セクト・太陽光線・オリエンタル／オクシデンタル
# ==============================================================================

SECT_METHOD = "horizon_asc_dsc"


def is_day_chart(sun_lon, asc_lon):
    """
    昼のチャートか ＝ METHOD §9（講座資料の定義）
    太陽が ASC–DSC 軸より上（ASC から黄道順に 180〜360°＝第7〜12ハウス側）なら昼図。
    ハウス方式やカスプ手前5°の規則には依存しない
    """
    return ((sun_lon - asc_lon) % 360.0) > 180.0


def sun_altitude(jd, lat, geo_lon):
    """太陽の実高度（度、大気差なし）。計算できなければ None"""
    try:
        xx, _ = swe.calc_ut(jd, swe.SUN, ac.CALC_FLAGS)
        _, true_alt, _ = swe.azalt(jd, swe.ECL2HOR, (geo_lon, lat, 0.0),
                                   0.0, 0.0, (xx[0], xx[1], xx[2]))
        return true_alt
    except Exception:
        return None


def sect_info(sun_lon, asc_lon, jd, lat, geo_lon):
    """
    セクト判定 ＝ METHOD §9
    判定は地平線基準（horizon_asc_dsc）。太陽高度は補助として併記し、
    高度による昼夜と食い違う場合（極圏・地平線際）は borderline=True
    """
    is_day = is_day_chart(sun_lon, asc_lon)
    alt = sun_altitude(jd, lat, geo_lon)
    alt_day = None if alt is None else alt > 0.0
    return {
        "method": SECT_METHOD,
        "is_day": is_day,
        "sun_altitude": alt,
        "altitude_is_day": alt_day,
        "borderline": alt_day is not None and alt_day != is_day,
    }


def solar_phase(planet_lon, sun_lon, planet_name):
    """
    太陽光線との関係を判定 ＝ リリー本文
    カジミ（17分以内）／コンバスト（8°30'以内）／サンビームス下（17°以内）／自由
    """
    if planet_name == "Sun":
        return {"state": "sun", "state_ja": "—", "distance": 0.0}
    dist = abs(((planet_lon - sun_lon + 180.0) % 360.0) - 180.0)
    if dist <= CAZIMI_ORB:
        state, ja = "cazimi", "カジミ"
    elif dist <= COMBUST_ORB:
        state, ja = "combust", "コンバスト"
    elif dist <= UNDER_BEAMS_ORB:
        state, ja = "under_beams", "サンビームス下"
    else:
        state, ja = "free", "光線から自由"
    return {"state": state, "state_ja": ja, "distance": round(dist, 2)}


def orientality(planet_lon, sun_lon, planet_name):
    """
    オリエンタル（太陽に先行して昇る）か オクシデンタルか ＝ リリー本文
    黄経で太陽より手前（(planet-sun)%360 > 180）ならオリエンタル
    """
    if planet_name == "Sun":
        return None
    diff = (planet_lon - sun_lon) % 360.0
    return "oriental" if diff > 180.0 else "occidental"


def moon_increasing(moon_lon, sun_lon):
    """月が光を増しているか（新月→満月）＝ リリー本文"""
    return ((moon_lon - sun_lon) % 360.0) < 180.0


def planet_sect(planet_name, orient):
    """
    惑星のセクト（党派）。水星はオリエンタルなら昼、オクシデンタルなら夜
    ＝ リリー本文
    """
    if planet_name in DIURNAL_PLANETS:
        return "diurnal"
    if planet_name in NOCTURNAL_PLANETS:
        return "nocturnal"
    return "diurnal" if orient == "oriental" else "nocturnal"


def hayz_status(planet_name, p_sect, is_day, above_horizon, sign_masculine):
    """
    ハイズ（Hayz）の判定 ＝ リリー本文
      - 昼の惑星が昼図で地平線上、かつ男性サインにある → ハイズ
      - 夜の惑星が夜図で地平線下、かつ女性サインにある → ハイズ
    半分だけ合う場合は「半ハイズ（ハーフ・ハイズ）」とする ＝ プロジェクト慣行
    """
    masculine_planet = p_sect == "diurnal"
    in_sect = (is_day and p_sect == "diurnal") or ((not is_day) and p_sect == "nocturnal")
    right_half = (is_day and above_horizon) or ((not is_day) and not above_horizon)
    right_sign = (masculine_planet and sign_masculine) or ((not masculine_planet) and not sign_masculine)

    if in_sect and right_half and right_sign:
        return "hayz", "ハイズ"
    if in_sect and (right_half or right_sign):
        return "half_hayz", "半ハイズ"
    if not in_sect and not right_half and not right_sign:
        return "contrary", "セクト違反"
    return "neutral", "—"


# ==============================================================================
# 恒星
# ==============================================================================

def fixed_star_longitudes(jd):
    """
    Regulus / Spica / Algol の黄経。
    sefstars.txt が使える環境では Swiss Ephemeris を、
    無ければ J2000 値＋歳差近似を用いる ＝ プロジェクト慣行
    """
    result = {}
    for name in FIXED_STARS_J2000:
        try:
            xx, _, _ = swe.fixstar2_ut(name, jd, ac.CALC_FLAGS)
            result[name] = xx[0]
        except Exception:
            years = (jd - 2451545.0) / 365.25
            result[name] = (FIXED_STARS_J2000[name] + PRECESSION_PER_YEAR * years) % 360.0
    return result


# ==============================================================================
# アスペクト（古典）
# ==============================================================================

def _signed_sep(lon1, lon2):
    """lon1 から見た lon2 への符号付き角度差（-180〜180）"""
    return ((lon2 - lon1 + 180.0) % 360.0) - 180.0


def _aspect_state(lon1, spd1, lon2, spd2, angle):
    """
    アプライング／セパレーティングの判定。
    離角の絶対値の時間変化から求める ＝ プロジェクト慣行（Lilly の定義に対応）
    """
    delta = _signed_sep(lon2, lon1)          # lon2 から見た lon1
    actual = abs(delta)
    rel = spd1 - spd2
    d_actual = rel if delta >= 0 else -rel   # d|delta|/dt
    if actual > angle:
        return "applying" if d_actual < 0 else "separating"
    return "applying" if d_actual > 0 else "separating"


def reception_between(p1, lon1, p2, lon2, is_day, trip_table=None):
    """
    p1 が p2 を、どの品位で受容（レセプション）しているかを返す。
    「p1 が p2 を受容する」＝ p2 の在泊する度数を p1 が支配している
    ＝ リリー本文
    トリプリシティによる受容はセクト主星に加えて関与星も認める
    （METHOD §3：関与星は得点なし・レセプション判定には用いる）
    """
    ed = essential_dignity(lon2, p1, is_day, trip_table)
    labels = list(ed["labels"])
    if ("triplicity" not in labels
            and ed["triplicity_rulers"]["participating"] == p1):
        pos = sum(1 for l in ("domicile", "exaltation") if l in labels)
        labels.insert(pos, "triplicity")
    return labels


def find_classical_aspects(bodies, is_day, trip_table=None):
    """
    古典的アスペクト（プトレマイオス5種）を検出する。
    オーブは両天体のモイエティの和 ＝ リリー本文

    Parameters:
        bodies: [{name_en, longitude, speed, is_point}] のリスト
    """
    aspects = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            b1, b2 = bodies[i], bodies[j]
            lon1, lon2 = b1["longitude"], b2["longitude"]
            diff = abs(_signed_sep(lon1, lon2))

            m1 = POINT_MOIETY if b1.get("is_point") else MOIETY[b1["name_en"]]
            m2 = POINT_MOIETY if b2.get("is_point") else MOIETY[b2["name_en"]]
            max_orb = m1 + m2

            for angle, full, abbrev, ja in CLASSICAL_ASPECTS:
                dev = abs(diff - angle)
                if dev > max_orb:
                    continue

                spd1 = b1.get("speed", 0.0)
                spd2 = b2.get("speed", 0.0)
                state = _aspect_state(lon1, spd1, lon2, spd2, angle)
                partile = dev <= PARTILE_ORB

                # デクスター／シニスター（速い側＝b1 が投げる向き）
                forward = (_signed_sep(lon1, lon2) > 0)
                direction = "sinister" if forward else "dexter"

                rec1 = rec2 = []
                if not b1.get("is_point") and not b2.get("is_point"):
                    rec1 = reception_between(b1["name_en"], lon1, b2["name_en"], lon2,
                                             is_day, trip_table)
                    rec2 = reception_between(b2["name_en"], lon2, b1["name_en"], lon1,
                                             is_day, trip_table)

                mutual = bool(rec1) and bool(rec2)
                aspects.append({
                    "planet1": b1["name_en"],
                    "planet1_ja": b1.get("name_ja", b1["name_en"]),
                    "planet1_symbol": PLANET_SYMBOLS.get(b1["name_en"], ""),
                    "planet2": b2["name_en"],
                    "planet2_ja": b2.get("name_ja", b2["name_en"]),
                    "planet2_symbol": PLANET_SYMBOLS.get(b2["name_en"], ""),
                    "aspect": full,
                    "aspect_abbrev": abbrev,
                    "aspect_ja": ja,
                    "aspect_symbol": ASPECT_SYMBOLS.get(full, ""),
                    "orb": round(dev, 2),
                    "max_orb": round(max_orb, 2),
                    "partile": partile,
                    "state": state,
                    "state_ja": "アプライ" if state == "applying" else "セパレート",
                    "direction": direction,
                    "reception_1to2": rec1,
                    "reception_2to1": rec2,
                    "mutual_reception": mutual,
                })

    aspects.sort(key=lambda a: (not a["partile"], a["orb"]))
    return aspects


def antiscia(lon):
    """アンティシャ（蟹0°／山羊0°軸の鏡像）と反アンティシャ ＝ リリー本文"""
    return (180.0 - lon) % 360.0, (360.0 - lon) % 360.0


# ==============================================================================
# アラビックパーツ・プレナタルシジジー
# ==============================================================================

def part_of_fortune(asc_lon, sun_lon, moon_lon, is_day):
    """
    フォーチュン（Pars Fortunae）＝ リリー本文（CA Ch.XXIII）
      昼： ASC ＋ ☽ − ☉ ／ 夜： ASC ＋ ☉ − ☽
    """
    if is_day:
        return (asc_lon + moon_lon - sun_lon) % 360.0
    return (asc_lon + sun_lon - moon_lon) % 360.0


def part_of_spirit(asc_lon, sun_lon, moon_lon, is_day):
    """スピリット（Pars Spiritus）＝ フォーチュンの昼夜逆算 ＝ プロジェクト慣行"""
    if is_day:
        return (asc_lon + sun_lon - moon_lon) % 360.0
    return (asc_lon + moon_lon - sun_lon) % 360.0


def prenatal_syzygy(jd_birth, max_days=32.0, step=0.25):
    """
    出生直前の新月または満月（プレナタル・シジジー）を求める。

    Returns:
        dict: jd, longitude, type（"new"/"full"）, datetime 文字列
    """
    best = None
    jd = jd_birth
    prev_vals = {
        0.0: ac.aspect_eval(ac.get_body_lon(jd, swe.MOON),
                            ac.get_body_lon(jd, swe.SUN), 0.0),
        180.0: ac.aspect_eval(ac.get_body_lon(jd, swe.MOON),
                              ac.get_body_lon(jd, swe.SUN), 180.0),
    }
    while jd > jd_birth - max_days:
        jd_prev = jd
        jd = jd - step
        for angle in (0.0, 180.0):
            val = ac.aspect_eval(ac.get_body_lon(jd, swe.MOON),
                                 ac.get_body_lon(jd, swe.SUN), angle)
            if ac.is_real_crossing(val, prev_vals[angle]):
                def f(t, a=angle):
                    return ac.aspect_eval(ac.get_body_lon(t, swe.MOON),
                                          ac.get_body_lon(t, swe.SUN), a)
                jd_exact = ac.bisect_find_zero(f, jd, jd_prev)
                if jd_exact is not None and (best is None or jd_exact > best[0]):
                    best = (jd_exact, angle)
            prev_vals[angle] = val
        if best is not None:
            break

    if best is None:
        return None

    jd_exact, angle = best
    moon_lon = ac.get_body_lon(jd_exact, swe.MOON)
    sun_lon = ac.get_body_lon(jd_exact, swe.SUN)
    # シジジーの度数は新月＝合の度数、満月＝そのとき地平線上にあった光の度数
    # ここでは伝統的な簡便法として、新月は合の度数、満月は月の度数を採る
    # ＝ プロジェクト慣行
    lon = sun_lon if angle == 0.0 else moon_lon
    dt = ac.jd_to_datetime_jst(jd_exact)
    return {
        "jd": jd_exact,
        "type": "new" if angle == 0.0 else "full",
        "type_ja": "新月" if angle == 0.0 else "満月",
        "longitude": lon,
        "sun_longitude": sun_lon,
        "moon_longitude": moon_lon,
        "datetime_str": ac.format_date_file2(dt),
    }


# ==============================================================================
# 曜日主星・時刻主星（プラネタリーアワー）
# ==============================================================================

def _sun_rise_set(jd, lat, lon, rise=True):
    """指定JD以降の最初の日の出／日の入りJDを返す（見つからなければ None）"""
    flag = swe.CALC_RISE if rise else swe.CALC_SET
    try:
        res, tret = swe.rise_trans(jd, swe.SUN, flag | swe.BIT_DISC_CENTER,
                                   (lon, lat, 0.0))
        if res == 0:
            return tret[0]
    except Exception:
        pass
    return None


def planetary_hour(jd, lat, lon):
    """
    出生時刻の曜日主星（Lord of the Day）と時刻主星（Lord of the Hour）。

    惑星の一日は日の出に始まり、昼夜それぞれを12等分した不等時間を用いる。
    時刻主星はカルデア順（♄♃♂☉♀☿☽）の循環 ＝ リリー本文
    （CA 巻末の惑星時テーブルは OCR 破損のため pyswisseph で計算する）
    """
    sunrise_prev = _sun_rise_set(jd - 1.0, lat, lon, rise=True)
    sunrise_next = _sun_rise_set(jd, lat, lon, rise=True)
    if sunrise_prev is None or sunrise_next is None:
        return None

    # 直前の日の出を特定
    if sunrise_next <= jd:
        sunrise = sunrise_next
        next_sunrise = _sun_rise_set(sunrise + 0.5, lat, lon, rise=True)
    else:
        sunrise = sunrise_prev
        next_sunrise = sunrise_next
    if next_sunrise is None:
        return None

    sunset = _sun_rise_set(sunrise, lat, lon, rise=False)
    if sunset is None or sunset <= sunrise:
        return None

    if jd < sunset:
        is_daytime = True
        hour_len = (sunset - sunrise) / 12.0
        index = int((jd - sunrise) / hour_len)
    else:
        is_daytime = False
        hour_len = (next_sunrise - sunset) / 12.0
        index = 12 + int((jd - sunset) / hour_len)
    index = max(0, min(23, index))

    # 惑星の一日の曜日（日の出時点の日付で判定）
    dt_sunrise = ac.jd_to_datetime_jst(sunrise)
    day_ruler = WEEKDAY_RULERS[dt_sunrise.weekday()]

    start = HOUR_ORDER.index(day_ruler)
    hour_ruler = HOUR_ORDER[(start + index) % 7]

    return {
        "day_ruler": day_ruler,
        "day_ruler_ja": PLANET_JA[day_ruler],
        "hour_ruler": hour_ruler,
        "hour_ruler_ja": PLANET_JA[hour_ruler],
        "hour_index": index + 1,
        "is_daytime": is_daytime,
        "sunrise_str": ac.format_date_file2(ac.jd_to_datetime_jst(sunrise)),
        "sunset_str": ac.format_date_file2(ac.jd_to_datetime_jst(sunset)),
    }


# ==============================================================================
# 偶発的品位（Accidental Dignities）
# ==============================================================================

def _is_besieged(lon, sat_lon, mars_lon):
    """
    ♄ と ♂ に挟まれているか（体の囲み＝簡略判定）。
    両悪星が30°以内で、当該天体がその短い弧の内側にある場合 ＝ プロジェクト慣行
    （Lilly の besieged はアスペクトの分離・接近を伴うが、ここでは体の囲みで近似）
    """
    arc = (mars_lon - sat_lon) % 360.0
    if arc > 180.0:
        sat_lon, mars_lon = mars_lon, sat_lon
        arc = (mars_lon - sat_lon) % 360.0
    if arc > 30.0:
        return False
    d = (lon - sat_lon) % 360.0
    return 0.0 < d < arc


def accidental_dignity(planet, ctx):
    """
    Lilly の「偶発的品位・偶発的debility」表に従って加減点する ＝ リリー本文
    （CA の表を実装。Via Combusta は同表には無いため得点化せず注記のみ）

    Parameters:
        planet: 天体 dict（name_en, longitude, speed, retrograde, house）
        ctx:    チャート文脈 dict（lons, sun_lon, node_lon, stars, is_day）

    Returns:
        dict: score, items [(英語コード, 和名, 点数), ...]
    """
    name = planet["name_en"]
    lon = planet["longitude"]
    speed = planet["speed"]
    items = []

    # --- ハウス（カスプ手前5°は次のハウスとして扱う）---
    h = planet.get("house_effective", planet["house"])
    if h in HOUSE_SCORE:
        items.append((f"house_{h}", f"第{h}ハウス", HOUSE_SCORE[h]))

    # --- 順行・逆行 / 速度（☉☾を除く）---
    if name not in LUMINARIES:
        if planet["retrograde"]:
            items.append(("retrograde", "逆行", -5))
        else:
            items.append(("direct", "順行", 4))
    if abs(speed) > MEAN_MOTION[name]:
        items.append(("swift", "速行（平均運動以上）", 2))
    else:
        items.append(("slow", "遅行（平均運動未満）", -2))

    # --- オリエンタル／オクシデンタル ---
    orient = planet.get("orientality")
    if name in ("Saturn", "Jupiter", "Mars"):
        items.append(("oriental", "オリエンタル", 2) if orient == "oriental"
                     else ("occidental", "オクシデンタル", -2))
    elif name in ("Venus", "Mercury"):
        items.append(("occidental", "オクシデンタル", 2) if orient == "occidental"
                     else ("oriental", "オリエンタル", -2))
    elif name == "Moon":
        if ctx["moon_increasing"]:
            items.append(("increasing_light", "増光", 2))
        else:
            items.append(("decreasing_light", "減光", -2))

    # --- 太陽光線 ---
    if name != "Sun":
        st = planet["solar_phase"]["state"]
        if st == "cazimi":
            items.append(("cazimi", "カジミ", 5))
        elif st == "combust":
            items.append(("combust", "コンバスト", -5))
        elif st == "under_beams":
            items.append(("under_beams", "サンビームス下", -4))
        else:
            items.append(("free_of_beams", "光線から自由", 5))

    # --- 他天体とのパーティル・アスペクト ---
    for other in ("Jupiter", "Venus", "Saturn", "Mars"):
        if other == name:
            continue
        o_lon = ctx["lons"][other]
        d = abs(_signed_sep(lon, o_lon))
        benefic = other in BENEFICS
        ol = other.lower()
        if d <= PARTILE_ORB:
            items.append((f"partile_conjunction_{ol}",
                          f"{PLANET_JA[other]}と合（パーティル）",
                          5 if benefic else -5))
        elif abs(d - 120.0) <= PARTILE_ORB and benefic:
            items.append((f"partile_trine_{ol}",
                          f"{PLANET_JA[other]}と三分（パーティル）", 4))
        elif abs(d - 60.0) <= PARTILE_ORB and benefic:
            items.append((f"partile_sextile_{ol}",
                          f"{PLANET_JA[other]}と六分（パーティル）", 3))
        elif abs(d - 180.0) <= PARTILE_ORB and not benefic:
            items.append((f"partile_opposition_{ol}",
                          f"{PLANET_JA[other]}と衝（パーティル）", -4))
        elif abs(d - 90.0) <= PARTILE_ORB and not benefic:
            items.append((f"partile_square_{ol}",
                          f"{PLANET_JA[other]}と矩（パーティル）", -3))

    # --- ノードとの合 ---
    if abs(_signed_sep(lon, ctx["node_lon"])) <= PARTILE_ORB:
        items.append(("partile_conjunction_north_node", "ドラゴンヘッドと合", 4))
    if abs(_signed_sep(lon, ctx["south_node_lon"])) <= PARTILE_ORB:
        items.append(("partile_conjunction_south_node", "ドラゴンテイルと合", -4))

    # --- 挟撃（besieged）---
    if name not in ("Saturn", "Mars"):
        if _is_besieged(lon, ctx["lons"]["Saturn"], ctx["lons"]["Mars"]):
            items.append(("besieged_saturn_mars", "土星と火星に挟まれる", -5))

    # --- 恒星 ---
    stars = ctx["stars"]
    if abs(_signed_sep(lon, stars["Regulus"])) <= PARTILE_ORB:
        items.append(("conjunct_regulus", "レグルスと合", 6))
    if abs(_signed_sep(lon, stars["Spica"])) <= PARTILE_ORB:
        items.append(("conjunct_spica", "スピカと合", 5))
    if abs(_signed_sep(lon, stars["Algol"])) <= 5.0:
        items.append(("conjunct_algol", "アルゴルと合（5°以内）", -5))

    return {"score": sum(it[2] for it in items), "items": items}


# ==============================================================================
# アルムテン・フィギュリス（出生図の総主星）
# ==============================================================================

HYLEGIACAL_LABELS = {
    "asc": "ASC", "sun": "太陽", "moon": "月",
    "fortune": "フォーチュン", "syzygy": "シジー",
}


def almuten_figuris(places, is_day, accidental_scores=None, trip_table=None,
                    house_of=None):
    """
    5つのハイレジカル・ポイント（ASC・☉・☾・フォーチュン・プレナタルシジジー）
    における本質的品位得点を合算し、出生図の総主星候補を求める ＝ プロジェクト慣行
    （イブン・エズラ由来の慣行。Lilly は「Lord of the Geniture」を
      総合判断で定めるため、本表は判断材料として提示する）
    同点はハウス位置で決着させず、同点の全天体を共同アルムテンとして
    almutens に列挙する ＝ METHOD §10 決定⑤
    （偶発的品位の得点・ハウスは参考として表に載せるが、順位の決定には用いない）

    Parameters:
        places:   {"asc": lon, "sun": lon, "moon": lon, "fortune": lon, "syzygy": lon}
        house_of: {惑星名: ハウス番号}（表示用）
    Returns:
        dict: almutens, almuten（単独時のみ。同点なら None）, almuten_tie, table, ranked
    """
    house_of = house_of or {}
    table = {}
    for name in PLANET_NAMES:
        row = {}
        total = 0
        for key, lon in places.items():
            if lon is None:
                row[key] = 0
                continue
            s = dignity_points(lon, name, is_day, trip_table)
            row[key] = s
            total += s
        row["total"] = total
        row["accidental"] = (accidental_scores or {}).get(name, 0)
        row["house"] = house_of.get(name)
        table[name] = row

    ranked = sorted(PLANET_NAMES, key=lambda n: table[n]["total"], reverse=True)
    top = table[ranked[0]]["total"]
    almutens = [n for n in ranked if table[n]["total"] == top] if top > 0 else []
    return {
        "almutens": almutens,
        "almuten": almutens[0] if len(almutens) == 1 else None,
        "almuten_tie": len(almutens) > 1,
        "table": table,
        "ranked": ranked,
    }


# ==============================================================================
# チャート計算
# ==============================================================================

HOUSE_SYSTEMS = {
    "R": ("Regiomontanus", "レジオモンタナス"),
    "P": ("Placidus", "プラシーダス"),
    "W": ("Whole Sign", "ホールサイン"),
    "C": ("Campanus", "カンパヌス"),
}


def _format_point(lon_deg, extra=None):
    """黄経 → 表示用 dict"""
    si, deg, mn = ac.lon_to_sign_deg_min(lon_deg)
    d = {
        "longitude": lon_deg,
        "sign": ac.SIGN_FULL[si],
        "sign_abbrev": ac.SIGN_ABBREV[si],
        "sign_ja": SIGN_JA[si],
        "sign_symbol": SIGN_SYMBOLS[si],
        "element": element_of(si),
        "element_ja": ELEMENT_JA[element_of(si)],
        "modality_ja": modality_of(si),
        "gender_ja": GENDER_JA[0 if is_masculine_sign(si) else 1],
        "degrees": deg,
        "minutes": mn,
        "position_str": f"{ac.SIGN_ABBREV[si]} {deg:02d}°{mn:02d}'",
        "position_ja": f"{SIGN_JA[si]}{SIGN_SYMBOLS[si]} {deg:02d}°{mn:02d}'",
    }
    if extra:
        d.update(extra)
    return d


def calculate_classical_chart(year, month, day, hour, minute, lat, lon,
                              tz_offset=9.0, house_system="R",
                              triplicity=DEFAULT_TRIPLICITY):
    """
    古典占星術のネイタルチャートを計算する。

    Parameters:
        year, month, day, hour, minute: 出生日時（現地時刻）
        lat, lon: 出生地の緯度・経度
        tz_offset: UTCからの時差（既定 9.0 ＝ JST）
        house_system: "R"（レジオモンタナス・既定）/"P"/"W"/"C"
        triplicity: "dorothean"（既定・参加星あり）/"lilly"（昼夜2主星）

    Returns:
        dict: planets, houses, house_rulers, asc, mc, sect, parts, syzygy,
              aspects, antiscia, almuten, planetary_hour, meta
    """
    trip_table = TRIPLICITY_TABLES.get(triplicity, TRIPLICITY_DOROTHEAN)
    jd = ac.datetime_local_to_jd(year, month, day, hour, minute, tz_offset)

    # --- ハウスカスプ・ASC・MC ---
    hsys = b"P" if house_system == "W" else house_system.encode()
    cusps, ascmc = swe.houses(jd, lat, lon, hsys)
    asc_lon, mc_lon = ascmc[0], ascmc[1]

    if house_system == "W":
        base = sign_of(asc_lon) * 30.0
        cusp_lons = [(base + 30.0 * i) % 360.0 for i in range(12)]
    else:
        cusp_lons = list(cusps)

    # --- 天体位置 ---
    raw = {}
    for body_id, name_en, name_ja, symbol in TRAD_PLANETS:
        lon_deg, speed = ac.get_body_lon_speed(jd, body_id)
        raw[name_en] = (lon_deg, speed)

    sun_lon = raw["Sun"][0]
    moon_lon = raw["Moon"][0]
    sect = sect_info(sun_lon, asc_lon, jd, lat, lon)
    is_day = sect["is_day"]
    increasing = moon_increasing(moon_lon, sun_lon)

    # 古典の慣行によりノードは Mean Node を既定とする ＝ TABLE_SOURCES["node"]
    # トゥルーノードは参考値として併記する（判断・得点には用いない）
    node_lon, node_speed = ac.get_body_lon_speed(jd, swe.MEAN_NODE)
    south_node_lon = (node_lon + 180.0) % 360.0
    true_node_lon, true_node_speed = ac.get_body_lon_speed(jd, swe.TRUE_NODE)
    true_south_node_lon = (true_node_lon + 180.0) % 360.0

    stars = fixed_star_longitudes(jd)
    positions = {n: raw[n][0] for n in PLANET_NAMES}

    planets = []
    for body_id, name_en, name_ja, symbol in TRAD_PLANETS:
        lon_deg, speed = raw[name_en]
        h_info = determine_house(lon_deg, cusp_lons)
        # カスプ手前5°は次のハウスに属すると見なす ＝ リリー本文
        house_eff = (h_info["house"] % 12 + 1) if h_info["near_cusp"] else h_info["house"]
        orient = orientality(lon_deg, sun_lon, name_en)
        p_sect = planet_sect(name_en, orient)
        above = house_eff >= 7
        hayz_key, hayz_ja = hayz_status(name_en, p_sect, is_day, above,
                                        is_masculine_sign(sign_of(lon_deg)))
        ed = essential_dignity(lon_deg, name_en, is_day, trip_table,
                               mutual_receptions(name_en, positions))
        ant, cont = antiscia(lon_deg)

        p = _format_point(lon_deg, {
            "name_en": name_en,
            "name_ja": name_ja,
            "symbol": symbol,
            "speed": speed,
            "retrograde": speed < 0,
            "house": h_info["house"],
            "house_effective": house_eff,
            "house_str": h_info["house_str"],
            "house_disp": f"{house_eff}*" if h_info["near_cusp"] else str(house_eff),
            "near_cusp": h_info["near_cusp"],
            "above_horizon": above,
            "orientality": orient,
            "orientality_ja": ("オリエンタル" if orient == "oriental"
                               else "オクシデンタル" if orient == "occidental" else "—"),
            "sect": p_sect,
            "sect_ja": "昼の星" if p_sect == "diurnal" else "夜の星",
            "in_sect": (is_day and p_sect == "diurnal") or ((not is_day) and p_sect == "nocturnal"),
            "hayz": hayz_key,
            "hayz_ja": hayz_ja,
            "solar_phase": solar_phase(lon_deg, sun_lon, name_en),
            "essential": ed,
            "antiscion": _format_point(ant),
            "contra_antiscion": _format_point(cont),
        })
        planets.append(p)

    # --- 偶発的品位 ---
    ctx = {
        "lons": {n: raw[n][0] for n in PLANET_NAMES},
        "sun_lon": sun_lon,
        "node_lon": node_lon,
        "south_node_lon": south_node_lon,
        "stars": stars,
        "is_day": is_day,
        "moon_increasing": increasing,
    }
    for p in planets:
        p["accidental"] = accidental_dignity(p, ctx)
        p["total_score"] = p["essential"]["score"] + p["accidental"]["score"]

    by_name = {p["name_en"]: p for p in planets}
    house_of = {p["name_en"]: p["house_effective"] for p in planets}

    # --- ノード（mean＝採用値／true＝参考値）---
    def _node_entries(nlon, snlon, spd, node_type):
        out = []
        for nm, lv in (("Node", nlon), ("SouthNode", snlon)):
            h_info = determine_house(lv, cusp_lons)
            house_eff = (h_info["house"] % 12 + 1) if h_info["near_cusp"] else h_info["house"]
            out.append(_format_point(lv, {
                "name_en": nm,
                "name_ja": PLANET_JA[nm],
                "symbol": PLANET_SYMBOLS[nm],
                "speed": spd if nm == "Node" else spd,
                "retrograde": spd < 0,
                "house": h_info["house"],
                "house_effective": house_eff,
                "house_str": h_info["house_str"],
                "node_type": node_type,
            }))
        return out

    nodes = _node_entries(node_lon, south_node_lon, node_speed, "mean")
    nodes_true = _node_entries(true_node_lon, true_south_node_lon,
                               true_node_speed, "true")

    # --- 現代天体（古典判断には用いない参考値）---
    modern_reference = []
    for body_id, nm, nm_ja in ((swe.URANUS, "Uranus", "天王星"),
                               (swe.NEPTUNE, "Neptune", "海王星"),
                               (swe.PLUTO, "Pluto", "冥王星")):
        m_lon, m_speed = ac.get_body_lon_speed(jd, body_id)
        h_info = determine_house(m_lon, cusp_lons)
        house_eff = (h_info["house"] % 12 + 1) if h_info["near_cusp"] else h_info["house"]
        modern_reference.append(_format_point(m_lon, {
            "name_en": nm, "name_ja": nm_ja,
            "speed": m_speed, "retrograde": m_speed < 0,
            "house": h_info["house"], "house_effective": house_eff,
        }))

    # --- ハウスカスプと各ハウス主星 ---
    houses = []
    house_rulers = []
    for i, c_lon in enumerate(cusp_lons):
        hd = _format_point(c_lon, {"number": i + 1})
        houses.append(hd)

        lord = DOMICILE_BY_SIGN[sign_of(c_lon)]
        lp = by_name[lord]
        house_rulers.append({
            "house": i + 1,
            "sign_ja": hd["sign_ja"],
            "sign_symbol": hd["sign_symbol"],
            "lord": lord,
            "lord_ja": PLANET_JA[lord],
            "lord_symbol": PLANET_SYMBOLS[lord],
            "lord_position_ja": lp["position_ja"],
            "lord_house": lp["house_effective"],
            "lord_dignity": lp["essential"]["labels"],
            "lord_score": lp["essential"]["score"],
            "lord_retrograde": lp["retrograde"],
            "lord_solar_phase": lp["solar_phase"]["state_ja"],
        })

    # --- ASC / MC / パーツ ---
    asc = _format_point(asc_lon)
    mc = _format_point(mc_lon)
    asc_alm = almuten_of_degree(asc_lon, is_day, trip_table, house_of)
    asc["almuten"] = asc_alm["almuten"]
    asc["almuten_scores"] = asc_alm["scores"]
    asc["almuten_detail"] = asc_alm
    asc_lord = DOMICILE_BY_SIGN[sign_of(asc_lon)]
    asc["lord"] = asc_lord
    asc["lord_ja"] = PLANET_JA[asc_lord]

    fortune_lon = part_of_fortune(asc_lon, sun_lon, moon_lon, is_day)
    spirit_lon = part_of_spirit(asc_lon, sun_lon, moon_lon, is_day)
    fh = determine_house(fortune_lon, cusp_lons)
    sh = determine_house(spirit_lon, cusp_lons)
    fortune = _format_point(fortune_lon, {
        "name_en": "Fortune", "name_ja": "フォーチュン",
        "symbol": PLANET_SYMBOLS["Fortune"],
        "house": fh["house"], "house_str": fh["house_str"],
        "lord": DOMICILE_BY_SIGN[sign_of(fortune_lon)],
    })
    spirit = _format_point(spirit_lon, {
        "name_en": "Spirit", "name_ja": "スピリット",
        "house": sh["house"], "house_str": sh["house_str"],
        "lord": DOMICILE_BY_SIGN[sign_of(spirit_lon)],
    })

    # --- プレナタル・シジジー ---
    syzygy = prenatal_syzygy(jd)
    if syzygy:
        syzygy["point"] = _format_point(syzygy["longitude"])
        sz_alm = almuten_of_degree(syzygy["longitude"], is_day, trip_table, house_of)
        syzygy["almuten"] = sz_alm["almuten"]
        syzygy["almuten_detail"] = sz_alm

    # --- アスペクト ---
    bodies = [{
        "name_en": p["name_en"], "name_ja": p["name_ja"],
        "longitude": p["longitude"], "speed": p["speed"],
    } for p in planets]
    bodies.append({"name_en": "ASC", "name_ja": "ASC", "longitude": asc_lon,
                   "speed": 0.0, "is_point": True})
    bodies.append({"name_en": "MC", "name_ja": "MC", "longitude": mc_lon,
                   "speed": 0.0, "is_point": True})
    bodies.append({"name_en": "Fortune", "name_ja": "フォーチュン",
                   "longitude": fortune_lon, "speed": 0.0, "is_point": True})
    aspects = find_classical_aspects(bodies, is_day, trip_table)

    # --- アルムテン・フィギュリス ---
    places = {
        "asc": asc_lon, "sun": sun_lon, "moon": moon_lon,
        "fortune": fortune_lon,
        "syzygy": syzygy["longitude"] if syzygy else None,
    }
    acc_scores = {p["name_en"]: p["accidental"]["score"] for p in planets}
    almuten = almuten_figuris(places, is_day, acc_scores, trip_table, house_of)

    # --- セクトライトの三分主星 ---
    light = "Sun" if is_day else "Moon"
    light_si = sign_of(raw[light][0])
    d_l, n_l, p_l = triplicity_rulers(light_si, trip_table)
    sect_light = {
        "light": light,
        "light_ja": PLANET_JA[light],
        "sign_ja": SIGN_JA[light_si],
        "element_ja": ELEMENT_JA[element_of(light_si)],
        "lords": [],
    }
    seen = {}
    for label, nm in (("昼", d_l), ("夜", n_l), ("関与", p_l)):
        if nm is None:
            continue
        if nm in seen:   # Lilly の水の三分主星は昼夜とも火星
            seen[nm]["order"] += "・" + label
            continue
        lp = by_name[nm]
        entry = {
            "order": label, "planet": nm, "planet_ja": PLANET_JA[nm],
            "position_ja": lp["position_ja"], "house": lp["house_effective"],
            "dignity": lp["essential"]["labels"],
            "score": lp["essential"]["score"] + lp["accidental"]["score"],
        }
        seen[nm] = entry
        sect_light["lords"].append(entry)

    return {
        "planets": planets,
        "nodes": nodes,
        "nodes_true": nodes_true,
        "modern_reference": modern_reference,
        "houses": houses,
        "house_rulers": house_rulers,
        "asc": asc,
        "mc": mc,
        "fortune": fortune,
        "spirit": spirit,
        "syzygy": syzygy,
        "aspects": aspects,
        "almuten": almuten,
        "sect_light": sect_light,
        "planetary_hour": planetary_hour(jd, lat, lon),
        "sect": dict(sect,
                     label_ja="昼のチャート" if is_day else "夜のチャート",
                     moon_increasing=increasing),
        "stars": {k: _format_point(v) for k, v in stars.items()},
        "meta": {
            "jd": jd,
            "birth": {
                "year": year, "month": month, "day": day,
                "hour": hour, "minute": minute,
                "tz_offset": tz_offset, "latitude": lat, "longitude": lon,
            },
            "house_system": house_system,
            "house_system_name": HOUSE_SYSTEMS.get(house_system, ("", ""))[0],
            "house_system_ja": HOUSE_SYSTEMS.get(house_system, ("", house_system))[1],
            "triplicity": triplicity,
            "terms": DEFAULT_TERMS,
            "terms_audit": TERMS_AUDIT,
            "faces": "chaldean",
            "node_type": "mean",
            "sources": TABLE_SOURCES,
        },
    }


# ==============================================================================
# テキストレポート生成
# ==============================================================================

_DIGNITY_MARK = [
    ("domicile", "支"), ("exaltation", "高"), ("triplicity", "三"),
    ("term", "限"), ("face", "面"),
]
_DEBILITY_MARK = [("detriment", "損"), ("fall", "堕"), ("peregrine", "遍")]


def dignity_marks(ed):
    """本質的品位を短い記号列にする（支高三限面／損堕遍）"""
    marks = [m for k, m in _DIGNITY_MARK if k in ed["labels"]]
    marks += [m for k, m in _DEBILITY_MARK if k in ed["debilities"]]
    if ed.get("peregrine") and "peregrine" not in ed["debilities"]:
        marks.append("(遍)")   # デトリメント／フォールと重複のため得点なし
    if ed.get("peregrine_cancelled_by"):
        marks.append("(遍解除)")
    return "".join(marks) if marks else "－"


def _sign_pad(text, width):
    """全角を2文字幅として概算パディング（異体字セレクタは幅0）"""
    w = 0
    for c in text:
        cp = ord(c)
        if 0xFE00 <= cp <= 0xFE0F:
            continue
        w += 2 if cp > 0x2E80 else 1
    return text + " " * max(0, width - w)


def generate_classical_text(chart, birth_info):
    """古典ネイタルチャートのテキストレポートを生成"""
    L = []
    meta = chart["meta"]
    sect = chart["sect"]

    L.append("=" * 74)
    L.append("  古典占星術ネイタルチャート（Christian Astrology 準拠）")
    L.append("=" * 74)
    L.append(f"出生日時 : {birth_info['year']}年{birth_info['month']}月{birth_info['day']}日 "
             f"{birth_info['hour']:02d}:{birth_info['minute']:02d} "
             f"(UTC{birth_info.get('tz_offset', 9.0):+.1f})")
    L.append(f"出生地   : 緯度 {birth_info['lat']:.4f}° / 経度 {birth_info['lon']:.4f}°")
    L.append(f"ハウス   : {meta['house_system_ja']}（{meta['house_system']}）"
             f" / トリプリシティ: {meta['triplicity']} / ノード: {meta['node_type']}")
    alt = sect.get("sun_altitude")
    alt_s = f"、太陽高度 {alt:+.2f}°" if alt is not None else ""
    border = "　※高度判定と食い違い（borderline）" if sect.get("borderline") else ""
    L.append(f"セクト   : {sect['label_ja']}"
             f"（ASC–DSC 地平線基準{alt_s}）"
             f"（月は{'増光' if sect['moon_increasing'] else '減光'}）{border}")

    ph = chart["planetary_hour"]
    if ph:
        L.append(f"曜日主星 : {ph['day_ruler_ja']}　"
                 f"時刻主星 : {ph['hour_ruler_ja']}"
                 f"（{'昼' if ph['is_daytime'] else '夜'}の第{ph['hour_index']}時）")
        L.append(f"日の出   : {ph['sunrise_str']}　日の入 : {ph['sunset_str']}")
    L.append("")

    # --- 天体位置 ---
    L.append("── 天体位置 ──")
    L.append("  " + _sign_pad("天体", 16) + _sign_pad("位置", 18)
             + _sign_pad("室", 6) + _sign_pad("品位", 12)
             + _sign_pad("本質", 6) + _sign_pad("偶発", 6) + "状態")
    L.append("  " + "-" * 74)
    for p in chart["planets"]:
        ed = p["essential"]
        states = []
        if p["retrograde"]:
            states.append("逆行")
        if p["solar_phase"]["state"] not in ("free", "sun"):
            states.append(p["solar_phase"]["state_ja"])
        if p["orientality"]:
            states.append(p["orientality_ja"])
        if p["hayz_ja"] != "—":
            states.append(p["hayz_ja"])
        L.append("  "
                 + _sign_pad(f"{p['symbol']}{p['name_ja']}", 16)
                 + _sign_pad(p["position_ja"], 18)
                 + _sign_pad(p["house_disp"], 6)
                 + _sign_pad(dignity_marks(ed), 12)
                 + _sign_pad(f"{ed['score']:+d}", 6)
                 + _sign_pad(f"{p['accidental']['score']:+d}", 6)
                 + " / ".join(states))
    for n in chart["nodes"]:
        L.append("  " + _sign_pad(f"{n['symbol']}{n['name_ja']}", 16)
                 + _sign_pad(n["position_ja"], 18)
                 + _sign_pad(str(n["house"]), 6))
    L.append("  " + _sign_pad("ASC", 16) + _sign_pad(chart["asc"]["position_ja"], 18)
             + _sign_pad("", 6)
             + f"主星 {PLANET_JA[chart['asc']['lord']]} / アルムテン "
             + f"{PLANET_JA.get(chart['asc']['almuten'], '—')}")
    L.append("  " + _sign_pad("MC", 16) + _sign_pad(chart["mc"]["position_ja"], 18))
    L.append("  " + _sign_pad("⊕フォーチュン", 16)
             + _sign_pad(chart["fortune"]["position_ja"], 18)
             + _sign_pad(str(chart["fortune"]["house"]), 6))
    L.append("  " + _sign_pad("スピリット", 16)
             + _sign_pad(chart["spirit"]["position_ja"], 18)
             + _sign_pad(str(chart["spirit"]["house"]), 6))
    L.append("  ※ 室の * 印はカスプ手前5°以内（次室の影響下）")
    L.append("")

    # --- 本質的品位表 ---
    L.append(f"── 本質的品位（ターム: エジプト式／トリプリシティ: {meta['triplicity']}）──")
    L.append("  " + _sign_pad("天体", 14) + _sign_pad("支配", 8) + _sign_pad("高揚", 8)
             + _sign_pad("三分", 8) + _sign_pad("限界", 8) + _sign_pad("面", 8) + "得点")
    L.append("  " + "-" * 62)
    for p in chart["planets"]:
        r = p["essential"]["rulers"]
        def _mk(key):
            owner = r.get(key)
            if owner is None:
                return "—"
            mark = "◎" if owner == p["name_en"] else " "
            return f"{PLANET_JA[owner]}{mark}"
        L.append("  " + _sign_pad(f"{p['symbol']}{p['name_ja']}", 14)
                 + _sign_pad(_mk("domicile"), 8) + _sign_pad(_mk("exaltation"), 8)
                 + _sign_pad(_mk("triplicity"), 8) + _sign_pad(_mk("term"), 8)
                 + _sign_pad(_mk("face"), 8)
                 + f"{p['essential']['score']:+d}")
    L.append("  ※ ◎＝その惑星自身が支配する（本質的品位を得ている）")
    L.append("  ※ 三分＝セクト主星（+3 はこの星のみ）。(遍)＝ペレグリンだが損／堕と重複のため")
    L.append("     得点なし。(遍解除)＝サイン／高揚のミューチュアル・レセプションで解除")
    diffs = [p for p in chart["planets"] if p["essential"]["term_audit"]["differs"]]
    if diffs:
        L.append("  監査（プトレマイオス式ターム・得点に不使用）: " + "、".join(
            f"{p['name_ja']} {PLANET_JA[p['essential']['rulers']['term']]}→"
            f"{PLANET_JA[p['essential']['term_audit']['ruler']]}" for p in diffs))
    L.append("")

    # --- 偶発的品位の内訳 ---
    L.append("── 偶発的品位の内訳 ──")
    for p in chart["planets"]:
        detail = "、".join(f"{lab}{pt:+d}" for _, lab, pt in p["accidental"]["items"])
        L.append(f"  {p['symbol']}{p['name_ja']}（計 {p['accidental']['score']:+d}）: {detail}")
    L.append("")

    # --- ハウスと主星 ---
    L.append(f"── ハウスカスプと主星（{meta['house_system_ja']}）──")
    for h, hr in zip(chart["houses"], chart["house_rulers"]):
        dign = dignity_marks({"labels": hr["lord_dignity"], "debilities": []})
        extra = []
        if hr["lord_retrograde"]:
            extra.append("逆行")
        if hr["lord_solar_phase"] not in ("光線から自由", "—"):
            extra.append(hr["lord_solar_phase"])
        extra_s = ("／" + "・".join(extra)) if extra else ""
        L.append(f"  第{h['number']:2d}ハウス {_sign_pad(h['position_ja'], 18)}"
                 f"主星 {hr['lord_symbol']}{hr['lord_ja']} → "
                 f"{hr['lord_position_ja']}・第{hr['lord_house']}ハウス"
                 f"（{dign} {hr['lord_score']:+d}）{extra_s}")
    L.append("")

    # --- アスペクト ---
    L.append("── アスペクト（プトレマイオス的5種／Lilly のオーブ）──")
    if not chart["aspects"]:
        L.append("  （オーブ内のアスペクトなし）")
    for a in chart["aspects"]:
        kind = "パーティル" if a["partile"] else "プラティック"
        rec = ""
        if a["mutual_reception"]:
            r1 = "・".join(DIGNITY_JA[x] for x in a["reception_1to2"])
            r2 = "・".join(DIGNITY_JA[x] for x in a["reception_2to1"])
            rec = f"　【相互レセプション: {r1} / {r2}】"
        elif a["reception_1to2"]:
            r1 = "・".join(DIGNITY_JA[x] for x in a["reception_1to2"])
            rec = f"　（{a['planet1_ja']}が{a['planet2_ja']}を受容: {r1}）"
        elif a["reception_2to1"]:
            r2 = "・".join(DIGNITY_JA[x] for x in a["reception_2to1"])
            rec = f"　（{a['planet2_ja']}が{a['planet1_ja']}を受容: {r2}）"
        L.append(f"  {_sign_pad(a['planet1_symbol'] + a['planet1_ja'], 14)}"
                 f"{a['aspect_symbol']} {_sign_pad(a['aspect_ja'], 6)}"
                 f"{_sign_pad(a['planet2_symbol'] + a['planet2_ja'], 14)}"
                 f" orb {a['orb']:5.2f}°  {_sign_pad(kind, 14)}"
                 f"{a['state_ja']}{rec}")
    L.append("")

    # --- アンティシャ ---
    L.append("── アンティシャ / 反アンティシャ ──")
    for p in chart["planets"]:
        L.append(f"  {p['symbol']}{p['name_ja']}: "
                 f"{p['antiscion']['position_ja']} ／ 反: {p['contra_antiscion']['position_ja']}")
    L.append("")

    # --- プレナタル・シジジー ---
    sz = chart["syzygy"]
    if sz:
        L.append("── プレナタル・シジジー（出生直前の朔望）──")
        L.append(f"  {sz['type_ja']}　{sz['datetime_str']}　"
                 f"{sz['point']['position_ja']}　"
                 f"アルムテン: {PLANET_JA.get(sz['almuten'], '—')}")
        L.append("")

    # --- アルムテン・フィギュリス ---
    alm = chart["almuten"]
    L.append("── アルムテン・フィギュリス（出生図の総主星の候補）──")
    L.append("  " + _sign_pad("天体", 14) + _sign_pad("ASC", 6) + _sign_pad("☉", 6)
             + _sign_pad("☽", 6) + _sign_pad("⊕", 6) + _sign_pad("シジー", 8)
             + _sign_pad("合計", 6) + "偶発")
    L.append("  " + "-" * 60)
    for name in alm["ranked"]:
        row = alm["table"][name]
        L.append("  " + _sign_pad(f"{PLANET_SYMBOLS[name]}{PLANET_JA[name]}", 14)
                 + _sign_pad(str(row["asc"]), 6) + _sign_pad(str(row["sun"]), 6)
                 + _sign_pad(str(row["moon"]), 6) + _sign_pad(str(row["fortune"]), 6)
                 + _sign_pad(str(row["syzygy"]), 8)
                 + _sign_pad(str(row["total"]), 6)
                 + f"{row['accidental']:+d}")
    if alm["almuten_tie"]:
        L.append("  → 共同アルムーテン: " + "・".join(PLANET_JA[n] for n in alm["almutens"])
                 + "（同点。両方を主星として読む）")
    else:
        L.append(f"  → アルムテン: {PLANET_JA.get(alm['almuten'], '—')}")
    L.append("    （Lilly の Lord of the Geniture は総合判断による。本表は材料）")
    L.append("")

    # --- セクトライトの三分主星 ---
    sl = chart["sect_light"]
    L.append(f"── セクトライト（{sl['light_ja']}・{sl['sign_ja']}／{sl['element_ja']}の三分主星）──")
    for lo in sl["lords"]:
        dign = dignity_marks({"labels": lo["dignity"], "debilities": []})
        L.append(f"  {lo['order']}主星 {PLANET_SYMBOLS[lo['planet']]}{lo['planet_ja']}: "
                 f"{lo['position_ja']}・第{lo['house']}ハウス（{dign} 合計{lo['score']:+d}）")
    L.append("")

    L.append("── 主要恒星の位置 ──")
    for name, sp in chart["stars"].items():
        L.append(f"  {_sign_pad(name, 10)}{sp['position_ja']}")
    L.append("  ※ sefstars.txt が無い環境では J2000 値＋歳差 50.29\"/年 の近似値")
    L.append("")

    L.append("─" * 37)
    L.append("凡例: 支＝ドミサイル 高＝イグザルテーション 三＝トリプリシティ")
    L.append("      限＝ターム 面＝フェイス 損＝デトリメント 堕＝フォール 遍＝ペレグリン")
    L.append(f"出所: 品位表（支配・高揚・三分・ターム・フェイス・損・堕）と得点は {METHOD_DOC}")
    L.append("      と照合済み。ターム＝エジプト式（§4.1）、プトレマイオス式は監査用（未照合）。")
    L.append("      オーブ・偶発的品位の表は Christian Astrology（リリー本文。CA Book I と未照合）。")
    L.append("      トリプリシティ＝ドロセウス式、ハウス＝レジオモンタナス、ノード＝平均値")
    L.append("      はプロジェクト慣行。アプライング判定・挟撃の近似・アルムテン合算法・")
    L.append("      恒星位置の歳差近似も実装上の補い。")

    return "\n".join(L)


# ==============================================================================
# JSON 出力
# ==============================================================================

SCHEMA_VERSION = "v1"

_JSON_NODE_NAME = {"Node": "NorthNode", "SouthNode": "SouthNode"}


def _json_point(pt):
    """感受点・天体の位置を JSON 用に整形（サイン名は英語）"""
    return {
        "longitude": round(pt["longitude"] % 360.0, 6),
        "sign": pt["sign"],
        "sign_index": sign_of(pt["longitude"]),
        "degrees": pt["degrees"],
        "minutes": pt["minutes"],
        "position": pt["position_str"],
    }


def _json_planet(p):
    """惑星1件を JSON 用に整形"""
    ed = p["essential"]
    acc = p["accidental"]
    codes = {it[0] for it in acc["items"]}
    sp = p["solar_phase"]

    d = _json_point(p)
    d.update({
        "name": p["name_en"],
        "speed": round(p["speed"], 6),
        "retrograde": p["retrograde"],
        "house": p["house_effective"],
        "house_raw": p["house"],
        "near_next_cusp": p["near_cusp"],
        "above_horizon": p["above_horizon"],
        "essential_dignity": {
            "dignities": ed["labels"],
            "debilities": ed["debilities"],
            "peregrine": ed["peregrine"],
            "peregrine_cancelled_by": ed["peregrine_cancelled_by"],
            "mutual_receptions": ed["mutual_receptions"],
            "score": ed["score"],
            "score_note": ed["score_note"],
            "rulers_of_position": ed["rulers"],
            "triplicity_rulers": ed["triplicity_rulers"],
            "term_audit": ed["term_audit"],
        },
        "accidental_dignity": {
            "score": acc["score"],
            "items": [{"code": c, "points": pt, "label_ja": ja}
                      for c, ja, pt in acc["items"]],
            "solar_phase": sp["state"],
            "distance_from_sun": sp["distance"],
            "cazimi": sp["state"] == "cazimi",
            "combust": sp["state"] == "combust",
            "under_beams": sp["state"] == "under_beams",
            "free_of_beams": sp["state"] == "free",
            "orientality": p["orientality"],
            "motion": "swift" if "swift" in codes else "slow",
        },
        "sect": {
            "planet_sect": p["sect"],
            "in_sect": p["in_sect"],
            "hayz": p["hayz"],
        },
        "total_score": p["total_score"],
        "antiscion": _json_point(p["antiscion"]),
        "contra_antiscion": _json_point(p["contra_antiscion"]),
    })
    return d


def _json_almuten(alm):
    """度数のアルムテン判定を JSON 用に整形"""
    return {
        "almuten": alm["almuten"],
        "almuten_tie": alm["almuten_tie"],
        "almuten_candidates": alm["candidates"],
        "almuten_tie_break": alm["tie_break"],
        "almuten_scores": alm["scores"],
    }


def to_json(chart):
    """
    チャートを JSON 直列化可能な dict に変換する。

    キーは英語のスネークケース、惑星名・サイン名も英語。
    現代天体（天王星・海王星・冥王星）は古典判断に用いないため
    "modern_reference" として別枠に置く。

    json.dump(to_json(chart), f, ensure_ascii=False, indent=2) で保存できる。
    """
    meta = chart["meta"]
    b = meta["birth"]
    ph = chart["planetary_hour"]
    sz = chart["syzygy"]

    by_name = {p["name_en"]: p for p in chart["planets"]}
    houses = []
    for h, hr in zip(chart["houses"], chart["house_rulers"]):
        lp = by_name[hr["lord"]]
        entry = _json_point(h)
        entry.update({
            "house": h["number"],
            "lord": hr["lord"],
            "lord_placement": {
                "sign": lp["sign"],
                "position": lp["position_str"],
                "house": lp["house_effective"],
                "dignities": lp["essential"]["labels"],
                "debilities": lp["essential"]["debilities"],
                "essential_score": lp["essential"]["score"],
                "accidental_score": lp["accidental"]["score"],
                "retrograde": lp["retrograde"],
                "solar_phase": lp["solar_phase"]["state"],
            },
        })
        houses.append(entry)

    return {
        "schema_version": SCHEMA_VERSION,
        "generator": "natal_classical.py",
        "birth_data": {
            "year": b["year"], "month": b["month"], "day": b["day"],
            "hour": b["hour"], "minute": b["minute"],
            "tz_offset": b["tz_offset"],
            "latitude": b["latitude"], "longitude": b["longitude"],
            "julian_day_ut": round(meta["jd"], 8),
        },
        "tables_used": {
            "terms": meta["terms"],
            "terms_audit": meta["terms_audit"],
            "triplicity": meta["triplicity"],
            "faces": meta["faces"],
            "house_system": {
                "code": meta["house_system"],
                "name": meta["house_system_name"],
            },
            "node": meta["node_type"],
            "sources": meta["sources"],
        },
        "sect": {
            "method": chart["sect"]["method"],
            "is_day": chart["sect"]["is_day"],
            "chart_sect": "diurnal" if chart["sect"]["is_day"] else "nocturnal",
            "sun_altitude": (None if chart["sect"]["sun_altitude"] is None
                             else round(chart["sect"]["sun_altitude"], 4)),
            "altitude_is_day": chart["sect"]["altitude_is_day"],
            "borderline": chart["sect"]["borderline"],
            "moon_increasing_light": chart["sect"]["moon_increasing"],
            "sect_light": {
                "light": chart["sect_light"]["light"],
                "triplicity_lords": [
                    {"order": lo["order"], "planet": lo["planet"],
                     "house": lo["house"], "dignities": lo["dignity"],
                     "score": lo["score"]}
                    for lo in chart["sect_light"]["lords"]
                ],
            },
        },
        "planetary_day_hour": ({
            "day_ruler": ph["day_ruler"],
            "hour_ruler": ph["hour_ruler"],
            "hour_index": ph["hour_index"],
            "is_daytime": ph["is_daytime"],
            "sunrise": ph["sunrise_str"],
            "sunset": ph["sunset_str"],
        } if ph else None),
        "angles": {
            "ascendant": dict(_json_point(chart["asc"]),
                              lord=chart["asc"]["lord"],
                              **_json_almuten(chart["asc"]["almuten_detail"])),
            "midheaven": _json_point(chart["mc"]),
        },
        "planets": [_json_planet(p) for p in chart["planets"]],
        "nodes": {
            "used": meta["node_type"],
            "mean": [dict(_json_point(n), name=_JSON_NODE_NAME[n["name_en"]],
                          house=n["house_effective"], retrograde=n["retrograde"])
                     for n in chart["nodes"]],
            "true": [dict(_json_point(n), name=_JSON_NODE_NAME[n["name_en"]],
                          house=n["house_effective"], retrograde=n["retrograde"])
                     for n in chart["nodes_true"]],
        },
        "lots": {
            "fortune": dict(_json_point(chart["fortune"]),
                            house=chart["fortune"]["house"],
                            lord=chart["fortune"]["lord"]),
            "spirit": dict(_json_point(chart["spirit"]),
                           house=chart["spirit"]["house"],
                           lord=chart["spirit"]["lord"]),
        },
        "prenatal_syzygy": ({
            "type": sz["type"],
            "datetime_local": sz["datetime_str"],
            **_json_almuten(sz["almuten_detail"]),
            **_json_point(sz["point"]),
        } if sz else None),
        "houses": houses,
        "aspects": [{
            "from": a["planet1"],
            "to": a["planet2"],
            "aspect": a["aspect"],
            "orb": a["orb"],
            "max_orb": a["max_orb"],
            "partile": a["partile"],
            "condition": a["state"],
            "direction": a["direction"],
            "reception_from_to": a["reception_1to2"],
            "reception_to_from": a["reception_2to1"],
            "mutual_reception": a["mutual_reception"],
        } for a in chart["aspects"]],
        "almuten_figuris": {
            "almutens": chart["almuten"]["almutens"],
            "almuten": chart["almuten"]["almuten"],
            "almuten_tie": chart["almuten"]["almuten_tie"],
            "ranking": chart["almuten"]["ranked"],
            "scores": {
                name: {
                    "ascendant": row["asc"], "sun": row["sun"],
                    "moon": row["moon"], "fortune": row["fortune"],
                    "syzygy": row["syzygy"], "total": row["total"],
                    "accidental": row["accidental"],
                    "house": row["house"],
                }
                for name, row in chart["almuten"]["table"].items()
            },
        },
        "fixed_stars": {name: _json_point(pt)
                        for name, pt in chart["stars"].items()},
        "modern_reference": {
            "note": "古典判断には用いない参考値 / not used in classical judgment",
            "planets": [dict(_json_point(m), name=m["name_en"],
                             speed=round(m["speed"], 6),
                             retrograde=m["retrograde"],
                             house=m["house_effective"])
                        for m in chart["modern_reference"]],
        },
    }


# ==============================================================================
# CLI
# ==============================================================================

def main():
    """python3 natal_classical.py 年 月 日 時 分 [緯度 経度] [ハウス記号] [--json]"""
    import sys
    import json as _json

    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv[1:]
    if len(args) < 5:
        print(main.__doc__.strip())
        print("例: python3 natal_classical.py 1985 7 21 14 30 35.6895 139.6917 R")
        print("    python3 natal_classical.py 1985 7 21 14 30 --json > chart.json")
        return

    y, mo, d, h, mi = (int(a) for a in args[:5])
    lat = float(args[5]) if len(args) > 5 else ac.TOKYO_LAT
    lon = float(args[6]) if len(args) > 6 else ac.TOKYO_LON
    hsys = args[7] if len(args) > 7 else "R"

    chart = calculate_classical_chart(y, mo, d, h, mi, lat, lon, house_system=hsys)
    if as_json:
        print(_json.dumps(to_json(chart), ensure_ascii=False, indent=2))
        return

    birth_info = {"year": y, "month": mo, "day": d, "hour": h, "minute": mi,
                  "lat": lat, "lon": lon, "tz_offset": 9.0}
    print(generate_classical_text(chart, birth_info))


if __name__ == "__main__":
    main()
