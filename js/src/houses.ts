/**
 * ASC／MC／ハウスカスプ。
 * レジオモンタナス（既定）はハウス円（地平線の南北点を通る大円）と黄道の交点として解く。
 * Python は swe.houses(jd, lat, lon, b"R") を呼んでいる。ゴールデン 10 図で
 * 最大 0.2 秒角（5.5e-5 度）まで一致することを確認済み。
 */
import { localSiderealTime, trueObliquity } from "./ephemeris.ts";
import { CUSP_THRESHOLD } from "./tables.ts";
import { angularDistance, norm360, signOf } from "./util.ts";

const DEG = Math.PI / 180;

type Vec = [number, number, number];

const cross = (a: Vec, b: Vec): Vec => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
const dot = (a: Vec, b: Vec): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const neg = (a: Vec): Vec => [-a[0], -a[1], -a[2]];

/** 地平線より上にあるべきハウス（8〜12）と下にあるべきハウス（2〜6） */
const ABOVE_HORIZON_HOUSES = [8, 9, 10, 11, 12];
const BELOW_HORIZON_HOUSES = [2, 3, 4, 5, 6];

export type HouseSystem = "R" | "W";

export interface HousesResult {
  ascendant: number;
  midheaven: number;
  cusps: number[];      // index 0 = 第1ハウス
  obliquity: number;
  siderealTime: number; // 地方恒星時（度）
}

/**
 * レジオモンタナスのカスプを計算する。
 *
 * 各ハウス円は地平線の南北点と、赤道上の点（赤経 = ARMC + 30°×n）を通る大円。
 * 黄道との交点は 2 つあるので、そのハウスが地平線の上下どちらにあるべきか
 * （1・7 室は東西どちらか）で選ぶ。極圏でもこの規則で Swiss と一致する。
 */
export function computeHouses(
  jd: number, lat: number, geoLon: number, system: HouseSystem = "R",
): HousesResult {
  const theta = localSiderealTime(jd, geoLon);
  const eps = trueObliquity(jd);
  const th = theta * DEG;
  const e = eps * DEG;
  const phi = lat * DEG;

  const north: Vec = [-Math.sin(phi) * Math.cos(th), -Math.sin(phi) * Math.sin(th), Math.cos(phi)];
  const zenith: Vec = [Math.cos(phi) * Math.cos(th), Math.cos(phi) * Math.sin(th), Math.sin(phi)];
  const east = cross(north, zenith);
  const eclipticPole: Vec = [0, -Math.sin(e), Math.cos(e)];
  const xEcl: Vec = [1, 0, 0];
  const yEcl: Vec = [0, Math.cos(e), Math.sin(e)];

  const longitudeOf = (v: Vec) => norm360((Math.atan2(dot(v, yEcl), dot(v, xEcl)) * 180) / Math.PI);

  const cusps: number[] = [];
  for (let house = 1; house <= 12; house++) {
    const H = (theta + 30 * (((house - 10) % 12 + 12) % 12)) * DEG;
    const equatorPoint: Vec = [Math.cos(H), Math.sin(H), 0];
    let d = cross(cross(north, equatorPoint), eclipticPole);
    const norm = Math.hypot(d[0], d[1], d[2]);
    d = [d[0] / norm, d[1] / norm, d[2] / norm];
    const altitude = dot(d, zenith);
    const eastward = dot(d, east);
    let flip = false;
    if (ABOVE_HORIZON_HOUSES.includes(house)) flip = altitude < 0;
    else if (BELOW_HORIZON_HOUSES.includes(house)) flip = altitude > 0;
    else if (house === 1) flip = eastward < 0;   // ASC は東の地平線
    else if (house === 7) flip = eastward > 0;   // DSC は西の地平線
    cusps.push(longitudeOf(flip ? neg(d) : d));
  }

  const ascendant = cusps[0];
  const midheaven = cusps[9];

  if (system === "W") {
    const base = signOf(ascendant) * 30;
    return {
      ascendant, midheaven, obliquity: eps, siderealTime: theta,
      cusps: Array.from({ length: 12 }, (_, i) => norm360(base + 30 * i)),
    };
  }
  return { ascendant, midheaven, cusps, obliquity: eps, siderealTime: theta };
}

export interface HousePlacement {
  house: number;
  nearCusp: boolean;
  distToNext: number;
  houseEffective: number;
}

/** 天体がどのハウスにあるか＝ natal.determine_house（カスプ手前 5°は次室扱い） */
export function determineHouse(planetLon: number, cuspLons: number[]): HousePlacement {
  for (let i = 0; i < 12; i++) {
    const start = cuspLons[i];
    const end = cuspLons[(i + 1) % 12];
    const span = angularDistance(start, end);
    const distFromStart = angularDistance(start, planetLon);
    if (distFromStart < span) {
      const distToNext = span - distFromStart;
      const nearCusp = distToNext < CUSP_THRESHOLD;
      const house = i + 1;
      return {
        house,
        nearCusp,
        distToNext,
        houseEffective: nearCusp ? (house % 12) + 1 : house,
      };
    }
  }
  return { house: 1, nearCusp: false, distToNext: 0, houseEffective: 1 };
}
