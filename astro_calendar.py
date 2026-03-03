#!/usr/bin/env python3
"""
占星術カレンダー自動生成ツール
Astrology Calendar Generator

毎月の占星術データ（月の動き＋VOC、天体アスペクト表）を
Swiss Ephemeris (Moshier) で自動計算して出力する。

使い方:
    python3 astro_calendar.py 2026 3

出力:
    moon_voc_2026_03.txt   - 月の動きとVoid of Course Moon
    planet_aspects_2026_03.txt - 各天体のアスペクト表
"""

import swisseph as swe
import datetime
import math
import sys
import os
import calendar

# ==============================================================================
# 定数・設定
# ==============================================================================

# エフェメリスパスの設定（Chiron等の小惑星に必要）
EPHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ephe")
if os.path.isdir(EPHE_DIR):
    swe.set_ephe_path(EPHE_DIR)

JST_OFFSET_HOURS = 9.0  # UTC+9

# 東京の座標
TOKYO_LON = 139.6917
TOKYO_LAT = 35.6895
TOKYO_ALT = 40.0

# 計算フラグ: Swiss Ephemerisファイル + 速度計算
# （Chiron等の小惑星にはSE filesが必要。主要惑星はファイルがなければ自動的にMoshierにフォールバック）
CALC_FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED

# 二分法の精度（日数単位、約8.6秒）
BISECT_TOLERANCE = 0.0001

# --- 天体定数 ---

# ファイル1用: 月がアスペクトを形成する対象天体
MOON_ASPECT_TARGETS = [
    (swe.SUN,     "Sun"),
    (swe.MERCURY, "Mercury"),
    (swe.VENUS,   "Venus"),
    (swe.MARS,    "Mars"),
    (swe.JUPITER, "Jupiter"),
    (swe.SATURN,  "Saturn"),
    (swe.URANUS,  "Uranus"),
    (swe.NEPTUNE, "Neptune"),
    (swe.PLUTO,   "Pluto"),
]

# ファイル2用: 天体間アスペクトの対象（Moonを除く）
PLANET_ASPECT_BODIES = [
    (swe.SUN,       "Sun"),
    (swe.MERCURY,   "Mercury"),
    (swe.VENUS,     "Venus"),
    (swe.MARS,      "Mars"),
    (swe.JUPITER,   "Jupiter"),
    (swe.SATURN,    "Saturn"),
    (swe.URANUS,    "Uranus"),
    (swe.NEPTUNE,   "Neptune"),
    (swe.PLUTO,     "Pluto"),
    (swe.MEAN_NODE, "Node"),  # 月間カレンダーは Mean Node（astro-seek準拠）
    (swe.MEAN_APOG, "Lilith"),
    (swe.CHIRON,    "Chiron"),
]

# イングレス検出対象（Sun〜Plutoのみ; Node/Lilith/Chironのイングレスは通常不要）
INGRESS_BODIES = [
    (swe.SUN,     "Sun"),
    (swe.MERCURY, "Mercury"),
    (swe.VENUS,   "Venus"),
    (swe.MARS,    "Mars"),
    (swe.JUPITER, "Jupiter"),
    (swe.SATURN,  "Saturn"),
    (swe.URANUS,  "Uranus"),
    (swe.NEPTUNE, "Neptune"),
    (swe.PLUTO,   "Pluto"),
]

# ステーション検出対象（逆行する天体のみ）
STATION_BODIES = [
    (swe.MERCURY, "Mercury"),
    (swe.VENUS,   "Venus"),
    (swe.MARS,    "Mars"),
    (swe.JUPITER, "Jupiter"),
    (swe.SATURN,  "Saturn"),
    (swe.URANUS,  "Uranus"),
    (swe.NEPTUNE, "Neptune"),
    (swe.PLUTO,   "Pluto"),
    (swe.CHIRON,  "Chiron"),
]

# --- メジャーアスペクト ---
ASPECTS = [
    (0.0,   "conjunction", "Con"),
    (60.0,  "sextile",     "Sex"),
    (90.0,  "square",      "Squ"),
    (120.0, "trine",       "Tri"),
    (180.0, "opposition",  "Opp"),
]

# --- 星座名 ---
SIGN_ABBREV = [
    "Ari", "Tau", "Gem", "Can", "Leo", "Vir",
    "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis",
]
SIGN_FULL = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# 月名の略称（strftimeの%bは環境依存なので明示的に定義）
MONTH_ABBREV = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


# ==============================================================================
# ユーティリティ関数
# ==============================================================================

def jd_to_datetime_jst(jd):
    """ユリウス日（UT）をJSTのdatetimeに変換"""
    year, month, day, hour_ut = swe.revjul(jd)
    hour_jst = hour_ut + JST_OFFSET_HOURS
    day_offset = 0
    if hour_jst >= 24.0:
        hour_jst -= 24.0
        day_offset = 1
    elif hour_jst < 0.0:
        hour_jst += 24.0
        day_offset = -1

    h = int(hour_jst)
    m = int((hour_jst - h) * 60)
    if m == 60:
        h += 1
        m = 0
        if h == 24:
            h = 0
            day_offset += 1

    dt = datetime.datetime(year, month, day, h, m)
    dt += datetime.timedelta(days=day_offset)
    return dt


def datetime_jst_to_jd(year, month, day, hour=0, minute=0):
    """JST日時をユリウス日（UT）に変換"""
    hour_ut = hour + minute / 60.0 - JST_OFFSET_HOURS
    d = day
    m = month
    y = year
    if hour_ut < 0:
        hour_ut += 24.0
        prev = datetime.date(y, m, d) - datetime.timedelta(days=1)
        y, m, d = prev.year, prev.month, prev.day
    elif hour_ut >= 24.0:
        hour_ut -= 24.0
        nxt = datetime.date(y, m, d) + datetime.timedelta(days=1)
        y, m, d = nxt.year, nxt.month, nxt.day
    return swe.julday(y, m, d, hour_ut)


def datetime_local_to_jd(year, month, day, hour=0, minute=0, tz_offset=9.0):
    """ローカル日時をユリウス日（UT）に変換。tz_offset=UTCからの時差（時間）"""
    hour_ut = hour + minute / 60.0 - tz_offset
    d = day
    m = month
    y = year
    if hour_ut < 0:
        hour_ut += 24.0
        prev = datetime.date(y, m, d) - datetime.timedelta(days=1)
        y, m, d = prev.year, prev.month, prev.day
    elif hour_ut >= 24.0:
        hour_ut -= 24.0
        nxt = datetime.date(y, m, d) + datetime.timedelta(days=1)
        y, m, d = nxt.year, nxt.month, nxt.day
    return swe.julday(y, m, d, hour_ut)


def month_jd_range(year, month):
    """指定月のJD範囲を返す（JST 0:00基準）"""
    jd_start = datetime_jst_to_jd(year, month, 1, 0, 0)
    if month == 12:
        jd_end = datetime_jst_to_jd(year + 1, 1, 1, 0, 0)
    else:
        jd_end = datetime_jst_to_jd(year, month + 1, 1, 0, 0)
    return jd_start, jd_end


def get_body_lon_speed(jd, body_id):
    """天体の経度と経度速度を返す"""
    xx, _ = swe.calc_ut(jd, body_id, CALC_FLAGS)
    return xx[0], xx[3]  # longitude, speed_in_longitude


def get_body_lon(jd, body_id):
    """天体の経度のみ返す"""
    xx, _ = swe.calc_ut(jd, body_id, CALC_FLAGS)
    return xx[0]


def lon_to_sign_deg_min(longitude):
    """経度を (sign_index, degrees, minutes) に変換"""
    longitude = longitude % 360.0
    sign_index = int(longitude / 30.0)
    degree_in_sign = longitude - sign_index * 30.0
    degrees = int(degree_in_sign)
    minutes = int((degree_in_sign - degrees) * 60)
    if minutes == 60:
        degrees += 1
        minutes = 0
        if degrees == 30:
            degrees = 0
            sign_index = (sign_index + 1) % 12
    return sign_index, degrees, minutes


def format_position_abbrev(longitude):
    """'Leo 27°45' 形式（ファイル1用）"""
    si, deg, mn = lon_to_sign_deg_min(longitude)
    return f"{SIGN_ABBREV[si]} {deg:02d}°{mn:02d}'"


def format_position_full(longitude):
    """'Virgo 12°51' 形式（ファイル2用）"""
    si, deg, mn = lon_to_sign_deg_min(longitude)
    return f"{SIGN_FULL[si]} {deg:02d}°{mn:02d}'"


def format_date_file1(dt, month):
    """'Mar 2, 17:35' 形式（ファイル1用）"""
    mon_abbr = MONTH_ABBREV[dt.month]
    return f"{mon_abbr} {dt.day}, {dt.hour:02d}:{dt.minute:02d}"


def format_date_file2(dt):
    """'2026-03-02 23:16' 形式（ファイル2用）"""
    return f"{dt.year}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"


# ==============================================================================
# コア計算エンジン
# ==============================================================================

def aspect_eval(lon1, lon2, aspect_angle):
    """
    アスペクト検出用の連続関数。ゼロ交差がアスペクト成立を示す。

    - conjunction (0°): 符号付き角度差を使用。合の時にゼロを横切る。
    - opposition (180°): 180°シフトした符号付き角度差を使用。
    - sextile/square/trine (60°/90°/120°): 無符号角度距離 - target を使用。
      ゼロ交差は正しいアスペクトでのみ発生。
    """
    if aspect_angle == 0.0:
        # 合: 符号付き角度差。0°でゼロを横切る。
        return ((lon1 - lon2 + 180.0) % 360.0) - 180.0
    elif aspect_angle == 180.0:
        # 衝: (lon1-lon2)%360 が180を横切る時にゼロ交差。
        return ((lon1 - lon2) % 360.0) - 180.0
    else:
        # 六分/矩/三分: 角度距離 - target
        d = abs(((lon1 - lon2 + 180.0) % 360.0) - 180.0)
        return d - aspect_angle


def is_real_crossing(prev_val, curr_val):
    """偽の符号変化（0/360度の折り返しジャンプ）を除外"""
    return prev_val * curr_val < 0 and abs(prev_val - curr_val) < 270.0


def bisect_find_zero(func, jd_a, jd_b, max_iter=50):
    """二分法で func(jd) = 0 となるjdを見つける"""
    fa = func(jd_a)
    fb = func(jd_b)
    if fa * fb > 0:
        return None

    for _ in range(max_iter):
        jd_mid = (jd_a + jd_b) / 2.0
        fm = func(jd_mid)
        if abs(jd_b - jd_a) < BISECT_TOLERANCE:
            return jd_mid
        if fa * fm <= 0:
            jd_b = jd_mid
            fb = fm
        else:
            jd_a = jd_mid
            fa = fm
    return (jd_a + jd_b) / 2.0


def find_exact_aspect_time(body1_id, body2_id, aspect_angle, jd_a, jd_b):
    """二分法で正確なアスペクト時刻を特定"""
    def f(jd):
        lon1 = get_body_lon(jd, body1_id)
        lon2 = get_body_lon(jd, body2_id)
        return aspect_eval(lon1, lon2, aspect_angle)
    return bisect_find_zero(f, jd_a, jd_b)


def bisect_body_longitude(jd_a, jd_b, body_id, target_lon):
    """天体が特定の経度（サイン境界）を通過する時刻を特定"""
    def f(jd):
        lon = get_body_lon(jd, body_id)
        diff = (lon - target_lon + 180.0) % 360.0 - 180.0
        return diff
    return bisect_find_zero(f, jd_a, jd_b)


def bisect_speed_zero(jd_a, jd_b, body_id):
    """天体の経度速度がゼロになる時刻を特定（ステーション）"""
    def f(jd):
        _, speed = get_body_lon_speed(jd, body_id)
        return speed
    return bisect_find_zero(f, jd_a, jd_b)


# ==============================================================================
# ファイル1: 月の動き＋Void of Course Moon
# ==============================================================================

def find_moon_sign_changes(jd_start, jd_end):
    """月のサイン移動を検出。(jd_exact, new_sign_index) のリストを返す"""
    STEP = 2.0 / 24.0  # 2時間
    results = []

    jd = jd_start
    prev_lon = get_body_lon(jd, swe.MOON)
    prev_sign = int(prev_lon / 30.0) % 12

    while jd < jd_end:
        jd_next = min(jd + STEP, jd_end)
        curr_lon = get_body_lon(jd_next, swe.MOON)
        curr_sign = int(curr_lon / 30.0) % 12

        if curr_sign != prev_sign:
            target_lon = curr_sign * 30.0
            jd_exact = bisect_body_longitude(jd, jd_next, swe.MOON, target_lon)
            if jd_exact is not None:
                results.append((jd_exact, curr_sign))

        prev_sign = curr_sign
        prev_lon = curr_lon
        jd = jd_next

    return results


def find_moon_aspects(jd_start, jd_end):
    """
    月と各天体のメジャーアスペクトを検出。
    (jd_exact, aspect_abbrev, planet_name, moon_lon) のリストを返す。
    """
    STEP = 2.0 / 24.0  # 2時間
    results = []

    for planet_id, planet_name in MOON_ASPECT_TARGETS:
        for aspect_angle, _, aspect_abbrev in ASPECTS:
            jd = jd_start
            prev_val = None

            while jd < jd_end:
                jd_next = min(jd + STEP, jd_end)
                moon_lon = get_body_lon(jd_next, swe.MOON)
                planet_lon = get_body_lon(jd_next, planet_id)
                curr_val = aspect_eval(moon_lon, planet_lon, aspect_angle)

                if prev_val is not None and is_real_crossing(prev_val, curr_val):
                    jd_exact = find_exact_aspect_time(
                        swe.MOON, planet_id, aspect_angle, jd, jd_next
                    )
                    if jd_exact is not None and jd_start <= jd_exact <= jd_end:
                        exact_moon_lon = get_body_lon(jd_exact, swe.MOON)
                        results.append((jd_exact, aspect_abbrev, planet_name, exact_moon_lon))

                prev_val = curr_val
                jd = jd_next

    results.sort(key=lambda x: x[0])
    return results


def determine_voc_periods(moon_aspects, sign_changes):
    """
    VOC期間を判定。
    各サイン移動の前で、同じサイン内の最後のアスペクトがVOC開始。
    サイン移動がVOC終了。

    特殊ケース: アスペクトがサイン移動とほぼ同時刻に起きる場合
    （例: 月が0°乙女座でUranus 0°双子座とスクエアを形成）、
    二分法の精度限界により順序が逆転することがある。
    この場合、tolerance内のアスペクトは前のサイン内として扱う。
    """
    # 同時イベント判定用tolerance（1分 = 1/1440日 ≈ 0.000694日）
    SIMULTANEOUS_TOL = 1.0 / (24.0 * 60.0)

    voc_periods = []

    for jd_ingress, new_sign in sign_changes:
        prev_sign = (new_sign - 1) % 12

        last_aspect = None
        for aspect in reversed(moon_aspects):
            jd_asp = aspect[0]
            if jd_asp >= jd_ingress:
                # アスペクトがイングレスのごく近く（同時イベント）なら
                # 前のサイン内の最後のアスペクトとして扱う
                if jd_asp - jd_ingress < SIMULTANEOUS_TOL:
                    moon_lon = aspect[3]
                    asp_sign = int(moon_lon / 30.0) % 12
                    # 月位置がサイン境界付近（0°00'台 or 前サインの29°台）
                    deg_in_sign = moon_lon % 30.0
                    if asp_sign == new_sign and deg_in_sign < 0.5:
                        last_aspect = aspect
                        break
                    elif asp_sign == prev_sign:
                        last_aspect = aspect
                        break
                continue
            moon_lon = aspect[3]
            asp_sign = int(moon_lon / 30.0) % 12
            if asp_sign == prev_sign:
                last_aspect = aspect
                break

        if last_aspect:
            voc_periods.append((
                last_aspect[0],   # VOC begins (最後のアスペクト時刻)
                last_aspect,      # (jd, abbrev, planet_name, moon_lon)
                jd_ingress,       # VOC ends
                new_sign,
            ))

    return voc_periods


def generate_file1(year, month):
    """ファイル1: 月の動きとVoid of Course Moonを生成"""
    jd_start, jd_end = month_jd_range(year, month)

    # VOC月境界処理のため、スキャン範囲を前後に拡張
    # （月初のVOC ends検出、月末のVOC begins→翌月VOC ends検出）
    jd_scan_start = jd_start - 3.0
    jd_scan_end = jd_end + 3.0

    print("  月のアスペクトを計算中...")
    moon_aspects = find_moon_aspects(jd_scan_start, jd_scan_end)
    month_aspects = [a for a in moon_aspects if jd_start <= a[0] < jd_end]
    print(f"    → {len(month_aspects)} 個のアスペクトを検出（月内）")

    print("  月のサイン移動を計算中...")
    sign_changes = find_moon_sign_changes(jd_scan_start, jd_scan_end)
    month_sign_changes = [sc for sc in sign_changes if jd_start <= sc[0] < jd_end]
    print(f"    → {len(month_sign_changes)} 回のサイン移動を検出（月内）")

    print("  VOC期間を判定中...")
    voc_periods = determine_voc_periods(moon_aspects, sign_changes)
    print(f"    → {len(voc_periods)} 個のVOC期間を検出（全範囲）")

    # VOC開始のアスペクトJDを集合で管理
    voc_begin_jds = set()
    for voc_begin_jd, _, _, _ in voc_periods:
        voc_begin_jds.add(voc_begin_jd)

    # VOC終了のイングレスJDをマップで管理
    voc_end_map = {}
    for _, _, jd_ingress, new_sign in voc_periods:
        voc_end_map[jd_ingress] = new_sign

    # 月末をまたぐVOC: VOC beginsが月内 & VOC endsが翌月
    extra_voc_end_jds = set()
    for voc_begin_jd, _, jd_ingress, _ in voc_periods:
        if jd_start <= voc_begin_jd < jd_end and jd_ingress >= jd_end:
            extra_voc_end_jds.add(jd_ingress)

    # イベントリストを構築
    events = []

    # アスペクト（月内のみ）
    for jd_asp, abbrev, planet_name, moon_lon in moon_aspects:
        if jd_asp < jd_start or jd_asp >= jd_end:
            continue
        is_voc_begin = any(abs(jd_asp - vb) < 1e-6 for vb in voc_begin_jds)
        dt = jd_to_datetime_jst(jd_asp)
        pos_str = format_position_abbrev(moon_lon)
        aspect_str = f"{abbrev}{planet_name}"
        if is_voc_begin:
            aspect_str += " (VOC begins)"
        events.append((jd_asp, dt, pos_str, aspect_str, False))

    # サイン移動（月内 + 月末VOCを閉じる翌月分）
    for jd_ingress, new_sign in sign_changes:
        in_month = jd_start <= jd_ingress < jd_end
        closes_month_end_voc = jd_ingress in extra_voc_end_jds
        if not (in_month or closes_month_end_voc):
            continue
        dt = jd_to_datetime_jst(jd_ingress)
        sign_full = SIGN_FULL[new_sign]
        sign_abbr = SIGN_ABBREV[new_sign]
        pos_str = f"{sign_abbr} 00°00'"
        is_voc_end = any(abs(jd_ingress - ve) < 1e-6 for ve in voc_end_map)
        if is_voc_end:
            aspect_str = f" enters 0°{sign_full} (VOC ends)"
            events.append((jd_ingress, dt, pos_str, aspect_str, True))
        else:
            aspect_str = f" enters 0°{sign_full}"
            events.append((jd_ingress, dt, pos_str, aspect_str, False))

    # 時系列ソート
    # 同じ表示分のイベントではアスペクトをサイン移動の前に配置
    # （サイン境界でアスペクトと移動が同時の場合、VOC begins→VOC endsの順を保証）
    events.sort(key=lambda x: (
        x[1],  # datetime (分単位の表示時刻) で一次ソート
        1 if x[3].strip().startswith("enters") else 0  # 同一分内: アスペクト→サイン移動
    ))

    # ヘッダー
    header = f"{year}年{month}月の月☽の動きとVoidofCourseMoon\n\n"
    header += "Date\n"
    header += f"{MONTH_ABBREV[month]} {year}, Time\tMoonPosition\tMoonAspects\t\n"

    # 出力行を生成
    lines = [header]
    for jd, dt, pos_str, aspect_str, is_voc_end in events:
        date_str = format_date_file1(dt, month)
        if is_voc_end:
            line = f"{date_str}\t{pos_str}\t{aspect_str}\t-\t"
        else:
            line = f"{date_str}\t{pos_str}\t{aspect_str}\t\t"
        lines.append(line)

    return "\n".join(lines)


# ==============================================================================
# ファイル2: 各天体のアスペクト表
# ==============================================================================

def find_planet_aspects(jd_start, jd_end):
    """天体間のメジャーアスペクトを検出（月を除く）"""
    STEP = 6.0 / 24.0  # 6時間
    results = []

    bodies = PLANET_ASPECT_BODIES

    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            body1_id, body1_name = bodies[i]
            body2_id, body2_name = bodies[j]

            for aspect_angle, aspect_full, _ in ASPECTS:
                jd = jd_start
                prev_val = None

                while jd < jd_end:
                    jd_next = min(jd + STEP, jd_end)
                    lon1 = get_body_lon(jd_next, body1_id)
                    lon2 = get_body_lon(jd_next, body2_id)
                    curr_val = aspect_eval(lon1, lon2, aspect_angle)

                    if prev_val is not None and is_real_crossing(prev_val, curr_val):
                        jd_exact = find_exact_aspect_time(
                            body1_id, body2_id, aspect_angle, jd, jd_next
                        )
                        if jd_exact is not None and jd_start <= jd_exact <= jd_end:
                            lon1_exact = get_body_lon(jd_exact, body1_id)
                            desc = f"{body1_name} {aspect_full} {body2_name}"
                            pos = format_position_full(lon1_exact)
                            results.append((jd_exact, desc, pos))

                    prev_val = curr_val
                    jd = jd_next

    return results


def find_planet_ingresses(jd_start, jd_end):
    """天体のサイン・イングレスを検出"""
    # 天体ごとのスキャンステップ（日数）
    STEP_MAP = {
        swe.SUN: 1.0,
        swe.MERCURY: 0.5,
        swe.VENUS: 0.5,
        swe.MARS: 1.0,
        swe.JUPITER: 2.0,
        swe.SATURN: 3.0,
        swe.URANUS: 5.0,
        swe.NEPTUNE: 7.0,
        swe.PLUTO: 7.0,
    }

    results = []

    for body_id, body_name in INGRESS_BODIES:
        step = STEP_MAP.get(body_id, 1.0)
        jd = jd_start
        prev_lon = get_body_lon(jd, body_id)
        prev_sign = int(prev_lon / 30.0) % 12

        while jd < jd_end:
            jd_next = min(jd + step, jd_end)
            curr_lon = get_body_lon(jd_next, body_id)
            curr_sign = int(curr_lon / 30.0) % 12

            if curr_sign != prev_sign:
                target_lon = curr_sign * 30.0
                jd_exact = bisect_body_longitude(jd, jd_next, body_id, target_lon)
                if jd_exact is not None:
                    sign_full = SIGN_FULL[curr_sign]
                    desc = f"{body_name} enters {sign_full}"
                    pos = f"{sign_full} 00°00'"
                    results.append((jd_exact, desc, pos))

            prev_sign = curr_sign
            prev_lon = curr_lon
            jd = jd_next

    return results


def find_stations(jd_start, jd_end):
    """逆行/順行ステーションを検出"""
    STEP = 1.0  # 1日
    results = []

    for body_id, body_name in STATION_BODIES:
        jd = jd_start
        _, prev_speed = get_body_lon_speed(jd, body_id)

        while jd < jd_end:
            jd_next = min(jd + STEP, jd_end)
            _, curr_speed = get_body_lon_speed(jd_next, body_id)

            if prev_speed * curr_speed < 0:
                jd_exact = bisect_speed_zero(jd, jd_next, body_id)
                if jd_exact is not None:
                    lon = get_body_lon(jd_exact, body_id)
                    pos = format_position_full(lon)

                    if prev_speed > 0 and curr_speed < 0:
                        desc = f"{body_name} Retrograde"
                    else:
                        desc = f"{body_name} Direct"

                    results.append((jd_exact, desc, pos))

            prev_speed = curr_speed
            jd = jd_next

    return results


def find_moon_phases(jd_start, jd_end):
    """
    月相を検出（新月・上弦・満月・下弦）

    離角(elongation) = (Moon - Sun) % 360 は月の公転で単調増加（約12°/日）。
    各月相は離角が特定の値を通過する時刻として検出する。
    """
    STEP = 3.0 / 24.0  # 3時間（離角は~0.5°/h変化するので十分）
    results = []

    phases = [
        (0.0,   "New Moon"),
        (90.0,  "First Quarter Moon"),
        (180.0, "Full Moon"),
        (270.0, "Last Quarter Moon"),
    ]

    jd = jd_start
    prev_elong = None

    while jd < jd_end:
        jd_next = min(jd + STEP, jd_end)
        moon_lon = get_body_lon(jd_next, swe.MOON)
        sun_lon = get_body_lon(jd_next, swe.SUN)
        curr_elong = (moon_lon - sun_lon) % 360.0

        if prev_elong is not None:
            for phase_angle, phase_name in phases:
                # 離角がphase_angleを通過したか判定
                if _elongation_crossed(prev_elong, curr_elong, phase_angle):
                    # 二分法で正確な時刻を特定
                    def make_phase_func(pa):
                        def f(jd_inner):
                            ml = get_body_lon(jd_inner, swe.MOON)
                            sl = get_body_lon(jd_inner, swe.SUN)
                            e = (ml - sl) % 360.0
                            delta = (e - pa + 180.0) % 360.0 - 180.0
                            return delta
                        return f

                    jd_exact = bisect_find_zero(make_phase_func(phase_angle), jd, jd_next)
                    if jd_exact is not None and jd_start <= jd_exact <= jd_end:
                        moon_lon_exact = get_body_lon(jd_exact, swe.MOON)
                        si, _, _ = lon_to_sign_deg_min(moon_lon_exact)
                        sign_full = SIGN_FULL[si]
                        desc = f"{phase_name} in {sign_full}"
                        pos = format_position_full(moon_lon_exact)
                        results.append((jd_exact, desc, pos))

        prev_elong = curr_elong
        jd = jd_next

    return results


def _elongation_crossed(prev_elong, curr_elong, target):
    """
    離角がtargetを通過したか判定。
    離角は基本的に単調増加（~12°/日）だが、360→0のラップアラウンドがある。
    """
    # 前ステップから今ステップへの離角変化量（通常は正の小さい値）
    delta = (curr_elong - prev_elong) % 360.0
    if delta > 180.0:
        # 逆行（まれ）または計算の揺らぎ
        return False

    # prev_elongからdelta度分進む間にtargetを通過したか
    dist_to_target = (target - prev_elong) % 360.0
    return 0.0 < dist_to_target <= delta


def find_eclipses(jd_start, jd_end):
    """日蝕・月蝕を検出"""
    results = []

    # 月蝕
    jd = jd_start
    while jd < jd_end:
        try:
            retflag, tret = swe.lun_eclipse_when(jd, swe.FLG_SWIEPH)
            jd_eclipse = tret[0]  # 最大食の時刻
        except Exception:
            break

        if jd_eclipse >= jd_end:
            break

        if jd_eclipse >= jd_start and retflag > 0:
            moon_lon = get_body_lon(jd_eclipse, swe.MOON)
            si, _, _ = lon_to_sign_deg_min(moon_lon)
            sign_full = SIGN_FULL[si]

            # 蝕のタイプを判定
            if retflag & swe.ECL_TOTAL:
                desc = f"Total Lunar Eclipse in {sign_full}"
            elif retflag & swe.ECL_PENUMBRAL:
                desc = f"Penumbral Lunar Eclipse in {sign_full}"
            else:
                desc = f"Lunar Eclipse in {sign_full}"

            pos = format_position_full(moon_lon)
            results.append((jd_eclipse, desc, pos))

        jd = jd_eclipse + 10.0  # 次の蝕まで少なくとも数週間あるので10日進める

    # 日蝕（全球検索）
    jd = jd_start
    while jd < jd_end:
        try:
            retflag, tret = swe.sol_eclipse_when_glob(jd, swe.FLG_SWIEPH)
            jd_eclipse = tret[0]
        except Exception:
            break

        if jd_eclipse >= jd_end:
            break

        if jd_eclipse >= jd_start and retflag > 0:
            sun_lon = get_body_lon(jd_eclipse, swe.SUN)
            si, _, _ = lon_to_sign_deg_min(sun_lon)
            sign_full = SIGN_FULL[si]

            if retflag & swe.ECL_TOTAL:
                desc = f"Total Solar Eclipse in {sign_full}"
            elif retflag & swe.ECL_ANNULAR:
                desc = f"Annular Solar Eclipse in {sign_full}"
            else:
                desc = f"Solar Eclipse in {sign_full}"

            pos = format_position_full(sun_lon)
            results.append((jd_eclipse, desc, pos))

        jd = jd_eclipse + 10.0

    return results


def generate_file2(year, month):
    """ファイル2: 各天体のアスペクト表を生成"""
    jd_start, jd_end = month_jd_range(year, month)

    all_events = []

    print("  天体間アスペクトを計算中...")
    planet_aspects = find_planet_aspects(jd_start, jd_end)
    print(f"    → {len(planet_aspects)} 個のアスペクトを検出")
    all_events.extend(planet_aspects)

    print("  天体のイングレスを計算中...")
    ingresses = find_planet_ingresses(jd_start, jd_end)
    print(f"    → {len(ingresses)} 個のイングレスを検出")
    all_events.extend(ingresses)

    print("  逆行/順行ステーションを計算中...")
    stations = find_stations(jd_start, jd_end)
    print(f"    → {len(stations)} 個のステーションを検出")
    all_events.extend(stations)

    print("  月相を計算中...")
    moon_phases = find_moon_phases(jd_start, jd_end)
    print(f"    → {len(moon_phases)} 個の月相を検出")
    all_events.extend(moon_phases)

    print("  日蝕・月蝕を計算中...")
    eclipses = find_eclipses(jd_start, jd_end)
    print(f"    → {len(eclipses)} 個の蝕を検出")
    all_events.extend(eclipses)

    # 時系列ソート
    all_events.sort(key=lambda x: x[0])

    # ヘッダー
    header = f"{year}年{month}月の各天体のアスペクト表\n"

    # 出力行を生成
    lines = [header]
    for jd, desc, pos in all_events:
        dt = jd_to_datetime_jst(jd)
        date_str = format_date_file2(dt)
        line = f"{date_str},\t{desc},\t{pos}"
        lines.append(line)

    return "\n".join(lines)


# ==============================================================================
# メインエントリポイント
# ==============================================================================

def main():
    if len(sys.argv) != 3:
        print("使い方: python3 astro_calendar.py <年> <月>")
        print("例:     python3 astro_calendar.py 2026 3")
        sys.exit(1)

    year = int(sys.argv[1])
    month = int(sys.argv[2])

    if month < 1 or month > 12:
        print("エラー: 月は1〜12の範囲で指定してください。")
        sys.exit(1)

    print(f"=== {year}年{month}月の占星術カレンダーを生成中 ===\n")

    # ファイル1: 月の動き＋VOC
    print("[ファイル1] 月の動きとVoid of Course Moon")
    file1_content = generate_file1(year, month)
    file1_name = f"moon_voc_{year}_{month:02d}.txt"
    with open(file1_name, "w", encoding="utf-8") as f:
        f.write(file1_content)
    print(f"  → 出力: {file1_name}\n")

    # ファイル2: 各天体のアスペクト表
    print("[ファイル2] 各天体のアスペクト表")
    file2_content = generate_file2(year, month)
    file2_name = f"planet_aspects_{year}_{month:02d}.txt"
    with open(file2_name, "w", encoding="utf-8") as f:
        f.write(file2_content)
    print(f"  → 出力: {file2_name}\n")

    print("=== 完了 ===")
    swe.close()


if __name__ == "__main__":
    main()
