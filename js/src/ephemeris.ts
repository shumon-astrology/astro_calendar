/**
 * Astronomy Engine のアダプタ。
 * Python（pyswisseph 2.10.03、se1 未配置のため Moshier）と同じ値を返すことを
 * ゴールデン比較（GT-2）で確認する。
 *
 * 座標系：真黄道・真春分点 of date（Ecliptic() が返す ECT）。
 * 速度：±1 時間の差分商（要件書 II-3）。
 */
import * as A from "astronomy-engine";
import { norm360 } from "./util.ts";

export const EPHEMERIS_LABEL = {
  library: "astronomy-engine",
  version: "2.1.19",
  frame: "true ecliptic of date" as const,
};

/**
 * 日出没に使う太陽の高度（度）。
 * Python は swe.rise_trans(..., BIT_DISC_CENTER)＝視位置・円盤中心・海抜 0 m・
 * 標準気圧 1013.25 hPa・0 ℃。0 ℃ の地平線大気差は約 36.6′ にあたる。
 * ゴールデン 5 図（sample・A・B・C・polar_4）で Python との差が最小になる値を
 * 較正して定数化した（最大 0.026 分＝1.6 秒）。
 */
export const RISE_SET_ALTITUDE_DEG = -0.61;

export const BODY: Record<string, A.Body> = {
  Sun: A.Body.Sun,
  Moon: A.Body.Moon,
  Mercury: A.Body.Mercury,
  Venus: A.Body.Venus,
  Mars: A.Body.Mars,
  Jupiter: A.Body.Jupiter,
  Saturn: A.Body.Saturn,
  Uranus: A.Body.Uranus,
  Neptune: A.Body.Neptune,
  Pluto: A.Body.Pluto,
};

export function timeOf(jd: number): A.AstroTime {
  return A.MakeTime(jd - 2451545.0);
}

/** 天体の黄経（真黄道 of date） */
export function bodyLongitude(jd: number, name: string): number {
  const t = timeOf(jd);
  return norm360(A.Ecliptic(A.GeoVector(BODY[name], t, true)).elon);
}

/** 天体の黄経と黄経速度（度/日） */
export function bodyLonSpeed(jd: number, name: string): { longitude: number; speed: number } {
  const h = 1 / 24;
  const lon = bodyLongitude(jd, name);
  const before = bodyLongitude(jd - h, name);
  const after = bodyLongitude(jd + h, name);
  const diff = ((after - before + 540) % 360) - 180;
  return { longitude: lon, speed: diff / (2 * h) };
}

/** 真黄道傾斜（度） */
export function trueObliquity(jd: number): number {
  return A.e_tilt(timeOf(jd)).tobl;
}

/** 地方恒星時（度）。Greenwich 視恒星時＋東経 */
export function localSiderealTime(jd: number, geoLon: number): number {
  return norm360(A.SiderealTime(timeOf(jd)) * 15 + geoLon);
}

/** 太陽の実高度（度、大気差なし）＝ Python の swe.azalt の true altitude */
export function sunAltitude(jd: number, lat: number, geoLon: number): number {
  const t = timeOf(jd);
  const eq = A.Equator(A.Body.Sun, t, new A.Observer(lat, geoLon, 0), true, true);
  // Python の swe.azalt は大気差を加えない「真高度」を返すので refraction は付けない
  return A.Horizon(t, new A.Observer(lat, geoLon, 0), eq.ra, eq.dec).altitude;
}

/**
 * 指定 JD 以降の最初の日の出／日の入り（JD）。見つからなければ null。
 * Python の _sun_rise_set と同じく「次の事象」を返す。
 */
export function sunRiseSet(jd: number, lat: number, geoLon: number, rise: boolean): number | null {
  const observer = new A.Observer(lat, geoLon, 0);
  const t = A.SearchAltitude(
    A.Body.Sun, observer, rise ? +1 : -1, timeOf(jd), 2, RISE_SET_ALTITUDE_DEG,
  );
  return t ? t.ut + 2451545.0 : null;
}

/** 平均ノードの黄経（Meeus 47.7） */
export function meanNode(jd: number): number {
  const T = (jd - 2451545.0) / 36525.0;
  const om = 125.0445479
    - 1934.1362891 * T
    + 0.0020754 * T * T
    + (T * T * T) / 467441
    - (T * T * T * T) / 60616000;
  return norm360(om);
}

/** 平均ノードの日々の運動（度/日）。速度は差分商で求める */
export function meanNodeSpeed(jd: number): number {
  const h = 1 / 24;
  return (((meanNode(jd + h) - meanNode(jd - h) + 540) % 360) - 180) / (2 * h);
}

/** トゥルーノード（瞬時軌道面の昇交点）の黄経 */
export function trueNode(jd: number): number {
  const t = timeOf(jd);
  const st = A.GeoMoonState(t);
  const rot = A.Rotation_EQJ_ECT(t);
  const p = A.RotateVector(rot, new A.Vector(st.x, st.y, st.z, t));
  const v = A.RotateVector(rot, new A.Vector(st.vx, st.vy, st.vz, t));
  // 軌道面の法線 h = r × v、昇交点の方向 = ẑ × h
  const hx = p.y * v.z - p.z * v.y;
  const hy = p.z * v.x - p.x * v.z;
  return norm360((Math.atan2(hx, -hy) * 180) / Math.PI);
}

export function trueNodeSpeed(jd: number): number {
  const h = 1 / 24;
  return (((trueNode(jd + h) - trueNode(jd - h) + 540) % 360) - 180) / (2 * h);
}

export interface Syzygy {
  jd: number;
  type: "new" | "full";
  longitude: number;
  sunLongitude: number;
  moonLongitude: number;
}

/**
 * 出生直前の新月または満月。
 * Python は 0.25 日刻みで遡って最初に見つけた朔望を採る（＝直前の朔望）。
 */
export function prenatalSyzygy(jd: number, maxDays = 45): Syzygy | null {
  const target = timeOf(jd);
  let best: { ut: number; phase: 0 | 180 } | null = null;
  for (const phase of [0, 180] as const) {
    let found: A.AstroTime | null = null;
    let cursor = A.SearchMoonPhase(phase, A.MakeTime(target.ut - maxDays), maxDays + 1);
    while (cursor && cursor.ut <= target.ut) {
      found = cursor;
      cursor = A.SearchMoonPhase(phase, A.MakeTime(cursor.ut + 1), maxDays);
    }
    if (found && (!best || found.ut > best.ut)) best = { ut: found.ut, phase };
  }
  if (!best) return null;
  const jdExact = best.ut + 2451545.0;
  const sunLongitude = bodyLongitude(jdExact, "Sun");
  const moonLongitude = bodyLongitude(jdExact, "Moon");
  return {
    jd: jdExact,
    type: best.phase === 0 ? "new" : "full",
    longitude: best.phase === 0 ? sunLongitude : moonLongitude,
    sunLongitude,
    moonLongitude,
  };
}
