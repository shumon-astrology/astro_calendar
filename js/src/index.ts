/**
 * computeChart(input) → SCHEMA_chart_v2 の JSON。
 * natal_classical.py（タグ v1-reference）の v1 キーに、要件書 I-2・I-4 の
 * 新設ブロックを足したもの。キーの順序はスキーマの properties に合わせる。
 */
import {
  accidentalDignity, hayzStatus, moonIncreasing, orientality, planetSect, solarPhase,
  type AccidentalContext, type SolarPhase,
} from "./accidental.ts";
import { ACCIDENTAL_LABELS_EN } from "./labels.ts";
import { antiscia, findClassicalAspects, receptionSoftening, type AspectBody } from "./aspects.ts";
import { buildDerived, type Condition, type DerivedInput } from "./derived.ts";
import {
  almutenFiguris, almutenOfDegree, essentialDignity, mutualReceptions, triplicityRulers,
  type AlmutenResult, type EssentialDignity,
} from "./dignity.ts";
import {
  EPHEMERIS_LABEL, bodyLonSpeed, bodyLongitude, meanNode, meanNodeSpeed, prenatalSyzygy,
  trueNode, trueNodeSpeed,
} from "./ephemeris.ts";
import { fixedStarLongitudes } from "./fixed_stars.ts";
import { computeHouses, determineHouse, type HouseSystem } from "./houses.ts";
import { isDayChart, partOfFortune, partOfSpirit, sectInfo } from "./lots.ts";
import { planetaryHour } from "./planetary_hours.ts";
import {
  buildProvenance, buildReadingNotes, buildSummary, GENERATOR, type BoundaryWarning,
} from "./serialize.ts";
import { JS_TABLE_SOURCES } from "./sources.ts";
import {
  DEFAULT_TERMS, DEFAULT_TRIPLICITY, DOMICILE_BY_SIGN, TABLE_SOURCES, TERMS_AUDIT,
  TRIPLICITY_TABLES,
} from "./tables.ts";
import { formatLocalDateTime, localToJd } from "./time.ts";
import { isKnownTimezone, resolveTimezone } from "./timezone.ts";
import type {
  SCHEMAChartV2ClassicalNatalChartJSONAmanJyoshiTraditionalchart as ChartV2,
} from "./types/chart_v2.d.ts";
import {
  PLANET_NAMES, SIGN_FULL, degInSign, isMasculineSign, jsonPoint, norm360, roundTo, signOf,
} from "./util.ts";

export type { ChartV2 };

export interface ChartInput {
  year: number;
  month: number;
  day: number;
  /** time_known が false のときは無視され、現地正午で計算する */
  hour?: number;
  minute?: number;
  latitude: number;
  longitude: number;
  /** UTC からの時差（時間）。timezoneId があればそちらが優先 */
  tzOffset?: number;
  /** IANA タイムゾーン名（例 "Asia/Tokyo"） */
  timezoneId?: string;
  place?: string;
  timeKnown?: boolean;
  houseSystem?: HouseSystem;
  triplicity?: string;
  /** provenance.generated_at。決定性テスト（GT-7）で固定するために渡せる */
  generatedAt?: string;
}

const HOUSE_SYSTEM_NAMES: Record<string, string> = {
  R: "Regiomontanus",
  W: "Whole Sign",
};

const ALSO_KNOWN_AS = {
  ascendant: ["Ascendant", "ASC", "Rising sign", "Horoscopus"],
  midheaven: ["Midheaven", "MC", "Medium Coeli"],
  northNode: ["North Node", "Dragon's Head", "Caput Draconis"],
  southNode: ["South Node", "Dragon's Tail", "Cauda Draconis"],
  fortune: ["Part of Fortune", "Fortuna", "Lot of Fortune"],
  spirit: ["Part of Spirit", "Daimon", "Lot of Spirit"],
};

const SEASON_QUARTER_NOTE =
  "season_quarter follows the quarters of the ecliptic (tropical, northern-hemisphere "
  + "convention) and is not mirrored in the southern hemisphere.";

const MOON_PHASE_QUARTERS = ["new_to_first", "first_to_full", "full_to_last", "last_to_new"];
const SEASON_QUARTERS = ["spring", "summer", "autumn", "winter"];

interface PlanetState {
  name: string;
  longitude: number;
  speed: number;
  retrograde: boolean;
  house: number | null;
  houseEffective: number | null;
  nearCusp: boolean | null;
  distToNext: number | null;
  aboveHorizon: boolean | null;
  orientality: "oriental" | "occidental" | null;
  sect: "diurnal" | "nocturnal" | null;
  inSect: boolean | null;
  hayz: string | null;
  solarPhase: SolarPhase;
  essential: EssentialDignity;
  accidental: { score: number; items: { code: string; label_ja: string; points: number }[] } | null;
  totalScore: number | null;
}

/** SCHEMA_chart_v2.json の型（json-schema-to-typescript で生成したもの）で返す */
export function computeChart(input: ChartInput): ChartV2 {
  const timeKnown = input.timeKnown ?? true;
  const houseSystem: HouseSystem = input.houseSystem ?? "R";
  const triplicityName = input.triplicity ?? DEFAULT_TRIPLICITY;
  const tripTable = TRIPLICITY_TABLES[triplicityName] ?? TRIPLICITY_TABLES[DEFAULT_TRIPLICITY];
  const { latitude: lat, longitude: geoLon } = input;

  // --- 時刻とタイムゾーン ---
  const hour = timeKnown ? (input.hour ?? 12) : 12;
  const minute = timeKnown ? (input.minute ?? 0) : 0;
  let tzOffset = input.tzOffset ?? 9.0;
  let timezoneId: string | null = null;
  let dstApplied: boolean | null = null;
  if (input.timezoneId && isKnownTimezone(input.timezoneId)) {
    const resolved = resolveTimezone(input.year, input.month, input.day, hour, minute,
      input.timezoneId);
    tzOffset = resolved.tzOffset;
    timezoneId = resolved.timezoneId;
    dstApplied = resolved.dstApplied;
  }
  const jd = localToJd(input.year, input.month, input.day, hour, minute, tzOffset);

  // --- 天体 ---
  const raw: Record<string, { longitude: number; speed: number }> = {};
  for (const name of PLANET_NAMES) raw[name] = bodyLonSpeed(jd, name);
  const sunLon = raw.Sun.longitude;
  const moonLon = raw.Moon.longitude;
  const positions: Record<string, number> = {};
  for (const name of PLANET_NAMES) positions[name] = raw[name].longitude;

  // --- ハウスとセクト（時刻不明なら求めない） ---
  const houses = timeKnown ? computeHouses(jd, lat, geoLon, houseSystem) : null;
  const ascLon = houses ? houses.ascendant : null;
  const mcLon = houses ? houses.midheaven : null;
  const cusps = houses ? houses.cusps : null;
  const sect = (timeKnown && ascLon !== null)
    ? sectInfo(sunLon, ascLon, jd, lat, geoLon) : null;
  const isDay = sect ? sect.is_day : null;
  const increasing = moonIncreasing(moonLon, sunLon);

  const nodeLon = meanNode(jd);
  const nodeSpeed = meanNodeSpeed(jd);
  const southNodeLon = norm360(nodeLon + 180);
  const trueNodeLon = trueNode(jd);
  const trueNodeSpd = trueNodeSpeed(jd);
  const trueSouthNodeLon = norm360(trueNodeLon + 180);
  const stars = fixedStarLongitudes(jd);

  // --- 天体の状態 ---
  const planets: PlanetState[] = PLANET_NAMES.map((name) => {
    const { longitude, speed } = raw[name];
    const placement = cusps ? determineHouse(longitude, cusps) : null;
    const orient = orientality(longitude, sunLon, name);
    const pSect = isDay === null ? null : planetSect(name, orient);
    const above = placement ? placement.houseEffective >= 7 : null;
    const essential = essentialDignity(longitude, name, isDay ?? true, {
      tripTable,
      receptions: mutualReceptions(name, positions),
      sectUnknown: isDay === null,
    });
    return {
      name,
      longitude,
      speed,
      retrograde: speed < 0,
      house: placement ? placement.house : null,
      houseEffective: placement ? placement.houseEffective : null,
      nearCusp: placement ? placement.nearCusp : null,
      distToNext: placement ? placement.distToNext : null,
      aboveHorizon: above,
      orientality: orient,
      sect: pSect,
      inSect: (isDay === null || pSect === null) ? null
        : (isDay && pSect === "diurnal") || (!isDay && pSect === "nocturnal"),
      hayz: (isDay === null || pSect === null || above === null) ? null
        : hayzStatus(pSect, isDay, above, isMasculineSign(signOf(longitude))),
      solarPhase: solarPhase(longitude, sunLon, name),
      essential,
      accidental: null,
      totalScore: null,
    };
  });

  if (timeKnown) {
    const ctx: AccidentalContext = {
      lons: positions, nodeLon, southNodeLon, stars, moonIncreasing: increasing,
    };
    for (const p of planets) {
      p.accidental = accidentalDignity({
        name: p.name,
        longitude: p.longitude,
        speed: p.speed,
        retrograde: p.retrograde,
        houseEffective: p.houseEffective as number,
        orientality: p.orientality,
        solarPhase: p.solarPhase,
      }, ctx);
      p.totalScore = p.essential.score + p.accidental.score;
    }
  }

  const byName: Record<string, PlanetState> = {};
  const houseOf: Record<string, number | null> = {};
  for (const p of planets) {
    byName[p.name] = p;
    houseOf[p.name] = p.houseEffective;
  }

  // --- 感受点 ---
  const ascAlmuten = ascLon === null ? null
    : almutenOfDegree(ascLon, isDay ?? true, tripTable, houseOf);
  const mcAlmuten = mcLon === null ? null
    : almutenOfDegree(mcLon, isDay ?? true, tripTable, houseOf);
  const fortuneLon = (ascLon !== null && isDay !== null)
    ? partOfFortune(ascLon, sunLon, moonLon, isDay) : null;
  const spiritLon = (ascLon !== null && isDay !== null)
    ? partOfSpirit(ascLon, sunLon, moonLon, isDay) : null;
  const fortuneNonReversed = ascLon === null ? null : partOfFortune(ascLon, sunLon, moonLon, true);
  const spiritNonReversed = ascLon === null ? null : partOfSpirit(ascLon, sunLon, moonLon, true);

  const syzygy = prenatalSyzygy(jd);
  const syzygyAlmuten = syzygy
    ? almutenOfDegree(syzygy.longitude, isDay ?? true, tripTable, houseOf) : null;

  // --- アスペクト ---
  const bodies: AspectBody[] = planets.map((p) => ({
    name: p.name, longitude: p.longitude, speed: p.speed,
  }));
  if (timeKnown && ascLon !== null && mcLon !== null && fortuneLon !== null) {
    bodies.push({ name: "ASC", longitude: ascLon, speed: 0, isPoint: true });
    bodies.push({ name: "MC", longitude: mcLon, speed: 0, isPoint: true });
    bodies.push({ name: "Fortune", longitude: fortuneLon, speed: 0, isPoint: true });
  }
  const aspects = findClassicalAspects(bodies, isDay ?? true, tripTable);

  const accScores: Record<string, number> = {};
  for (const p of planets) if (p.accidental) accScores[p.name] = p.accidental.score;
  const figuris = (timeKnown && ascLon !== null && fortuneLon !== null)
    ? almutenFiguris(
      { asc: ascLon, sun: sunLon, moon: moonLon, fortune: fortuneLon,
        syzygy: syzygy ? syzygy.longitude : null },
      isDay ?? true, accScores, tripTable, houseOf,
    )
    : null;

  // --- セクトライトの三分主星 ---
  const light = isDay === null ? null : (isDay ? "Sun" : "Moon");
  const triplicityLords: {
    order: string; rank: number; role: string; planet: string;
    house: number | null; dignities: string[]; score: number | null;
  }[] = [];
  if (light) {
    const trip = triplicityRulers(signOf(raw[light].longitude), tripTable);
    const seen = new Set<string>();
    const rows: [string, string, string | null][] = [
      ["昼", "day", trip.day], ["夜", "night", trip.night], ["関与", "participating", trip.participating],
    ];
    rows.forEach(([label, role, nm], index) => {
      if (!nm) return;
      if (seen.has(nm)) {
        const entry = triplicityLords.find((e) => e.planet === nm)!;
        entry.order += "・" + label;
        return;
      }
      seen.add(nm);
      const lp = byName[nm];
      triplicityLords.push({
        order: label,
        rank: index + 1,
        role,
        planet: nm,
        house: lp.houseEffective,
        dignities: lp.essential.labels,
        score: lp.accidental ? lp.essential.score + lp.accidental.score : lp.essential.score,
      });
    });
  }

  const ph = timeKnown ? planetaryHour(jd, lat, geoLon, tzOffset) : null;

  // --- 現代天体 ---
  const modern = ["Uranus", "Neptune", "Pluto"].map((name) => {
    const { longitude, speed } = bodyLonSpeed(jd, name);
    const placement = cusps ? determineHouse(longitude, cusps) : null;
    return { name, longitude, speed, house: placement ? placement.houseEffective : null };
  });

  // --- サイン境界までの分数（±30 分、1 分刻み） ---
  const signChange = (which: "ascendant" | "midheaven") => {
    if (!timeKnown || !houses) {
      return { sign_change_within_minutes: null, minutes_to_previous_sign: null,
        minutes_to_next_sign: null };
    }
    const current = signOf(which === "ascendant" ? houses.ascendant : houses.midheaven);
    let back: number | null = null;
    let forward: number | null = null;
    for (let m = 1; m <= 30; m++) {
      if (back === null) {
        const h = computeHouses(jd - m / 1440, lat, geoLon, houseSystem);
        if (signOf(which === "ascendant" ? h.ascendant : h.midheaven) !== current) back = m;
      }
      if (forward === null) {
        const h = computeHouses(jd + m / 1440, lat, geoLon, houseSystem);
        if (signOf(which === "ascendant" ? h.ascendant : h.midheaven) !== current) forward = m;
      }
      if (back !== null && forward !== null) break;
    }
    const nearest = [back, forward].filter((v): v is number => v !== null);
    return {
      sign_change_within_minutes: nearest.length ? Math.min(...nearest) : null,
      minutes_to_previous_sign: back,
      minutes_to_next_sign: forward,
    };
  };

  const jsonAlmuten = (alm: AlmutenResult | null) => ({
    almuten: alm ? alm.almuten : null,
    almuten_tie: alm ? alm.almuten_tie : false,
    almuten_candidates: alm ? alm.candidates : [],
    almuten_tie_break: alm ? alm.tie_break : null,
    almuten_scores: alm ? alm.scores : {},
  });

  // --- ハウス ---
  const housesJson = cusps
    ? cusps.map((cuspLon, i) => {
      const lord = DOMICILE_BY_SIGN[signOf(cuspLon)];
      const lp = byName[lord];
      return {
        ...jsonPoint(cuspLon),
        house: i + 1,
        lord,
        lord_placement: {
          sign: SIGN_FULL[signOf(lp.longitude)],
          position: jsonPoint(lp.longitude).position,
          house: lp.houseEffective,
          dignities: lp.essential.labels,
          debilities: lp.essential.debilities,
          essential_score: lp.essential.score,
          accidental_score: lp.accidental ? lp.accidental.score : null,
          retrograde: lp.retrograde,
          solar_phase: lp.solarPhase.state,
        },
        ...jsonAlmuten(almutenOfDegree(cuspLon, isDay ?? true, tripTable, houseOf)),
      };
    })
    : null;

  // --- houses_summary ---
  const housesSummary = cusps
    ? (() => {
      const cuspSigns = cusps.map((c) => signOf(c));
      const counts = new Map<number, number>();
      for (const s of cuspSigns) counts.set(s, (counts.get(s) ?? 0) + 1);
      const planetsByHouse: Record<string, string[]> = {};
      for (let h = 1; h <= 12; h++) planetsByHouse[String(h)] = [];
      for (const p of planets) planetsByHouse[String(p.houseEffective)].push(p.name);
      return {
        intercepted_signs: SIGN_FULL.filter((_, i) => !counts.has(i)),
        signs_on_two_cusps: SIGN_FULL.filter((_, i) => (counts.get(i) ?? 0) >= 2),
        empty_houses: Object.entries(planetsByHouse)
          .filter(([, list]) => list.length === 0).map(([h]) => Number(h)),
        planets_by_house: planetsByHouse,
      };
    })()
    : null;

  // --- 月の範囲（時刻不明のときだけ） ---
  const moonRange = timeKnown ? null : (() => {
    const start = localToJd(input.year, input.month, input.day, 0, 0, tzOffset);
    const end = localToJd(input.year, input.month, input.day, 23, 59, tzOffset);
    const a = bodyLongitude(start, "Moon");
    const b = bodyLongitude(end, "Moon");
    return {
      longitude_at_00_00: roundTo(a, 6),
      longitude_at_23_59: roundTo(b, 6),
      sign_at_00_00: SIGN_FULL[signOf(a)],
      sign_at_23_59: SIGN_FULL[signOf(b)],
      sign_change: signOf(a) !== signOf(b),
    };
  })();

  // --- 境界警告 ---
  const warnings: BoundaryWarning[] = [];
  if (timeKnown && houses) {
    const ascChange = signChange("ascendant");
    const mcChange = signChange("midheaven");
    const nearBoundary = (lon: number) => Math.min(degInSign(lon), 30 - degInSign(lon));
    if (nearBoundary(houses.ascendant) <= 2) {
      warnings.push({
        id: "asc_near_sign_boundary", level: 2, target: "ascendant",
        value: roundTo(nearBoundary(houses.ascendant), 4), threshold: 2,
        message_en: `The ascendant is within 2° of a sign boundary`
          + (ascChange.sign_change_within_minutes !== null
            ? ` (sign changes ${ascChange.sign_change_within_minutes} minutes of birth time away).`
            : "."),
      });
    }
    if (nearBoundary(houses.midheaven) <= 2) {
      warnings.push({
        id: "mc_near_sign_boundary", level: 2, target: "midheaven",
        value: roundTo(nearBoundary(houses.midheaven), 4), threshold: 2,
        message_en: `The midheaven is within 2° of a sign boundary`
          + (mcChange.sign_change_within_minutes !== null
            ? ` (sign changes ${mcChange.sign_change_within_minutes} minutes of birth time away).`
            : "."),
      });
    }
    for (const p of planets) {
      if (p.distToNext !== null && p.distToNext <= 1) {
        warnings.push({
          id: "planet_near_cusp", level: 1, target: p.name,
          value: roundTo(p.distToNext, 4), threshold: 1,
          message_en: `${p.name} is within 1° of the cusp of house `
            + `${(p.house! % 12) + 1}; it is counted in that house by the 5° rule.`,
        });
      }
    }
    if (sect?.borderline) {
      warnings.push({
        id: "sect_borderline", level: 2, target: "sect",
        value: sect.sun_altitude === null ? null : roundTo(sect.sun_altitude, 4), threshold: 0,
        message_en: "The horizon (ASC–DSC) and the Sun's altitude disagree about the sect.",
      });
    }
  }

  // --- derived ---
  const derivedInput: DerivedInput = {
    mode: timeKnown ? "full" : "time_unknown",
    isDay,
    planets: planets.map((p) => ({
      name: p.name,
      sign: SIGN_FULL[signOf(p.longitude)],
      position: jsonPoint(p.longitude).position,
      house: p.houseEffective,
      essential_score: p.essential.score,
      accidental_score: p.accidental ? p.accidental.score : null,
      total_score: p.totalScore,
      dignities: p.essential.labels,
      debilities: p.essential.debilities,
      peregrine: p.essential.peregrine,
      peregrine_cancelled_by: p.essential.peregrine_cancelled_by,
      retrograde: p.retrograde,
      solar_phase: p.solarPhase.state,
      in_sect: p.inSect,
      sign_index: signOf(p.longitude),
    })),
    aspects: aspects.map((a) => ({
      from: a.planet1, to: a.planet2, aspect: a.aspect, orb: a.orb, partile: a.partile,
      reception_softens: receptionSoftening(a).softens,
    })),
    houses: housesJson
      ? housesJson.map((h) => ({ house: h.house, lord: h.lord, sign_index: h.sign_index }))
      : null,
    ascendant: (ascLon !== null && ascAlmuten)
      ? {
        sign_index: signOf(ascLon),
        lord: DOMICILE_BY_SIGN[signOf(ascLon)],
        almuten: ascAlmuten.almuten,
      }
      : null,
    lots: (fortuneLon !== null && spiritLon !== null)
      ? {
        fortune_lord: DOMICILE_BY_SIGN[signOf(fortuneLon)],
        spirit_lord: DOMICILE_BY_SIGN[signOf(spiritLon)],
      }
      : null,
    almutens: figuris ? figuris.almutens : [],
    almutenFigurisScore: figuris && figuris.almutens.length
      ? figuris.table[figuris.almutens[0]].total : null,
  };
  const derived = buildDerived(derivedInput);

  // --- summary ---
  const sectLightState = light ? byName[light] : null;
  const ascLordName = ascLon === null ? null : DOMICILE_BY_SIGN[signOf(ascLon)];
  const summary = buildSummary({
    timeKnown,
    isDay,
    borderline: sect ? sect.borderline : false,
    sectLight: (sectLightState && light)
      ? {
        planet: light,
        sign: SIGN_FULL[signOf(sectLightState.longitude)],
        house: sectLightState.houseEffective,
        essential: sectLightState.essential.score,
        accidental: sectLightState.accidental ? sectLightState.accidental.score : null,
      }
      : null,
    ascendant: (ascLon !== null && ascLordName && ascAlmuten)
      ? {
        sign: SIGN_FULL[signOf(ascLon)],
        position: jsonPoint(ascLon).position,
        lord: ascLordName,
        lordSign: SIGN_FULL[signOf(byName[ascLordName].longitude)],
        lordHouse: byName[ascLordName].houseEffective,
        lordDignities: byName[ascLordName].essential.labels,
        lordPeregrine: byName[ascLordName].essential.peregrine,
        almuten: ascAlmuten.almuten,
        almutenIsCoSignificator: ascAlmuten.almuten !== null
          && ascAlmuten.almuten !== ascLordName,
      }
      : null,
    lordOfGeniture: {
      primary: derived.lord_of_geniture.primary,
      score: derivedInput.almutenFigurisScore,
      secondary: derived.lord_of_geniture.secondary,
      secondaryScore: derived.strongest_planet.total_score
        ?? derived.strongest_planet.essential_score,
    },
    strongest: {
      planet: derived.strongest_planet.planet,
      score: derived.strongest_planet.total_score ?? derived.strongest_planet.essential_score,
    },
    weakest: {
      planet: derived.weakest_planet.planet,
      score: derived.weakest_planet.total_score ?? derived.weakest_planet.essential_score,
    },
    outOfSectMalefic: derived.out_of_sect_malefic as Condition | null,
    lots: (fortuneLon !== null && spiritLon !== null)
      ? {
        fortuneSign: SIGN_FULL[signOf(fortuneLon)],
        fortunePosition: jsonPoint(fortuneLon).position,
        fortuneHouse: cusps ? determineHouse(fortuneLon, cusps).house : null,
        fortuneLord: DOMICILE_BY_SIGN[signOf(fortuneLon)],
        spiritSign: SIGN_FULL[signOf(spiritLon)],
        spiritPosition: jsonPoint(spiritLon).position,
        spiritHouse: cusps ? determineHouse(spiritLon, cusps).house : null,
        spiritLord: DOMICILE_BY_SIGN[signOf(spiritLon)],
        sectReversed: isDay === false,
      }
      : null,
    flags: warnings.map((w) => w.id),
    generator: GENERATOR,
  });

  // --- JSON 化 ---
  const planetJson = (p: PlanetState) => {
    const codes = new Set((p.accidental?.items ?? []).map((it) => it.code));
    const ant = antiscia(p.longitude);
    return {
      ...jsonPoint(p.longitude),
      name: p.name,
      speed: roundTo(p.speed, 6),
      retrograde: p.retrograde,
      house: p.houseEffective,
      house_raw: p.house,
      near_next_cusp: p.nearCusp,
      above_horizon: p.aboveHorizon,
      essential_dignity: {
        dignities: p.essential.labels,
        debilities: p.essential.debilities,
        peregrine: p.essential.peregrine,
        peregrine_cancelled_by: p.essential.peregrine_cancelled_by,
        peregrine_scored: p.essential.peregrine_scored,
        peregrine_uncertain: p.essential.peregrine_uncertain,
        mutual_receptions: p.essential.mutual_receptions,
        score: p.essential.score,
        score_note: p.essential.score_note,
        rulers_of_position: p.essential.rulers,
        triplicity_rulers: p.essential.triplicity_rulers,
        term_audit: p.essential.term_audit,
      },
      accidental_dignity: p.accidental
        ? {
          score: p.accidental.score,
          items: p.accidental.items.map((it) => ({
            code: it.code,
            points: it.points,
            label_ja: it.label_ja,
            label_en: ACCIDENTAL_LABELS_EN[it.code] ?? it.code.replace(/_/g, " "),
          })),
          solar_phase: p.solarPhase.state,
          distance_from_sun: p.solarPhase.distance,
          cazimi: p.solarPhase.state === "cazimi",
          combust: p.solarPhase.state === "combust",
          under_beams: p.solarPhase.state === "under_beams",
          free_of_beams: p.solarPhase.state === "free",
          orientality: p.orientality,
          motion: codes.has("swift") ? "swift" : "slow",
        }
        : null,
      sect: p.sect === null ? null : {
        planet_sect: p.sect,
        in_sect: p.inSect,
        hayz: p.hayz,
      },
      total_score: p.totalScore,
      antiscion: jsonPoint(ant.antiscion),
      contra_antiscion: jsonPoint(ant.contraAntiscion),
    };
  };

  const nodeEntry = (lonValue: number, name: string, speed: number, aka: string[]) => {
    const placement = cusps ? determineHouse(lonValue, cusps) : null;
    return {
      ...jsonPoint(lonValue),
      name,
      house: placement ? placement.houseEffective : null,
      retrograde: speed < 0,
      also_known_as: aka,
    };
  };

  const ascChange = signChange("ascendant");
  const mcChange = signChange("midheaven");
  const generatedAt = input.generatedAt ?? new Date().toISOString();

  const chart = {
    schema_version: "v2",
    generator: GENERATOR,
    birth_data: {
      year: input.year,
      month: input.month,
      day: input.day,
      hour,
      minute,
      tz_offset: tzOffset,
      latitude: lat,
      longitude: geoLon,
      julian_day_ut: roundTo(jd, 8),
      place: input.place ?? null,
      timezone_id: timezoneId,
      time_known: timeKnown,
      time_source: timeKnown ? "entered" : "noon_default",
      dst_applied: dstApplied,
    },
    tables_used: {
      terms: DEFAULT_TERMS,
      terms_audit: TERMS_AUDIT,
      triplicity: triplicityName,
      faces: "chaldean",
      house_system: {
        code: houseSystem,
        name: HOUSE_SYSTEM_NAMES[houseSystem] ?? houseSystem,
      },
      node: "mean",
      sources: { ...TABLE_SOURCES, ...JS_TABLE_SOURCES },
      scoring: "lilly",
      ephemeris: EPHEMERIS_LABEL,
      timezone: {
        source: "IANA tzdata via Intl",
        version: null,
      },
    },
    sect: sect === null ? null : {
      method: sect.method,
      is_day: sect.is_day,
      chart_sect: sect.is_day ? "diurnal" : "nocturnal",
      sun_altitude: sect.sun_altitude === null ? null : roundTo(sect.sun_altitude, 4),
      altitude_is_day: sect.altitude_is_day,
      borderline: sect.borderline,
      moon_increasing_light: increasing,
      moon_phase_quarter: MOON_PHASE_QUARTERS[Math.floor(norm360(moonLon - sunLon) / 90)],
      season_quarter: SEASON_QUARTERS[Math.floor(signOf(sunLon) / 3)],
      season_quarter_note: SEASON_QUARTER_NOTE,
      sect_light: {
        light,
        triplicity_lords: triplicityLords,
      },
    },
    planetary_day_hour: ph,
    angles: (ascLon === null || mcLon === null) ? null : {
      ascendant: {
        ...jsonPoint(ascLon),
        lord: DOMICILE_BY_SIGN[signOf(ascLon)],
        ...jsonAlmuten(ascAlmuten),
        also_known_as: ALSO_KNOWN_AS.ascendant,
        ...ascChange,
      },
      midheaven: {
        ...jsonPoint(mcLon),
        lord: DOMICILE_BY_SIGN[signOf(mcLon)],
        ...jsonAlmuten(mcAlmuten),
        also_known_as: ALSO_KNOWN_AS.midheaven,
        ...mcChange,
      },
    },
    planets: planets.map(planetJson),
    nodes: {
      used: "mean",
      mean: [
        nodeEntry(nodeLon, "NorthNode", nodeSpeed, ALSO_KNOWN_AS.northNode),
        nodeEntry(southNodeLon, "SouthNode", nodeSpeed, ALSO_KNOWN_AS.southNode),
      ],
      true: [
        nodeEntry(trueNodeLon, "NorthNode", trueNodeSpd, ALSO_KNOWN_AS.northNode),
        nodeEntry(trueSouthNodeLon, "SouthNode", trueNodeSpd, ALSO_KNOWN_AS.southNode),
      ],
    },
    lots: (fortuneLon === null || spiritLon === null || !cusps) ? null : {
      fortune: {
        ...jsonPoint(fortuneLon),
        house: determineHouse(fortuneLon, cusps).house,
        lord: DOMICILE_BY_SIGN[signOf(fortuneLon)],
        also_known_as: ALSO_KNOWN_AS.fortune,
        sect_reversed: isDay === false,
        non_reversed_longitude: roundTo(fortuneNonReversed as number, 6),
        non_reversed_position: jsonPoint(fortuneNonReversed as number).position,
      },
      spirit: {
        ...jsonPoint(spiritLon),
        house: determineHouse(spiritLon, cusps).house,
        lord: DOMICILE_BY_SIGN[signOf(spiritLon)],
        also_known_as: ALSO_KNOWN_AS.spirit,
        sect_reversed: isDay === false,
        non_reversed_longitude: roundTo(spiritNonReversed as number, 6),
        non_reversed_position: jsonPoint(spiritNonReversed as number).position,
      },
    },
    prenatal_syzygy: syzygy
      ? {
        type: syzygy.type,
        datetime_local: formatLocalDateTime(syzygy.jd, tzOffset),
        ...jsonAlmuten(syzygyAlmuten),
        ...jsonPoint(syzygy.longitude),
      }
      : null,
    houses: housesJson,
    aspects: aspects.map((a) => {
      const reception = receptionSoftening(a);
      return {
        from: a.planet1,
        to: a.planet2,
        aspect: a.aspect,
        orb: a.orb,
        max_orb: a.max_orb,
        partile: a.partile,
        condition: a.state,
        direction: a.direction,
        reception_from_to: a.reception_1to2,
        reception_to_from: a.reception_2to1,
        mutual_reception: a.mutual_reception,
        reception_softens: reception.softens,
        reception_minor: reception.minor,
        time_unknown_caveat: !timeKnown,
      };
    }),
    almuten_figuris: figuris === null ? null : {
      almutens: figuris.almutens,
      almuten: figuris.almuten,
      almuten_tie: figuris.almuten_tie,
      ranking: figuris.ranked,
      scores: Object.fromEntries(
        Object.entries(figuris.table).map(([name, row]) => [name, {
          ascendant: row.asc,
          sun: row.sun,
          moon: row.moon,
          fortune: row.fortune,
          syzygy: row.syzygy,
          total: row.total,
          accidental: row.accidental,
          house: row.house,
        }]),
      ),
    },
    fixed_stars: Object.fromEntries(
      Object.entries(stars).map(([name, starLon]) => [name, jsonPoint(starLon)]),
    ),
    modern_reference: {
      note: "古典判断には用いない参考値 / not used in classical judgment",
      planets: modern.map((m) => ({
        ...jsonPoint(m.longitude),
        name: m.name,
        speed: roundTo(m.speed, 6),
        retrograde: m.speed < 0,
        house: m.house,
      })),
    },
    moon_range: moonRange,
    derived,
    houses_summary: housesSummary,
    fixed_star_contacts: null,
    boundary_warnings: warnings,
    vocation: null,
    vocation_blocked_reason: timeKnown
      ? "vocation is implemented in a later phase"
      : "birth time unknown",
    timing: null,
    summary,
    reading_notes: buildReadingNotes(timeKnown),
    provenance: buildProvenance(generatedAt, "natal_classical.py@226e8d6"),
  };
  return chart as unknown as ChartV2;
}
