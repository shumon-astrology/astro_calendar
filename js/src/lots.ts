/**
 * フォーチュン／スピリットとセクト判定。
 * ロットは夜図で式が反転する（Dorotheus 式、METHOD_natal_v1 決定 6）。
 * セクトは ASC–DSC 地平線基準が主、太陽高度が副（METHOD §9）。
 */
import { sunAltitude } from "./ephemeris.ts";
import { SECT_METHOD } from "./tables.ts";
import { norm360 } from "./util.ts";

/** 昼： ASC ＋ ☽ − ☉ ／ 夜： ASC ＋ ☉ − ☽ */
export function partOfFortune(asc: number, sun: number, moon: number, isDay: boolean): number {
  return norm360(isDay ? asc + moon - sun : asc + sun - moon);
}

/** スピリットはフォーチュンの昼夜逆算 */
export function partOfSpirit(asc: number, sun: number, moon: number, isDay: boolean): number {
  return norm360(isDay ? asc + sun - moon : asc + moon - sun);
}

/** 太陽が ASC–DSC 軸より上（第7〜12ハウス側）なら昼図 */
export function isDayChart(sunLon: number, ascLon: number): boolean {
  return norm360(sunLon - ascLon) > 180;
}

export interface SectInfo {
  method: string;
  is_day: boolean;
  sun_altitude: number | null;
  altitude_is_day: boolean | null;
  borderline: boolean;
}

export function sectInfo(
  sunLon: number, ascLon: number, jd: number, lat: number, geoLon: number,
): SectInfo {
  const isDay = isDayChart(sunLon, ascLon);
  let alt: number | null = null;
  try {
    alt = sunAltitude(jd, lat, geoLon);
  } catch {
    alt = null;
  }
  const altDay = alt === null ? null : alt > 0;
  return {
    method: SECT_METHOD,
    is_day: isDay,
    sun_altitude: alt,
    altitude_is_day: altDay,
    borderline: altDay !== null && altDay !== isDay,
  };
}
