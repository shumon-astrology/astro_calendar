/**
 * 角度と数値整形の共通関数。
 * natal_classical.py / astro_calendar.py の対応する関数を写したもの。
 */
import tables from "../data/tables_dignity.json" with { type: "json" };

export const SIGN_ABBREV = tables.sign_abbrev as string[];
export const SIGN_FULL = tables.sign_full as string[];
export const ELEMENTS = tables.elements as string[];
export const PLANET_NAMES = tables.planets as string[];

/** 0〜360 に正規化する */
export function norm360(deg: number): number {
  return ((deg % 360) + 360) % 360;
}

/** 黄経 → サインインデックス（0=牡羊） */
export function signOf(lon: number): number {
  return Math.floor(norm360(lon) / 30);
}

/** 黄経 → サイン内度数（0.0〜30.0） */
export function degInSign(lon: number): number {
  return norm360(lon) - signOf(lon) * 30;
}

/** lon1 から見た lon2 への符号付き角度差（-180〜180） */
export function signedSep(lon1: number, lon2: number): number {
  return (((lon2 - lon1 + 180) % 360) + 360) % 360 - 180;
}

/** lonFrom → lonTo への正方向の角距離（0〜360）＝ natal._angular_distance */
export function angularDistance(lonFrom: number, lonTo: number): number {
  return norm360(lonTo - lonFrom);
}

/** メジャー・アスペクトの角度（パーティル判定用） */
const MAJOR_ASPECT_ANGLES = [0, 60, 90, 120, 180];

/** パーティルの閾値（度）。正確なアスペクトからのずれ */
export const PARTILE_TOLERANCE = 1.0;

/**
 * パーティルか ＝ 決定 D 改（2026-09-19 三河）。
 * メジャー・アスペクト（合・六分・矩・三分・衝）の正確な角度からのずれが
 * 1°以内なら真。サインは問わない（例：牡羊 12°40′ と蟹 11°40′〜13°40′ は矩で成立）。
 * 一時採用した「両天体の整数度が同じ」は撤回した。
 */
export function isPartile(lon1: number, lon2: number): boolean {
  const sep = Math.abs(signedSep(lon1, lon2));
  return MAJOR_ASPECT_ANGLES.some((angle) => Math.abs(sep - angle) <= PARTILE_TOLERANCE);
}

export function elementOf(signIndex: number): string {
  return ELEMENTS[signIndex % 4];
}

/** 牡羊・双子・獅子…（奇数サイン）が男性サイン */
export function isMasculineSign(signIndex: number): boolean {
  return signIndex % 2 === 0;
}

/**
 * Python の round() と同じ丸め（偶数丸め）。
 * JS の toFixed は半数切り上げなので、境界値で Python と食い違わないようにする。
 */
export function roundTo(value: number, digits: number): number {
  if (!Number.isFinite(value)) return value;
  const factor = 10 ** digits;
  const scaled = value * factor;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  let result: number;
  if (Math.abs(diff - 0.5) < Number.EPSILON * Math.abs(scaled)) {
    result = floor % 2 === 0 ? floor : floor + 1;   // ちょうど半数 → 偶数側
  } else {
    result = Math.round(scaled);
  }
  // 二進の誤差で 1 桁ずれないよう、十進の丸めでもう一度均す
  const viaString = Number(value.toFixed(digits));
  return Math.abs(viaString - result / factor) < 1e-12 ? viaString : result / factor;
}

/** 黄経 → (サイン, 度, 分)。分は切り捨て（Python の int()） */
export function toSignDegMin(lon: number): { sign: number; degrees: number; minutes: number } {
  const l = norm360(lon);
  const sign = Math.floor(l / 30);
  const deg = l - sign * 30;
  const degrees = Math.floor(deg);
  const minutes = Math.floor((deg - degrees) * 60);
  return { sign, degrees, minutes };
}

const pad2 = (n: number) => String(n).padStart(2, "0");

/** "Can 28°24'" 形式 */
export function formatPosition(lon: number): string {
  const { sign, degrees, minutes } = toSignDegMin(lon);
  return `${SIGN_ABBREV[sign]} ${pad2(degrees)}°${pad2(minutes)}'`;
}

/** JSON の感受点ブロック（v1 の _json_point と同形・同順） */
export interface JsonPoint {
  longitude: number;
  sign: string;
  sign_index: number;
  degrees: number;
  minutes: number;
  position: string;
}

export function jsonPoint(lon: number): JsonPoint {
  const { sign, degrees, minutes } = toSignDegMin(lon);
  return {
    longitude: roundTo(norm360(lon), 6),
    sign: SIGN_FULL[sign],
    sign_index: signOf(lon),
    degrees,
    minutes,
    position: formatPosition(lon),
  };
}
