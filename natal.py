"""
ネイタルチャート計算 & トランジット分析モジュール
Natal Chart Calculator & Transit Analyzer

Swiss Ephemeris (pyswisseph) を使用して個人の出生図を計算し、
指定月のトランジット（経過天体）がネイタル天体に形成する
正確なアスペクト時刻を検出する。
"""

import swisseph as swe
import astro_calendar as ac


# ==============================================================================
# 定数
# ==============================================================================

# 天体記号
PLANET_SYMBOLS = {
    "Sun": "\u2609", "Moon": "\u263d", "Mercury": "\u263f",
    "Venus": "\u2640\ufe0e", "Mars": "\u2642\ufe0e", "Jupiter": "\u2643",
    "Saturn": "\u2644", "Uranus": "\u2645", "Neptune": "\u2646",
    "Pluto": "\u2647", "Node": "\u260a", "Lilith": "\u26b8",
    "Chiron": "\u26b7", "ASC": "", "MC": "",
}

# サイン（日本語名・記号）— ac.SIGN_FULL / ac.SIGN_ABBREV と同順
SIGN_JA = [
    "牡羊座", "牡牛座", "双子座", "蟹座", "獅子座", "乙女座",
    "天秤座", "蠍座", "射手座", "山羊座", "水瓶座", "魚座",
]
SIGN_SYMBOLS = [
    "\u2648\ufe0e", "\u2649\ufe0e", "\u264a\ufe0e", "\u264b\ufe0e", "\u264c\ufe0e", "\u264d\ufe0e",
    "\u264e\ufe0e", "\u264f\ufe0e", "\u2650\ufe0e", "\u2651\ufe0e", "\u2652\ufe0e", "\u2653\ufe0e",
]

# アスペクト記号
ASPECT_SYMBOLS = {
    "conjunction": "\u260c",
    "sextile": "\u26b9",
    "square": "\u25a1",
    "trine": "\u25b3",
    "opposition": "\u260d",
}

# ネイタルチャートの天体
NATAL_BODIES = [
    (swe.SUN,       "Sun",     "太陽"),
    (swe.MOON,      "Moon",    "月"),
    (swe.MERCURY,   "Mercury", "水星"),
    (swe.VENUS,     "Venus",   "金星"),
    (swe.MARS,      "Mars",    "火星"),
    (swe.JUPITER,   "Jupiter", "木星"),
    (swe.SATURN,    "Saturn",  "土星"),
    (swe.URANUS,    "Uranus",  "天王星"),
    (swe.NEPTUNE,   "Neptune", "海王星"),
    (swe.PLUTO,     "Pluto",   "冥王星"),
    (swe.TRUE_NODE, "Node",    "ノード"),   # ネイタルでは True Node が標準
    (swe.MEAN_APOG, "Lilith",  "リリス"),
    (swe.CHIRON,    "Chiron",  "キロン"),
]

# トランジット走査天体とステップ幅（日数）
# Moonは1日で全サインのネイタル天体にアスペクトするため除外
# （月の動きは既存のファイル1でカバー済み）
TRANSIT_BODIES = [
    (swe.SUN,       "Sun",     "太陽",    0.5),
    (swe.MERCURY,   "Mercury", "水星",    0.25),
    (swe.VENUS,     "Venus",   "金星",    0.5),
    (swe.MARS,      "Mars",    "火星",    0.5),
    (swe.JUPITER,   "Jupiter", "木星",    1.0),
    (swe.SATURN,    "Saturn",  "土星",    1.0),
    (swe.URANUS,    "Uranus",  "天王星",  1.0),
    (swe.NEPTUNE,   "Neptune", "海王星",  1.0),
    (swe.PLUTO,     "Pluto",   "冥王星",  1.0),
    (swe.TRUE_NODE, "Node",    "ノード",  1.0),  # トランジットも True Node
    (swe.CHIRON,    "Chiron",  "キロン",  1.0),
]

# ネイタルアスペクトのオーブ（度）
# Sun/Moon が関わる場合はより広いオーブを使用
NATAL_ORBS = {
    0.0:   {"default": 8.0, "luminary": 10.0},   # conjunction
    60.0:  {"default": 5.0, "luminary": 6.0},     # sextile
    90.0:  {"default": 6.0, "luminary": 7.0},     # square
    120.0: {"default": 7.0, "luminary": 8.0},     # trine
    180.0: {"default": 8.0, "luminary": 10.0},    # opposition
}

LUMINARIES = {"Sun", "Moon"}

# トランジットの重要度
# 3=★★★ (トランスサタニアン), 2=★★ (木星/土星), 1=★ (内惑星等)
TRANSIT_SIGNIFICANCE = {
    "Pluto":   3,
    "Neptune": 3,
    "Uranus":  3,
    "Saturn":  2,
    "Jupiter": 2,
    "Mars":    1,
    "Venus":   1,
    "Mercury": 1,
    "Sun":     1,
    "Node":    1,
    "Chiron":  1,
}

# ハードアスペクト（重要度ボーナス）
HARD_ASPECTS = {0.0, 90.0, 180.0}


# ==============================================================================
# ハウス判定
# ==============================================================================

# カスプ手前の閾値（度）— この範囲内なら「次のハウスの影響下」と見なす
CUSP_THRESHOLD = 5.0


def _angular_distance(lon_from, lon_to):
    """lon_from → lon_to への正方向の角距離（0〜360）"""
    return (lon_to - lon_from) % 360.0


def determine_house(planet_lon, cusp_lons):
    """
    天体がどのハウスに在室しているかを判定する（Placidus）。

    Parameters:
        planet_lon: 天体の黄経（度、0〜360）
        cusp_lons:  12個のハウスカスプ黄経のリスト（index 0 = 第1ハウス）

    Returns:
        dict: house, near_cusp, dist_to_next, house_str
    """
    for i in range(12):
        cusp_start = cusp_lons[i]
        cusp_end = cusp_lons[(i + 1) % 12]
        house_num = i + 1
        next_house = (i + 1) % 12 + 1

        # このハウスの全幅
        house_span = _angular_distance(cusp_start, cusp_end)
        # カスプ開始から天体までの距離
        dist_from_start = _angular_distance(cusp_start, planet_lon)

        if dist_from_start < house_span:
            # この天体は第 house_num ハウスに在室
            dist_to_next = house_span - dist_from_start
            near_cusp = dist_to_next < CUSP_THRESHOLD

            if near_cusp:
                house_str = f"{next_house}（{house_num}の終わり）"
            else:
                house_str = str(house_num)

            return {
                "house": house_num,
                "near_cusp": near_cusp,
                "dist_to_next": round(dist_to_next, 2),
                "house_str": house_str,
            }

    # フォールバック（通常到達しない）
    return {"house": 1, "near_cusp": False, "dist_to_next": 0, "house_str": "1"}


# ==============================================================================
# ネイタルチャート計算
# ==============================================================================

def calculate_natal_chart(year, month, day, hour, minute, lat, lon, tz_offset=9.0):
    """
    ネイタルチャートを計算する。

    Parameters:
        year, month, day: 出生日（現地時刻）
        hour, minute: 出生時刻（現地時刻）
        lat, lon: 出生地の緯度・経度
        tz_offset: UTCからの時差（時間）。デフォルト9.0（JST）

    Returns:
        dict: planets, houses, asc, mc, aspects
    """
    jd = ac.datetime_local_to_jd(year, month, day, hour, minute, tz_offset)

    # --- 天体位置 ---
    planets = []
    for body_id, name_en, name_ja in NATAL_BODIES:
        lon_deg, speed = ac.get_body_lon_speed(jd, body_id)
        si, deg, mn = ac.lon_to_sign_deg_min(lon_deg)
        planets.append({
            "name_en": name_en,
            "name_ja": name_ja,
            "symbol": PLANET_SYMBOLS.get(name_en, ""),
            "longitude": lon_deg,
            "sign": ac.SIGN_FULL[si],
            "sign_abbrev": ac.SIGN_ABBREV[si],
            "sign_ja": SIGN_JA[si],
            "sign_symbol": SIGN_SYMBOLS[si],
            "degrees": deg,
            "minutes": mn,
            "retrograde": speed < 0,
            "position_str": f"{ac.SIGN_ABBREV[si]} {deg:02d}\u00b0{mn:02d}'",
            "position_ja": f"{SIGN_JA[si]}{SIGN_SYMBOLS[si]} {deg:02d}\u00b0{mn:02d}'",
        })

    # --- ハウスカスプ（Placidus） ---
    cusps, ascmc = swe.houses(jd, lat, lon, b'P')

    houses = []
    for i, cusp_lon in enumerate(cusps):
        si, deg, mn = ac.lon_to_sign_deg_min(cusp_lon)
        houses.append({
            "number": i + 1,
            "longitude": cusp_lon,
            "sign": ac.SIGN_FULL[si],
            "sign_abbrev": ac.SIGN_ABBREV[si],
            "sign_ja": SIGN_JA[si],
            "sign_symbol": SIGN_SYMBOLS[si],
            "degrees": deg,
            "minutes": mn,
            "position_str": f"{ac.SIGN_ABBREV[si]} {deg:02d}\u00b0{mn:02d}'",
            "position_ja": f"{SIGN_JA[si]}{SIGN_SYMBOLS[si]} {deg:02d}\u00b0{mn:02d}'",
        })

    # --- 各天体のハウス判定 ---
    cusp_lons = [c["longitude"] for c in houses]
    for p in planets:
        h_info = determine_house(p["longitude"], cusp_lons)
        p["house"] = h_info["house"]
        p["house_str"] = h_info["house_str"]
        p["near_cusp"] = h_info["near_cusp"]

    # --- ASC / MC ---
    def _format_point(lon_deg):
        si, deg, mn = ac.lon_to_sign_deg_min(lon_deg)
        return {
            "longitude": lon_deg,
            "sign": ac.SIGN_FULL[si],
            "sign_abbrev": ac.SIGN_ABBREV[si],
            "sign_ja": SIGN_JA[si],
            "sign_symbol": SIGN_SYMBOLS[si],
            "degrees": deg,
            "minutes": mn,
            "position_str": f"{ac.SIGN_ABBREV[si]} {deg:02d}\u00b0{mn:02d}'",
            "position_ja": f"{SIGN_JA[si]}{SIGN_SYMBOLS[si]} {deg:02d}\u00b0{mn:02d}'",
        }

    asc = _format_point(ascmc[0])
    mc = _format_point(ascmc[1])

    # --- ネイタルアスペクト ---
    aspects = find_natal_aspects(planets)

    return {
        "planets": planets,
        "houses": houses,
        "asc": asc,
        "mc": mc,
        "aspects": aspects,
    }


def find_natal_aspects(planets):
    """
    ネイタル天体間のメジャーアスペクトを検出。
    オーブ内に入っているアスペクトをすべて返す。
    """
    aspects = []

    for i in range(len(planets)):
        for j in range(i + 1, len(planets)):
            p1 = planets[i]
            p2 = planets[j]
            lon1 = p1["longitude"]
            lon2 = p2["longitude"]

            diff = abs(((lon1 - lon2 + 180.0) % 360.0) - 180.0)

            for asp_angle, asp_full, asp_abbrev in ac.ASPECTS:
                is_luminary = (
                    p1["name_en"] in LUMINARIES or
                    p2["name_en"] in LUMINARIES
                )
                orb_info = NATAL_ORBS[asp_angle]
                max_orb = orb_info["luminary"] if is_luminary else orb_info["default"]

                deviation = abs(diff - asp_angle)
                if deviation <= max_orb:
                    aspects.append({
                        "planet1": p1["name_en"],
                        "planet1_ja": p1["name_ja"],
                        "planet1_symbol": p1.get("symbol", ""),
                        "planet2": p2["name_en"],
                        "planet2_ja": p2["name_ja"],
                        "planet2_symbol": p2.get("symbol", ""),
                        "aspect": asp_full,
                        "aspect_abbrev": asp_abbrev,
                        "aspect_symbol": ASPECT_SYMBOLS.get(asp_full, ""),
                        "orb": round(deviation, 2),
                    })

    # オーブが小さい（タイトな）順にソート
    aspects.sort(key=lambda x: x["orb"])
    return aspects


# ==============================================================================
# トランジット分析
# ==============================================================================

def find_transits_to_natal(natal_chart, year, month):
    """
    指定月のトランジット天体がネイタル天体・感受点に形成する
    正確なアスペクト時刻を検出する。

    Parameters:
        natal_chart: calculate_natal_chart() の返り値
        year, month: トランジットを走査する年月

    Returns:
        list of dict: 時系列順のトランジットイベント
    """
    jd_start, jd_end = ac.month_jd_range(year, month)

    # ネイタルターゲット: 13天体 + ASC + MC
    natal_targets = []
    for p in natal_chart["planets"]:
        natal_targets.append({
            "name_en": p["name_en"],
            "name_ja": p["name_ja"],
            "longitude": p["longitude"],
            "position_str": p["position_str"],
        })
    natal_targets.append({
        "name_en": "ASC",
        "name_ja": "ASC",
        "longitude": natal_chart["asc"]["longitude"],
        "position_str": natal_chart["asc"]["position_str"],
    })
    natal_targets.append({
        "name_en": "MC",
        "name_ja": "MC",
        "longitude": natal_chart["mc"]["longitude"],
        "position_str": natal_chart["mc"]["position_str"],
    })

    results = []

    for t_body_id, t_name, t_name_ja, step in TRANSIT_BODIES:
        for nt in natal_targets:
            # 同じ天体同士のトランジットはスキップ
            # （例: t.Sun con n.Sun = ソーラーリターンで別途扱う）
            if t_name == nt["name_en"] and t_name not in ("Node", "Chiron"):
                continue

            natal_lon = nt["longitude"]

            for asp_angle, asp_full, asp_abbrev in ac.ASPECTS:
                jd = jd_start
                prev_val = None

                while jd < jd_end:
                    jd_next = min(jd + step, jd_end)
                    t_lon = ac.get_body_lon(jd_next, t_body_id)
                    curr_val = ac.aspect_eval(t_lon, natal_lon, asp_angle)

                    if prev_val is not None and ac.is_real_crossing(prev_val, curr_val):
                        jd_exact = _bisect_transit(
                            t_body_id, natal_lon, asp_angle, jd, jd_next
                        )
                        if jd_exact is not None and jd_start <= jd_exact <= jd_end:
                            t_lon_exact = ac.get_body_lon(jd_exact, t_body_id)
                            dt = ac.jd_to_datetime_jst(jd_exact)
                            t_si, t_deg, t_mn = ac.lon_to_sign_deg_min(t_lon_exact)

                            # 重要度
                            sig = TRANSIT_SIGNIFICANCE.get(t_name, 1)
                            if asp_angle in HARD_ASPECTS and sig >= 2:
                                sig = min(sig + 1, 3)

                            results.append({
                                "jd": jd_exact,
                                "date_str": ac.format_date_file2(dt),
                                "month": dt.month,
                                "day": dt.day,
                                "hour": dt.hour,
                                "minute": dt.minute,
                                "transit_planet": t_name,
                                "transit_planet_ja": t_name_ja,
                                "transit_symbol": PLANET_SYMBOLS.get(t_name, ""),
                                "aspect": asp_full,
                                "aspect_abbrev": asp_abbrev,
                                "aspect_symbol": ASPECT_SYMBOLS.get(asp_full, ""),
                                "natal_planet": nt["name_en"],
                                "natal_planet_ja": nt["name_ja"],
                                "natal_symbol": PLANET_SYMBOLS.get(nt["name_en"], ""),
                                "transit_position": ac.format_position_full(t_lon_exact),
                                "transit_position_ja": f"{SIGN_JA[t_si]}{SIGN_SYMBOLS[t_si]} {t_deg:02d}\u00b0{t_mn:02d}'",
                                "natal_position": nt["position_str"],
                                "significance": sig,
                            })

                    prev_val = curr_val
                    jd = jd_next

    results.sort(key=lambda x: x["jd"])
    return results


def _bisect_transit(t_body_id, natal_lon, asp_angle, jd_a, jd_b):
    """トランジット天体がネイタル位置と正確なアスペクトを形成する時刻を二分法で特定"""
    def f(jd):
        t_lon = ac.get_body_lon(jd, t_body_id)
        return ac.aspect_eval(t_lon, natal_lon, asp_angle)
    return ac.bisect_find_zero(f, jd_a, jd_b)


# ==============================================================================
# テキストレポート生成
# ==============================================================================

def generate_natal_text(natal_chart, birth_info):
    """ネイタルチャートのテキスト表現を生成"""
    lines = []
    lines.append(f"=== ネイタルチャート ===")
    lines.append(f"出生日時: {birth_info['year']}年{birth_info['month']}月"
                 f"{birth_info['day']}日 {birth_info['hour']:02d}:{birth_info['minute']:02d} JST")
    lines.append(f"出生地:   北緯{birth_info['lat']:.4f}° 東経{birth_info['lon']:.4f}°")
    lines.append("")

    # 天体位置
    lines.append("--- 天体位置 ---")
    for p in natal_chart["planets"]:
        retro = " R" if p["retrograde"] else "  "
        lines.append(f"  {p['name_en']:8s} {p['name_ja']:4s}  {p['position_str']}{retro}")
    lines.append(f"  {'ASC':8s} {'ASC':4s}  {natal_chart['asc']['position_str']}")
    lines.append(f"  {'MC':8s} {'MC':4s}  {natal_chart['mc']['position_str']}")
    lines.append("")

    # ハウスカスプ
    lines.append("--- ハウスカスプ (Placidus) ---")
    for h in natal_chart["houses"]:
        lines.append(f"  House {h['number']:2d}:  {h['position_str']}")
    lines.append("")

    # ネイタルアスペクト
    lines.append("--- ネイタルアスペクト ---")
    for a in natal_chart["aspects"]:
        lines.append(
            f"  {a['planet1']:8s} {a['aspect_abbrev']:3s} {a['planet2']:8s}"
            f"  (orb {a['orb']:.1f}°)"
        )

    return "\n".join(lines)


def generate_transit_text(natal_chart, transits, year, month, birth_info):
    """月間トランジットレポートのテキスト表現を生成"""
    lines = []
    lines.append(f"=== {year}年{month}月のトランジット ===")
    lines.append(f"対象: {birth_info['year']}年{birth_info['month']}月"
                 f"{birth_info['day']}日 {birth_info['hour']:02d}:{birth_info['minute']:02d} JST 生まれ")
    lines.append("")

    if not transits:
        lines.append("  この月に正確なトランジットアスペクトはありません。")
        return "\n".join(lines)

    lines.append(f"{'日時':19s}  {'トランジット':10s} {'Asp':3s} {'ネイタル':10s}"
                 f"  {'トランジット位置':18s}  重要度")
    lines.append("-" * 90)

    for t in transits:
        stars = "\u2605" * t["significance"]
        lines.append(
            f"{t['date_str']}  "
            f"t.{t['transit_planet']:8s} {t['aspect_abbrev']:3s} "
            f"n.{t['natal_planet']:8s}  "
            f"{t['transit_position']:18s}  {stars}"
        )

    return "\n".join(lines)
