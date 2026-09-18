/**
 * 偶発的品位（Lilly の表）と太陽光線・セクト・ハイズ。
 * natal_classical.py の accidental_dignity / solar_phase / hayz_status を写す。
 * 表そのものは未照合（verified:false）のまま Python から書き出した値を使う。
 */
import {
  BENEFICS, CAZIMI_ORB, COMBUST_ORB, DIURNAL_PLANETS, HOUSE_SCORE, LUMINARIES,
  MEAN_MOTION, NOCTURNAL_PLANETS, PARTILE_ORB, PLANET_JA, UNDER_BEAMS_ORB,
} from "./tables.ts";
import { isPartile, norm360, roundTo, signOf, signedSep } from "./util.ts";

export type SolarState = "sun" | "cazimi" | "combust" | "under_beams" | "free";

export interface SolarPhase {
  state: SolarState;
  distance: number;
  same_sign_as_sun: boolean;
}

/**
 * 太陽光線との関係。
 * 決定 C（2026-09-18 三河）：カジミ・燃焼・光線下はいずれも太陽と同一サインを要する。
 * サインが違えば離角によらず free。典拠 CA I ll.9344–9353（燃焼）。
 */
export function solarPhase(planetLon: number, sunLon: number, planetName: string): SolarPhase {
  if (planetName === "Sun") {
    return { state: "sun", distance: 0, same_sign_as_sun: true };
  }
  const dist = Math.abs(signedSep(sunLon, planetLon));
  const sameSign = signOf(planetLon) === signOf(sunLon);
  let state: SolarState;
  if (!sameSign) state = "free";
  else if (dist <= CAZIMI_ORB) state = "cazimi";
  else if (dist <= COMBUST_ORB) state = "combust";
  else if (dist <= UNDER_BEAMS_ORB) state = "under_beams";
  else state = "free";
  return { state, distance: roundTo(dist, 2), same_sign_as_sun: sameSign };
}

/** オリエンタル（太陽に先行して昇る）か オクシデンタルか */
export function orientality(
  planetLon: number, sunLon: number, planetName: string,
): "oriental" | "occidental" | null {
  if (planetName === "Sun") return null;
  return norm360(planetLon - sunLon) > 180 ? "oriental" : "occidental";
}

/** 月が光を増しているか */
export function moonIncreasing(moonLon: number, sunLon: number): boolean {
  return norm360(moonLon - sunLon) < 180;
}

/** 惑星のセクト（党派）。水星はオリエンタルなら昼、オクシデンタルなら夜 */
export function planetSect(
  planetName: string, orient: "oriental" | "occidental" | null,
): "diurnal" | "nocturnal" {
  if (DIURNAL_PLANETS.includes(planetName)) return "diurnal";
  if (NOCTURNAL_PLANETS.includes(planetName)) return "nocturnal";
  return orient === "oriental" ? "diurnal" : "nocturnal";
}

export type Hayz = "hayz" | "half_hayz" | "contrary" | "neutral";

export function hayzStatus(
  pSect: "diurnal" | "nocturnal", isDay: boolean, aboveHorizon: boolean, signMasculine: boolean,
): Hayz {
  const masculinePlanet = pSect === "diurnal";
  const inSect = (isDay && pSect === "diurnal") || (!isDay && pSect === "nocturnal");
  const rightHalf = (isDay && aboveHorizon) || (!isDay && !aboveHorizon);
  const rightSign = (masculinePlanet && signMasculine) || (!masculinePlanet && !signMasculine);
  if (inSect && rightHalf && rightSign) return "hayz";
  if (inSect && (rightHalf || rightSign)) return "half_hayz";
  if (!inSect && !rightHalf && !rightSign) return "contrary";
  return "neutral";
}

export interface AccidentalItem {
  code: string;
  label_ja: string;
  points: number;
}

export interface AccidentalContext {
  lons: Record<string, number>;
  nodeLon: number;
  southNodeLon: number;
  stars: Record<string, number>;
  moonIncreasing: boolean;
}

export interface AccidentalPlanet {
  name: string;
  longitude: number;
  speed: number;
  retrograde: boolean;
  houseEffective: number;
  orientality: "oriental" | "occidental" | null;
  solarPhase: SolarPhase;
}

/** ♄ と ♂ に挟まれているか（体の囲みで近似） */
export function isBesieged(lon: number, satLon: number, marsLon: number): boolean {
  let a = satLon;
  let b = marsLon;
  let arc = norm360(b - a);
  if (arc > 180) {
    [a, b] = [b, a];
    arc = norm360(b - a);
  }
  if (arc > 30) return false;
  const d = norm360(lon - a);
  return d > 0 && d < arc;
}

/** Lilly の偶発的品位表。項目の順序は Python と同じ（JSON の items 配列がこの順） */
export function accidentalDignity(
  planet: AccidentalPlanet, ctx: AccidentalContext,
): { score: number; items: AccidentalItem[] } {
  const items: AccidentalItem[] = [];
  const push = (code: string, labelJa: string, points: number) =>
    items.push({ code, label_ja: labelJa, points });
  const name = planet.name;
  const lon = planet.longitude;

  const h = planet.houseEffective;
  if (HOUSE_SCORE[String(h)] !== undefined) {
    push(`house_${h}`, `第${h}ハウス`, HOUSE_SCORE[String(h)]);
  }

  if (!LUMINARIES.includes(name)) {
    if (planet.retrograde) push("retrograde", "逆行", -5);
    else push("direct", "順行", 4);
  }
  if (Math.abs(planet.speed) > MEAN_MOTION[name]) push("swift", "速行（平均運動以上）", 2);
  else push("slow", "遅行（平均運動未満）", -2);

  const orient = planet.orientality;
  if (["Saturn", "Jupiter", "Mars"].includes(name)) {
    if (orient === "oriental") push("oriental", "オリエンタル", 2);
    else push("occidental", "オクシデンタル", -2);
  } else if (["Venus", "Mercury"].includes(name)) {
    if (orient === "occidental") push("occidental", "オクシデンタル", 2);
    else push("oriental", "オリエンタル", -2);
  } else if (name === "Moon") {
    if (ctx.moonIncreasing) push("increasing_light", "増光", 2);
    else push("decreasing_light", "減光", -2);
  }

  if (name !== "Sun") {
    const st = planet.solarPhase.state;
    if (st === "cazimi") push("cazimi", "カジミ", 5);
    else if (st === "combust") push("combust", "コンバスト", -5);
    else if (st === "under_beams") push("under_beams", "サンビームス下", -4);
    else push("free_of_beams", "光線から自由", 5);
  }

  for (const other of ["Jupiter", "Venus", "Saturn", "Mars"]) {
    if (other === name) continue;
    const d = Math.abs(signedSep(lon, ctx.lons[other]));
    const benefic = BENEFICS.includes(other);
    const ol = other.toLowerCase();
    const ja = PLANET_JA[other];
    // 決定 D：同度数であることを要する（PARTILE_ORB はどのアスペクトかを選ぶ窓）
    const samePartile = isPartile(lon, ctx.lons[other]);
    if (d <= PARTILE_ORB && samePartile) {
      push(`partile_conjunction_${ol}`, `${ja}と合（パーティル）`, benefic ? 5 : -5);
    } else if (Math.abs(d - 120) <= PARTILE_ORB && samePartile && benefic) {
      push(`partile_trine_${ol}`, `${ja}と三分（パーティル）`, 4);
    } else if (Math.abs(d - 60) <= PARTILE_ORB && samePartile && benefic) {
      push(`partile_sextile_${ol}`, `${ja}と六分（パーティル）`, 3);
    } else if (Math.abs(d - 180) <= PARTILE_ORB && samePartile && !benefic) {
      push(`partile_opposition_${ol}`, `${ja}と衝（パーティル）`, -4);
    } else if (Math.abs(d - 90) <= PARTILE_ORB && samePartile && !benefic) {
      push(`partile_square_${ol}`, `${ja}と矩（パーティル）`, -3);
    }
  }

  if (Math.abs(signedSep(lon, ctx.nodeLon)) <= PARTILE_ORB && isPartile(lon, ctx.nodeLon)) {
    push("partile_conjunction_north_node", "ドラゴンヘッドと合", 4);
  }
  if (Math.abs(signedSep(lon, ctx.southNodeLon)) <= PARTILE_ORB
    && isPartile(lon, ctx.southNodeLon)) {
    push("partile_conjunction_south_node", "ドラゴンテイルと合", -4);
  }

  if (name !== "Saturn" && name !== "Mars") {
    if (isBesieged(lon, ctx.lons.Saturn, ctx.lons.Mars)) {
      push("besieged_saturn_mars", "土星と火星に挟まれる", -5);
    }
  }

  if (Math.abs(signedSep(lon, ctx.stars.Regulus)) <= PARTILE_ORB
    && isPartile(lon, ctx.stars.Regulus)) {
    push("conjunct_regulus", "レグルスと合", 6);
  }
  if (Math.abs(signedSep(lon, ctx.stars.Spica)) <= PARTILE_ORB
    && isPartile(lon, ctx.stars.Spica)) {
    push("conjunct_spica", "スピカと合", 5);
  }
  if (Math.abs(signedSep(lon, ctx.stars.Algol)) <= 5.0) {
    push("conjunct_algol", "アルゴルと合（5°以内）", -5);
  }

  return { score: items.reduce((s, it) => s + it.points, 0), items };
}
