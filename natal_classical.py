"""
古典占星術ネイタルチャート計算モジュール
Classical (Traditional) Natal Chart Calculator

William Lilly "Christian Astrology" の体系に基づき、出生図の
本質的品位（Essential Dignities）・偶発的品位（Accidental Dignities）・
セクト・アラビックパーツ・アルムテンなどを算出する。

natal.py（モダン）との違い:
  - 天体は伝統的7惑星（♄♃♂☉♀☿☽）＋ドラゴンヘッド／テイルのみ
  - ノードは Mean Node（古典の慣行）
  - ハウスはレギオモンタヌス（Lilly 準拠）を既定とし、
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
# Lilly の表は昼／夜の2主星のみ（水は昼夜とも火星）＝ リリー本文
TRIPLICITY_LILLY = {
    "fire":  ("Sun", "Jupiter", None),
    "earth": ("Venus", "Moon", None),
    "air":   ("Saturn", "Mercury", None),
    "water": ("Mars", "Mars", None),
}
# ドロセウス式（参加星を含む）＝ プロジェクト慣行（オプション）
TRIPLICITY_DOROTHEAN = {
    "fire":  ("Sun", "Jupiter", "Saturn"),
    "earth": ("Venus", "Moon", "Mars"),
    "air":   ("Saturn", "Mercury", "Jupiter"),
    "water": ("Venus", "Mars", "Moon"),
}

# エジプシャン・ターム（Lilly の表と同一）＝ リリー本文
# 各サイン [(上限度数, 主星), ...]
TERMS_EGYPTIAN = [
    [(6, "Jupiter"), (14, "Venus"), (21, "Mercury"), (26, "Mars"), (30, "Saturn")],      # Ari
    [(8, "Venus"), (15, "Mercury"), (22, "Jupiter"), (26, "Saturn"), (30, "Mars")],      # Tau
    [(7, "Mercury"), (14, "Jupiter"), (21, "Venus"), (25, "Mars"), (30, "Saturn")],      # Gem
    [(6, "Mars"), (13, "Jupiter"), (20, "Mercury"), (27, "Venus"), (30, "Saturn")],      # Can
    [(6, "Jupiter"), (13, "Venus"), (19, "Saturn"), (25, "Mercury"), (30, "Mars")],      # Leo
    [(7, "Mercury"), (17, "Venus"), (21, "Jupiter"), (28, "Mars"), (30, "Saturn")],      # Vir
    [(6, "Saturn"), (14, "Mercury"), (21, "Jupiter"), (28, "Venus"), (30, "Mars")],      # Lib
    [(7, "Mars"), (11, "Venus"), (19, "Mercury"), (24, "Jupiter"), (30, "Saturn")],      # Sco
    [(12, "Jupiter"), (17, "Venus"), (21, "Mercury"), (26, "Saturn"), (30, "Mars")],     # Sag
    [(7, "Mercury"), (14, "Jupiter"), (22, "Venus"), (26, "Saturn"), (30, "Mars")],      # Cap
    [(7, "Mercury"), (13, "Venus"), (20, "Jupiter"), (25, "Mars"), (30, "Saturn")],      # Aqu
    [(12, "Venus"), (16, "Jupiter"), (19, "Mercury"), (28, "Mars"), (30, "Saturn")],     # Pis
]

# フェイス（デカン）＝ カルデア順の循環 ＝ リリー本文
CHALDEAN_ORDER = ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"]
FACES = [
    [CHALDEAN_ORDER[(si * 3 + k) % 7] for k in range(3)]
    for si in range(12)
]

# 品位の得点 ＝ リリー本文
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

def term_ruler(lon):
    """タームの主星を返す ＝ リリー本文（エジプシャン・ターム）"""
    si = sign_of(lon)
    d = deg_in_sign(lon)
    for limit, ruler in TERMS_EGYPTIAN[si]:
        if d < limit:
            return ruler
    return TERMS_EGYPTIAN[si][-1][1]


def face_ruler(lon):
    """フェイス（デカン）の主星を返す ＝ リリー本文（カルデア順）"""
    si = sign_of(lon)
    return FACES[si][int(deg_in_sign(lon) // 10)]


def triplicity_rulers(si, table=None):
    """サインのトリプリシティ主星 (昼, 夜, 参加) を返す"""
    table = table or TRIPLICITY_LILLY
    return table[element_of(si)]


def essential_dignity(lon, planet, is_day, trip_table=None):
    """
    ある黄経における惑星の本質的品位を判定する。

    Returns:
        dict: labels（成立した品位のリスト）, score, peregrine, rulers
    """
    trip_table = trip_table or TRIPLICITY_LILLY
    si = sign_of(lon)
    d = deg_in_sign(lon)

    day_l, night_l, part_l = triplicity_rulers(si, trip_table)
    trip_ruler = day_l if is_day else night_l

    labels = []
    if DOMICILE_BY_SIGN[si] == planet:
        labels.append("domicile")
    if si in EXALT_BY_SIGN and EXALT_BY_SIGN[si][0] == planet:
        labels.append("exaltation")
    if planet == trip_ruler or (part_l is not None and planet == part_l):
        labels.append("triplicity")
    if term_ruler(lon) == planet:
        labels.append("term")
    if face_ruler(lon) == planet:
        labels.append("face")

    debilities = []
    if DETRIMENT_BY_SIGN[si] == planet:
        debilities.append("detriment")
    if si in FALL_BY_SIGN and FALL_BY_SIGN[si][0] == planet:
        debilities.append("fall")

    # ペレグリン＝いかなる本質的品位も持たない（デトリメント／フォールとは別勘定）
    peregrine = (not labels) and (not debilities)
    if peregrine:
        debilities.append("peregrine")

    score = sum(DIGNITY_SCORE[l] for l in labels + debilities)

    return {
        "sign": si,
        "degree": d,
        "labels": labels,
        "debilities": debilities,
        "peregrine": peregrine,
        "score": score,
        "rulers": {
            "domicile": DOMICILE_BY_SIGN[si],
            "exaltation": EXALT_BY_SIGN.get(si, (None, None))[0],
            "triplicity": trip_ruler,
            "triplicity_participating": part_l,
            "term": term_ruler(lon),
            "face": face_ruler(lon),
        },
    }


def almuten_of_degree(lon, is_day, trip_table=None):
    """
    ある度数のアルムテン（最も品位の高い惑星）を求める。
    各惑星の本質的品位得点（プラスのみ）を合算する ＝ プロジェクト慣行
    """
    scores = {}
    for name in PLANET_NAMES:
        ed = essential_dignity(lon, name, is_day, trip_table)
        s = sum(DIGNITY_SCORE[l] for l in ed["labels"])
        if s:
            scores[name] = s
    if not scores:
        return None, {}
    winner = max(scores.items(), key=lambda kv: kv[1])[0]
    return winner, scores


# ==============================================================================
# セクト・太陽光線・オリエンタル／オクシデンタル
# ==============================================================================

def is_day_chart(sun_lon, asc_lon):
    """
    昼のチャートか（太陽が地平線上＝第7〜12ハウス）。
    ASC から黄道順に 0〜180° が地平線下（第1〜6ハウス）＝ プロジェクト慣行
    """
    return ((sun_lon - asc_lon) % 360.0) > 180.0


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
    """
    ed = essential_dignity(lon2, p1, is_day, trip_table)
    return ed["labels"]


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
        dict: score, items [(項目, 点数), ...]
    """
    name = planet["name_en"]
    lon = planet["longitude"]
    speed = planet["speed"]
    items = []

    # --- ハウス（カスプ手前5°は次のハウスとして扱う）---
    h = planet.get("house_effective", planet["house"])
    if h in HOUSE_SCORE:
        items.append((f"第{h}ハウス", HOUSE_SCORE[h]))

    # --- 順行・逆行 / 速度（☉☾を除く）---
    if name not in LUMINARIES:
        if planet["retrograde"]:
            items.append(("逆行", -5))
        else:
            items.append(("順行", 4))
    if abs(speed) > MEAN_MOTION[name]:
        items.append(("速行（平均運動以上）", 2))
    else:
        items.append(("遅行（平均運動未満）", -2))

    # --- オリエンタル／オクシデンタル ---
    orient = planet.get("orientality")
    if name in ("Saturn", "Jupiter", "Mars"):
        items.append(("オリエンタル", 2) if orient == "oriental"
                     else ("オクシデンタル", -2))
    elif name in ("Venus", "Mercury"):
        items.append(("オクシデンタル", 2) if orient == "occidental"
                     else ("オリエンタル", -2))
    elif name == "Moon":
        if ctx["moon_increasing"]:
            items.append(("増光", 2))
        else:
            items.append(("減光", -2))

    # --- 太陽光線 ---
    if name != "Sun":
        st = planet["solar_phase"]["state"]
        if st == "cazimi":
            items.append(("カジミ", 5))
        elif st == "combust":
            items.append(("コンバスト", -5))
        elif st == "under_beams":
            items.append(("サンビームス下", -4))
        else:
            items.append(("光線から自由", 5))

    # --- 他天体とのパーティル・アスペクト ---
    for other in ("Jupiter", "Venus", "Saturn", "Mars"):
        if other == name:
            continue
        o_lon = ctx["lons"][other]
        d = abs(_signed_sep(lon, o_lon))
        benefic = other in BENEFICS
        if d <= PARTILE_ORB:
            items.append((f"{PLANET_JA[other]}と合（パーティル）",
                          5 if benefic else -5))
        elif abs(d - 120.0) <= PARTILE_ORB and benefic:
            items.append((f"{PLANET_JA[other]}と三分（パーティル）", 4))
        elif abs(d - 60.0) <= PARTILE_ORB and benefic:
            items.append((f"{PLANET_JA[other]}と六分（パーティル）", 3))
        elif abs(d - 180.0) <= PARTILE_ORB and not benefic:
            items.append((f"{PLANET_JA[other]}と衝（パーティル）", -4))
        elif abs(d - 90.0) <= PARTILE_ORB and not benefic:
            items.append((f"{PLANET_JA[other]}と矩（パーティル）", -3))

    # --- ノードとの合 ---
    if abs(_signed_sep(lon, ctx["node_lon"])) <= PARTILE_ORB:
        items.append(("ドラゴンヘッドと合", 4))
    if abs(_signed_sep(lon, ctx["south_node_lon"])) <= PARTILE_ORB:
        items.append(("ドラゴンテイルと合", -4))

    # --- 挟撃（besieged）---
    if name not in ("Saturn", "Mars"):
        if _is_besieged(lon, ctx["lons"]["Saturn"], ctx["lons"]["Mars"]):
            items.append(("土星と火星に挙さまれる", -5))

    # --- 恒星 ---
    stars = ctx["stars"]
    if abs(_signed_sep(lon, stars["Regulus"])) <= PARTILE_ORB:
        items.append(("レグルスと合", 6))
    if abs(_signed_sep(lon, stars["Spica"])) <= PARTILE_ORB:
        items.append(("スピカと合", 5))
    if abs(_signed_sep(lon, stars["Algol"])) <= 5.0:
        items.append(("アルゴルと合（5°以内）", -5))

    return {"score": sum(pt for _, pt in items), "items": items}


# ==============================================================================
# アルムテン・フィギュリス（出生図の総主星）
# ==============================================================================

HYLEGIACAL_LABELS = {
    "asc": "ASC", "sun": "太陽", "moon": "月",
    "fortune": "フォーチュン", "syzygy": "シジー",
}


def almuten_figuris(places, is_day, accidental_scores=None, trip_table=None):
    """
    5つのハイレジカル・ポイント（ASC・☉・☾・フォーチュン・プレナタルシジジー）
    における本質的品位得点を合算し、出生図の総主星候補を求める。
    同点は偶発的品位の高い方を上位とする ＝ プロジェクト慣行
    （イブン・エズラ由来の慣行。Lilly は「Lord of the Geniture」を
      総合判断で定めるため、本表は判断材料として提示する）

    Parameters:
        places: {"asc": lon, "sun": lon, "moon": lon, "fortune": lon, "syzygy": lon}
    """
    table = {}
    for name in PLANET_NAMES:
        row = {}
        total = 0
        for key, lon in places.items():
            if lon is None:
                row[key] = 0
                continue
            ed = essential_dignity(lon, name, is_day, trip_table)
            s = sum(DIGNITY_SCORE[l] for l in ed["labels"])
            row[key] = s
            total += s
        row["total"] = total
        row["accidental"] = (accidental_scores or {}).get(name, 0)
        table[name] = row

    ranked = sorted(table.items(),
                    key=lambda kv: (kv[1]["total"], kv[1]["accidental"]),
                    reverse=True)
    return {"table": table, "ranked": [n for n, _ in ranked],
            "almuten": ranked[0][0] if ranked else None}


# ==============================================================================
# チャート計算
# ==============================================================================

HOUSE_SYSTEMS = {
    "R": ("Regiomontanus", "レギオモンタヌス"),
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
                              triplicity="lilly"):
    """
    古典占星術のネイタルチャートを計算する。

    Parameters:
        year, month, day, hour, minute: 出生日時（現地時刻）
        lat, lon: 出生地の緯度・経度
        tz_offset: UTCからの時差（既定 9.0 ＝ JST）
        house_system: "R"（レギオモンタヌス・既定）/"P"/"W"/"C"
        triplicity: "lilly"（既定）/"dorothean"

    Returns:
        dict: planets, houses, house_rulers, asc, mc, sect, parts, syzygy,
              aspects, antiscia, almuten, planetary_hour, meta
    """
    trip_table = TRIPLICITY_DOROTHEAN if triplicity == "dorothean" else TRIPLICITY_LILLY
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
    is_day = is_day_chart(sun_lon, asc_lon)
    increasing = moon_increasing(moon_lon, sun_lon)

    # 古典の慣行によりノードは Mean Node を用いる
    node_lon, node_speed = ac.get_body_lon_speed(jd, swe.MEAN_NODE)
    south_node_lon = (node_lon + 180.0) % 360.0

    stars = fixed_star_longitudes(jd)

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
        ed = essential_dignity(lon_deg, name_en, is_day, trip_table)
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

    # --- ノード ---
    nodes = []
    for nm, nlon in (("Node", node_lon), ("SouthNode", south_node_lon)):
        h_info = determine_house(nlon, cusp_lons)
        nodes.append(_format_point(nlon, {
            "name_en": nm,
            "name_ja": PLANET_JA[nm],
            "symbol": PLANET_SYMBOLS[nm],
            "house": h_info["house"],
            "house_str": h_info["house_str"],
            "retrograde": node_speed < 0,
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
    asc["almuten"], asc["almuten_scores"] = almuten_of_degree(asc_lon, is_day, trip_table)
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
        syzygy["almuten"], _ = almuten_of_degree(syzygy["longitude"], is_day, trip_table)

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
    almuten = almuten_figuris(places, is_day, acc_scores, trip_table)

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
    for label, nm in (("第1", d_l), ("第2", n_l), ("参加", p_l)):
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
        "sect": {
            "is_day": is_day,
            "label_ja": "昼のチャート" if is_day else "夜のチャート",
            "moon_increasing": increasing,
        },
        "stars": {k: _format_point(v) for k, v in stars.items()},
        "meta": {
            "jd": jd,
            "house_system": house_system,
            "house_system_ja": HOUSE_SYSTEMS.get(house_system, ("", house_system))[1],
            "triplicity": triplicity,
            "node_type": "Mean Node",
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
    L.append(f"セクト   : {sect['label_ja']}"
             f"（月は{'増光' if sect['moon_increasing'] else '減光'}）")

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
    L.append("── 本質的品位（Lilly の表）──")
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
    L.append("")

    # --- 偶発的品位の内訳 ---
    L.append("── 偶発的品位の内訳 ──")
    for p in chart["planets"]:
        detail = "、".join(f"{lab}{pt:+d}" for lab, pt in p["accidental"]["items"])
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
    L.append(f"  → アルムテン: {PLANET_JA[alm['almuten']]}"
             "（Lilly の Lord of the Geniture は総合判断による。本表は材料）")
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
    L.append("出所: 品位表・オーブ表・偶発的品位表は Christian Astrology（リリー本文）。")
    L.append("      アプライング判定・挟撃の近似・アルムテン合算法・恒星位置の歳差近似は")
    L.append("      プロジェクト慣行（実装上の補い）。")

    return "\n".join(L)


# ==============================================================================
# CLI
# ==============================================================================

def main():
    """python3 natal_classical.py 年 月 日 時 分 [緯度 経度] [ハウス記号]"""
    import sys
    args = sys.argv[1:]
    if len(args) < 5:
        print(main.__doc__.strip())
        print("例: python3 natal_classical.py 1985 7 21 14 30 35.6895 139.6917 R")
        return

    y, mo, d, h, mi = (int(a) for a in args[:5])
    lat = float(args[5]) if len(args) > 5 else ac.TOKYO_LAT
    lon = float(args[6]) if len(args) > 6 else ac.TOKYO_LON
    hsys = args[7] if len(args) > 7 else "R"

    chart = calculate_classical_chart(y, mo, d, h, mi, lat, lon, house_system=hsys)
    birth_info = {"year": y, "month": mo, "day": d, "hour": h, "minute": mi,
                  "lat": lat, "lon": lon, "tz_offset": 9.0}
    print(generate_classical_text(chart, birth_info))


if __name__ == "__main__":
    main()
