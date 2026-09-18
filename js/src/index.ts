/**
 * computeChart(input) → v1 相当の JSON（Phase 2 の範囲）。
 * natal_classical.calculate_classical_chart + to_json を写したもの。
 * v2 の新設ブロック（derived, summary, vocation …）は Phase 3・4 で足す。
 */
import * as A from "astronomy-engine";
import {
  accidentalDignity, hayzStatus, moonIncreasing, orientality, planetSect, solarPhase,
  type AccidentalContext, type SolarPhase,
} from "./accidental.ts";
import { antiscia, findClassicalAspects, type AspectBody } from "./aspects.ts";
import {
  almutenFiguris, almutenOfDegree, essentialDignity, mutualReceptions, triplicityRulers,
  type AlmutenResult, type EssentialDignity,
} from "./dignity.ts";
import {
  EPHEMERIS_LABEL, bodyLonSpeed, meanNode, meanNodeSpeed, prenatalSyzygy, trueNode,
  trueNodeSpeed,
} from "./ephemeris.ts";
import { fixedStarLongitudes } from "./fixed_stars.ts";
import { computeHouses, determineHouse, type HouseSystem } from "./houses.ts";
import { isDayChart, partOfFortune, partOfSpirit, sectInfo } from "./lots.ts";
import { planetaryHour } from "./planetary_hours.ts";
import {
  DEFAULT_TERMS, DEFAULT_TRIPLICITY, DOMICILE_BY_SIGN, TABLE_SOURCES, TERMS_AUDIT,
  TRIPLICITY_TABLES,
} from "./tables.ts";
import { localToJd } from "./time.ts";
import {
  PLANET_NAMES, elementOf, isMasculineSign, jsonPoint, norm360, roundTo, signOf,
  type JsonPoint,
} from "./util.ts";

export interface ChartInput {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  latitude: number;
  longitude: number;
  tzOffset?: number;
  houseSystem?: HouseSystem;
  triplicity?: string;
}

const HOUSE_SYSTEM_NAMES: Record<string, string> = {
  R: "Regiomontanus",
  W: "Whole Sign",
};

const NODE_NAMES = { node: "NorthNode", southNode: "SouthNode" } as const;

interface PlanetState {
  name: string;
  longitude: number;
  speed: number;
  retrograde: boolean;
  house: number;
  houseEffective: number;
  nearCusp: boolean;
  aboveHorizon: boolean;
  orientality: "oriental" | "occidental" | null;
  sect: "diurnal" | "nocturnal";
  inSect: boolean;
  hayz: string;
  solarPhase: SolarPhase;
  essential: EssentialDignity;
  accidental: { score: number; items: { code: string; label_ja: string; points: number }[] };
  totalScore: number;
}

/** v1 スキーマの JSON を返す */
export function computeChart(input: ChartInput): Record<string, unknown> {
  const tzOffset = input.tzOffset ?? 9.0;
  const houseSystem: HouseSystem = input.houseSystem ?? "R";
  const triplicityName = input.triplicity ?? DEFAULT_TRIPLICITY;
  const tripTable = TRIPLICITY_TABLES[triplicityName] ?? TRIPLICITY_TABLES[DEFAULT_TRIPLICITY];
  const { latitude: lat, longitude: geoLon } = input;

  const jd = localToJd(input.year, input.month, input.day, input.hour, input.minute, tzOffset);
  const houses = computeHouses(jd, lat, geoLon, houseSystem);
  const ascLon = houses.ascendant;
  const mcLon = houses.midheaven;
  const cusps = houses.cusps;

  const raw: Record<string, { longitude: number; speed: number }> = {};
  for (const name of PLANET_NAMES) raw[name] = bodyLonSpeed(jd, name);
  const sunLon = raw.Sun.longitude;
  const moonLon = raw.Moon.longitude;

  const sect = sectInfo(sunLon, ascLon, jd, lat, geoLon);
  const isDay = sect.is_day;
  const increasing = moonIncreasing(moonLon, sunLon);

  const nodeLon = meanNode(jd);
  const nodeSpeed = meanNodeSpeed(jd);
  const southNodeLon = norm360(nodeLon + 180);
  const trueNodeLon = trueNode(jd);
  const trueNodeSpd = trueNodeSpeed(jd);
  const trueSouthNodeLon = norm360(trueNodeLon + 180);

  const stars = fixedStarLongitudes(jd);
  const positions: Record<string, number> = {};
  for (const name of PLANET_NAMES) positions[name] = raw[name].longitude;

  const planets: PlanetState[] = PLANET_NAMES.map((name) => {
    const { longitude, speed } = raw[name];
    const placement = determineHouse(longitude, cusps);
    const orient = orientality(longitude, sunLon, name);
    const pSect = planetSect(name, orient);
    const above = placement.houseEffective >= 7;
    const essential = essentialDignity(longitude, name, isDay, {
      tripTable,
      receptions: mutualReceptions(name, positions),
    });
    return {
      name,
      longitude,
      speed,
      retrograde: speed < 0,
      house: placement.house,
      houseEffective: placement.houseEffective,
      nearCusp: placement.nearCusp,
      aboveHorizon: above,
      orientality: orient,
      sect: pSect,
      inSect: (isDay && pSect === "diurnal") || (!isDay && pSect === "nocturnal"),
      hayz: hayzStatus(pSect, isDay, above, isMasculineSign(signOf(longitude))),
      solarPhase: solarPhase(longitude, sunLon, name),
      essential,
      accidental: { score: 0, items: [] },
      totalScore: 0,
    };
  });

  const ctx: AccidentalContext = {
    lons: positions,
    nodeLon,
    southNodeLon,
    stars,
    moonIncreasing: increasing,
  };
  for (const p of planets) {
    p.accidental = accidentalDignity(
      {
        name: p.name,
        longitude: p.longitude,
        speed: p.speed,
        retrograde: p.retrograde,
        houseEffective: p.houseEffective,
        orientality: p.orientality,
        solarPhase: p.solarPhase,
      },
      ctx,
    );
    p.totalScore = p.essential.score + p.accidental.score;
  }

  const byName: Record<string, PlanetState> = {};
  const houseOf: Record<string, number | null> = {};
  for (const p of planets) {
    byName[p.name] = p;
    houseOf[p.name] = p.houseEffective;
  }

  const ascAlmuten = almutenOfDegree(ascLon, isDay, tripTable, houseOf);
  const fortuneLon = partOfFortune(ascLon, sunLon, moonLon, isDay);
  const spiritLon = partOfSpirit(ascLon, sunLon, moonLon, isDay);
  const syzygy = prenatalSyzygy(jd);
  const syzygyAlmuten = syzygy
    ? almutenOfDegree(syzygy.longitude, isDay, tripTable, houseOf)
    : null;

  const bodies: AspectBody[] = planets.map((p) => ({
    name: p.name, longitude: p.longitude, speed: p.speed,
  }));
  bodies.push({ name: "ASC", longitude: ascLon, speed: 0, isPoint: true });
  bodies.push({ name: "MC", longitude: mcLon, speed: 0, isPoint: true });
  bodies.push({ name: "Fortune", longitude: fortuneLon, speed: 0, isPoint: true });
  const aspects = findClassicalAspects(bodies, isDay, tripTable);

  const accScores: Record<string, number> = {};
  for (const p of planets) accScores[p.name] = p.accidental.score;
  const figuris = almutenFiguris(
    { asc: ascLon, sun: sunLon, moon: moonLon, fortune: fortuneLon,
      syzygy: syzygy ? syzygy.longitude : null },
    isDay, accScores, tripTable, houseOf,
  );

  // --- セクトライトの三分主星 ---
  const light = isDay ? "Sun" : "Moon";
  const lightSign = signOf(raw[light].longitude);
  const trip = triplicityRulers(lightSign, tripTable);
  const seen = new Set<string>();
  const triplicityLords: { order: string; planet: string; house: number; dignities: string[]; score: number }[] = [];
  for (const [label, nm] of [["昼", trip.day], ["夜", trip.night], ["関与", trip.participating]] as const) {
    if (!nm) continue;
    if (seen.has(nm)) {
      const entry = triplicityLords.find((e) => e.planet === nm)!;
      entry.order += "・" + label;
      continue;
    }
    seen.add(nm);
    const lp = byName[nm];
    triplicityLords.push({
      order: label,
      planet: nm,
      house: lp.houseEffective,
      dignities: lp.essential.labels,
      score: lp.essential.score + lp.accidental.score,
    });
  }

  const ph = planetaryHour(jd, lat, geoLon, tzOffset);

  // --- 現代天体（参考値） ---
  const modern = ["Uranus", "Neptune", "Pluto"].map((name) => {
    const { longitude, speed } = bodyLonSpeed(jd, name);
    const placement = determineHouse(longitude, cusps);
    return { name, longitude, speed, placement };
  });

  const nodeEntry = (lon: number, name: string, speed: number) => {
    const placement = determineHouse(lon, cusps);
    return {
      ...jsonPoint(lon),
      name,
      house: placement.houseEffective,
      retrograde: speed < 0,
    };
  };

  const housesJson = cusps.map((cuspLon, i) => {
    const lord = DOMICILE_BY_SIGN[signOf(cuspLon)];
    const lp = byName[lord];
    return {
      ...jsonPoint(cuspLon),
      house: i + 1,
      lord,
      lord_placement: {
        sign: jsonPoint(lp.longitude).sign,
        position: jsonPoint(lp.longitude).position,
        house: lp.houseEffective,
        dignities: lp.essential.labels,
        debilities: lp.essential.debilities,
        essential_score: lp.essential.score,
        accidental_score: lp.accidental.score,
        retrograde: lp.retrograde,
        solar_phase: lp.solarPhase.state,
      },
    };
  });

  const jsonAlmuten = (alm: AlmutenResult) => ({
    almuten: alm.almuten,
    almuten_tie: alm.almuten_tie,
    almuten_candidates: alm.candidates,
    almuten_tie_break: alm.tie_break,
    almuten_scores: alm.scores,
  });

  const planetJson = (p: PlanetState) => {
    const codes = new Set(p.accidental.items.map((it) => it.code));
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
        mutual_receptions: p.essential.mutual_receptions,
        score: p.essential.score,
        score_note: p.essential.score_note,
        rulers_of_position: p.essential.rulers,
        triplicity_rulers: p.essential.triplicity_rulers,
        term_audit: p.essential.term_audit,
      },
      accidental_dignity: {
        score: p.accidental.score,
        items: p.accidental.items.map((it) => ({
          code: it.code, points: it.points, label_ja: it.label_ja,
        })),
        solar_phase: p.solarPhase.state,
        distance_from_sun: p.solarPhase.distance,
        cazimi: p.solarPhase.state === "cazimi",
        combust: p.solarPhase.state === "combust",
        under_beams: p.solarPhase.state === "under_beams",
        free_of_beams: p.solarPhase.state === "free",
        orientality: p.orientality,
        motion: codes.has("swift") ? "swift" : "slow",
      },
      sect: {
        planet_sect: p.sect,
        in_sect: p.inSect,
        hayz: p.hayz,
      },
      total_score: p.totalScore,
      antiscion: jsonPoint(ant.antiscion),
      contra_antiscion: jsonPoint(ant.contraAntiscion),
    };
  };

  return {
    schema_version: "v1",
    generator: "traditionalchart-js 0.1.0",
    birth_data: {
      year: input.year,
      month: input.month,
      day: input.day,
      hour: input.hour,
      minute: input.minute,
      tz_offset: tzOffset,
      latitude: lat,
      longitude: geoLon,
      julian_day_ut: roundTo(jd, 8),
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
      sources: TABLE_SOURCES,
      ephemeris: EPHEMERIS_LABEL,
    },
    sect: {
      method: sect.method,
      is_day: sect.is_day,
      chart_sect: sect.is_day ? "diurnal" : "nocturnal",
      sun_altitude: sect.sun_altitude === null ? null : roundTo(sect.sun_altitude, 4),
      altitude_is_day: sect.altitude_is_day,
      borderline: sect.borderline,
      moon_increasing_light: increasing,
      sect_light: {
        light,
        triplicity_lords: triplicityLords,
      },
    },
    planetary_day_hour: ph,
    angles: {
      ascendant: {
        ...jsonPoint(ascLon),
        lord: DOMICILE_BY_SIGN[signOf(ascLon)],
        ...jsonAlmuten(ascAlmuten),
      },
      midheaven: jsonPoint(mcLon),
    },
    planets: planets.map(planetJson),
    nodes: {
      used: "mean",
      mean: [
        nodeEntry(nodeLon, NODE_NAMES.node, nodeSpeed),
        nodeEntry(southNodeLon, NODE_NAMES.southNode, nodeSpeed),
      ],
      true: [
        nodeEntry(trueNodeLon, NODE_NAMES.node, trueNodeSpd),
        nodeEntry(trueSouthNodeLon, NODE_NAMES.southNode, trueNodeSpd),
      ],
    },
    lots: {
      fortune: {
        ...jsonPoint(fortuneLon),
        house: determineHouse(fortuneLon, cusps).house,
        lord: DOMICILE_BY_SIGN[signOf(fortuneLon)],
      },
      spirit: {
        ...jsonPoint(spiritLon),
        house: determineHouse(spiritLon, cusps).house,
        lord: DOMICILE_BY_SIGN[signOf(spiritLon)],
      },
    },
    prenatal_syzygy: syzygy
      ? {
        type: syzygy.type,
        datetime_local: formatSyzygyTime(syzygy.jd, tzOffset),
        ...jsonAlmuten(syzygyAlmuten as AlmutenResult),
        ...jsonPoint(syzygy.longitude),
      }
      : null,
    houses: housesJson,
    aspects: aspects.map((a) => ({
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
    })),
    almuten_figuris: {
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
      Object.entries(stars).map(([name, lon]) => [name, jsonPoint(lon)]),
    ),
    modern_reference: {
      note: "古典判断には用いない参考値 / not used in classical judgment",
      planets: modern.map((m) => ({
        ...jsonPoint(m.longitude),
        name: m.name,
        speed: roundTo(m.speed, 6),
        retrograde: m.speed < 0,
        house: m.placement.houseEffective,
      })),
    },
  };
}

function formatSyzygyTime(jd: number, tzOffset: number): string {
  // astro_calendar.format_date_file2 と同じ整形
  const ms = (jd - 2440587.5) * 86400000 + tzOffset * 3600000;
  const d = new Date(Math.round(ms));
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} `
    + `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

export { A as AstronomyEngine };
