/**
 * 恒星 3 星（Regulus, Spica, Algol）。
 *
 * Python の現行実装：
 *   - Spica は Swiss Ephemeris の内蔵値（視位置・その日の黄道）から得られる
 *   - Regulus と Algol は sefstars.txt が無いため J2000 定数＋歳差 50.29″/年 の線形近似
 * この「方式の混在」は I-2-1 の保留により現状維持（要件書 v0.3 Phase 2 手順 9）。
 * JS では Swiss の内蔵値を呼べないため 3 星とも線形近似で計算する。
 * Spica だけ Python と約 18″ ずれる（GT-2 では fixed_stars は報告のみ）。
 */
import { FIXED_STARS_J2000, PRECESSION_PER_YEAR } from "./tables.ts";
import { norm360 } from "./util.ts";

export const SPICA_NOTE =
  "Spica in the Python reference comes from the Swiss Ephemeris built-in value "
  + "(apparent position of date); here it is the same linear approximation as the other "
  + "two stars, so it differs by about 18 arcseconds.";

export function fixedStarLongitudes(jd: number): Record<string, number> {
  const years = (jd - 2451545.0) / 365.25;
  const out: Record<string, number> = {};
  for (const [name, j2000] of Object.entries(FIXED_STARS_J2000)) {
    out[name] = norm360(j2000 + PRECESSION_PER_YEAR * years);
  }
  return out;
}
