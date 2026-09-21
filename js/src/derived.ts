/**
 * `derived` ブロック（要件書 I-2）。
 * ここに解釈語は入れない。値はすべて planets[]・houses[]・aspects[]・lots から
 * 再計算できる（GT-3 がそれを検証する）。
 */
import { houseAngularity } from "./dignity.ts";
import { isInJoy } from "./joys.ts";
import { BENEFICS, MALEFICS } from "./tables.ts";
import { PLANET_NAMES, signOf } from "./util.ts";

export const THRESHOLDS = {
  favoured: { essential_min: 3, accidental_min: 5 },
  effort: { essential_max: -4, accidental_max: 0 },
  status: "provisional (METHOD_natal_v1 決定 5; review after 3 test charts)",
} as const;

/** アバージョン（見えない関係）＝ サイン差が 1・5・7・11 */
export const AVERSION_DISTANCES = [1, 5, 7, 11];

export type HouseClass = "angular" | "succedent" | "cadent";
export type Classification = "favoured" | "neutral" | "effort";

export interface AspectContact {
  by: string;
  aspect: string;
  orb: number;
  partile: boolean;
  reception_softens: boolean;
}

export interface Condition {
  planet: string;
  sign: string;
  position: string;
  house: number | null;
  house_class: HouseClass | null;
  essential_score: number;
  accidental_score: number | null;
  total_score: number | null;
  dignities: string[];
  debilities: string[];
  peregrine: boolean | null;
  peregrine_cancelled_by: string | null;
  retrograde: boolean;
  solar_phase: string;
  in_sect: boolean | null;
  afflicted_by: AspectContact[];
  assisted_by: AspectContact[];
  classification: Classification;
}

export interface RankingRow {
  rank: number;
  planet: string;
  total_score: number | null;
  essential_score: number;
  accidental_score: number | null;
  house: number | null;
  house_class: HouseClass | null;
  tie: boolean;
}

export interface RankingExtreme {
  planet: string | null;
  total_score: number | null;
  essential_score: number | null;
  tie: boolean;
  co: string[];
}

/** derived を組み立てるために必要な、既に計算済みの材料 */
export interface DerivedInput {
  mode: "full" | "time_unknown";
  isDay: boolean | null;
  planets: {
    name: string;
    sign: string;
    position: string;
    house: number | null;
    essential_score: number;
    accidental_score: number | null;
    total_score: number | null;
    dignities: string[];
    debilities: string[];
    peregrine: boolean | null;
    peregrine_cancelled_by: string | null;
    retrograde: boolean;
    solar_phase: string;
    in_sect: boolean | null;
    sign_index: number;
  }[];
  aspects: {
    from: string;
    to: string;
    aspect: string;
    orb: number;
    partile: boolean;
    reception_softens: boolean;
  }[];
  houses: { house: number; lord: string; sign_index: number }[] | null;
  ascendant: { sign_index: number; lord: string; almuten: string | null } | null;
  lots: { fortune_lord: string; spirit_lord: string } | null;
  almutens: string[];
  almutenFigurisScore: number | null;
}

export interface Derived {
  mode: "full" | "time_unknown";
  ranking_basis: "total_score" | "essential_score";
  dignity_ranking: RankingRow[];
  strongest_planet: RankingExtreme;
  weakest_planet: RankingExtreme;
  lord_of_geniture: {
    primary: string[];
    primary_basis: "almuten_figuris";
    primary_tie: boolean;
    secondary: string | null;
    secondary_basis: "total_score";
  };
  sect_light_condition: Condition | null;
  asc_lord_condition: (Condition & { co_significator: Condition | null }) | null;
  lot_lords_condition: { fortune: Condition; spirit: Condition } | null;
  out_of_sect_malefic: Condition | null;
  in_sect_benefic: Condition | null;
  house_conditions: {
    house: number;
    lord: string;
    lord_house: number | null;
    essential_score: number;
    accidental_score: number | null;
    classification: Classification;
    lord_in_aversion: boolean;
  }[] | null;
  aversions_to_ascendant: string[] | null;
  joys: { planet: string; house: number; essential_score: number; total_score: number }[] | null;
  reading_order: string[];
  thresholds: typeof THRESHOLDS;
}

export function houseClassOf(house: number | null): HouseClass | null {
  if (house == null) return null;
  const rank = houseAngularity(house);
  return rank === 3 ? "angular" : rank === 2 ? "succedent" : "cadent";
}

export function classify(essential: number, accidental: number | null): Classification {
  if (accidental === null) return "neutral";
  if (essential >= THRESHOLDS.favoured.essential_min
    && accidental >= THRESHOLDS.favoured.accidental_min) return "favoured";
  if (essential <= THRESHOLDS.effort.essential_max
    && accidental <= THRESHOLDS.effort.accidental_max) return "effort";
  return "neutral";
}

/** サイン差が 1・5・7・11 なら互いに見えない（決定 10） */
export function inAversion(signA: number, signB: number): boolean {
  return AVERSION_DISTANCES.includes(((signA - signB) % 12 + 12) % 12);
}

const AFFLICTING_ASPECTS = ["conjunction", "square", "opposition"];
const ASSISTING_ASPECTS = ["conjunction", "trine", "sextile"];

function contactsFor(
  planet: string, input: DerivedInput, from: string[], aspects: string[],
): AspectContact[] {
  const out: AspectContact[] = [];
  for (const a of input.aspects) {
    if (!aspects.includes(a.aspect)) continue;
    const other = a.from === planet ? a.to : a.to === planet ? a.from : null;
    if (other === null || !from.includes(other)) continue;
    out.push({
      by: other,
      aspect: a.aspect,
      orb: a.orb,
      partile: a.partile,
      reception_softens: a.reception_softens,
    });
  }
  return out;
}

export function conditionOf(planet: string, input: DerivedInput): Condition {
  const p = input.planets.find((x) => x.name === planet)!;
  return {
    planet: p.name,
    sign: p.sign,
    position: p.position,
    house: p.house,
    house_class: houseClassOf(p.house),
    essential_score: p.essential_score,
    accidental_score: p.accidental_score,
    total_score: p.total_score,
    dignities: p.dignities,
    debilities: p.debilities,
    peregrine: p.peregrine,
    peregrine_cancelled_by: p.peregrine_cancelled_by,
    retrograde: p.retrograde,
    solar_phase: p.solar_phase,
    in_sect: p.in_sect,
    afflicted_by: contactsFor(planet, input, MALEFICS, AFFLICTING_ASPECTS),
    assisted_by: contactsFor(planet, input, BENEFICS, ASSISTING_ASPECTS),
    classification: classify(p.essential_score, p.accidental_score),
  };
}

export function buildDerived(input: DerivedInput): Derived {
  const timeUnknown = input.mode === "time_unknown";
  const basis: "total_score" | "essential_score" = timeUnknown ? "essential_score" : "total_score";
  const scoreOf = (name: string) => {
    const p = input.planets.find((x) => x.name === name)!;
    return (timeUnknown ? p.essential_score : p.total_score) ?? p.essential_score;
  };

  // --- dignity_ranking：得点降順、同点はハウス位置、なお同点なら同じ rank で tie ---
  const sorted = [...PLANET_NAMES].sort((a, b) => {
    const d = scoreOf(b) - scoreOf(a);
    if (d !== 0) return d;
    const pa = input.planets.find((x) => x.name === a)!;
    const pb = input.planets.find((x) => x.name === b)!;
    return houseAngularity(pb.house) - houseAngularity(pa.house);
  });
  const dignity_ranking: RankingRow[] = [];
  sorted.forEach((name, index) => {
    const p = input.planets.find((x) => x.name === name)!;
    const prev = index > 0 ? input.planets.find((x) => x.name === sorted[index - 1])! : null;
    const tiedWithPrev = prev !== null
      && scoreOf(prev.name) === scoreOf(name)
      && houseAngularity(prev.house) === houseAngularity(p.house);
    const next = index + 1 < sorted.length
      ? input.planets.find((x) => x.name === sorted[index + 1])! : null;
    const tiedWithNext = next !== null
      && scoreOf(next.name) === scoreOf(name)
      && houseAngularity(next.house) === houseAngularity(p.house);
    dignity_ranking.push({
      rank: tiedWithPrev ? dignity_ranking[index - 1].rank : index + 1,
      planet: name,
      total_score: timeUnknown ? null : p.total_score,
      essential_score: p.essential_score,
      accidental_score: p.accidental_score,
      house: p.house,
      house_class: houseClassOf(p.house),
      tie: tiedWithPrev || tiedWithNext,
    });
  });

  const extreme = (rows: RankingRow[], pick: "first" | "last"): RankingExtreme => {
    const target = pick === "first" ? rows[0] : rows[rows.length - 1];
    const score = scoreOf(target.planet);
    const co = rows.filter((r) => r.planet !== target.planet && scoreOf(r.planet) === score)
      .map((r) => r.planet);
    return {
      planet: target.planet,
      total_score: target.total_score,
      essential_score: target.essential_score,
      tie: co.length > 0,
      co,
    };
  };
  const strongest = extreme(dignity_ranking, "first");
  const weakest = extreme(dignity_ranking, "last");

  const conditionFor = (name: string | null | undefined): Condition | null =>
    (!timeUnknown && name ? conditionOf(name, input) : null);

  const sectLight = input.isDay === null ? null : (input.isDay ? "Sun" : "Moon");
  const ascLordCondition = (() => {
    if (timeUnknown || !input.ascendant) return null;
    const base = conditionOf(input.ascendant.lord, input);
    const almuten = input.ascendant.almuten;
    return {
      ...base,
      co_significator: almuten && almuten !== input.ascendant.lord
        ? conditionOf(almuten, input) : null,
    };
  })();

  const houseConditions = (!timeUnknown && input.houses)
    ? input.houses.map((h) => {
      const lord = input.planets.find((x) => x.name === h.lord)!;
      return {
        house: h.house,
        lord: h.lord,
        lord_house: lord.house,
        essential_score: lord.essential_score,
        accidental_score: lord.accidental_score,
        classification: classify(lord.essential_score, lord.accidental_score),
        lord_in_aversion: inAversion(lord.sign_index, h.sign_index),
      };
    })
    : null;

  const aversions = (!timeUnknown && input.ascendant)
    ? input.planets.filter((p) => inAversion(p.sign_index, input.ascendant!.sign_index))
      .map((p) => p.name)
    : null;

  // --- joys（喜悦）。得点には入らない記述層。強い順に並べる ---
  // 判定は house（＝ 5°規則の適用後）で行う。並びは dignity_ranking と同じ総合点の降順、
  // 同点はハウス番号の小さい順。
  const joys = timeUnknown ? null : input.planets
    .filter((p) => isInJoy(p.name, p.house) === true)
    .map((p) => ({
      planet: p.name,
      house: p.house as number,
      essential_score: p.essential_score,
      total_score: p.total_score ?? p.essential_score,
    }))
    .sort((a, b) => (b.total_score - a.total_score) || (a.house - b.house));

  // --- reading_order（決定 12）。重複は先勝ち ---
  const order: string[] = [];
  const push = (name: string | null | undefined) => {
    if (name && !order.includes(name)) order.push(name);
  };
  push(sectLight);
  if (input.ascendant) {
    push(input.ascendant.lord);
    if (input.ascendant.almuten && input.ascendant.almuten !== input.ascendant.lord) {
      push(input.ascendant.almuten);
    }
  }
  for (const n of input.almutens) push(n);
  if (input.isDay !== null) push(input.isDay ? "Mars" : "Saturn");
  for (const row of dignity_ranking) push(row.planet);

  return {
    mode: input.mode,
    ranking_basis: basis,
    dignity_ranking,
    strongest_planet: strongest,
    weakest_planet: weakest,
    lord_of_geniture: {
      primary: input.almutens,
      primary_basis: "almuten_figuris",
      primary_tie: input.almutens.length > 1,
      secondary: strongest.planet,
      secondary_basis: "total_score",
    },
    sect_light_condition: conditionFor(sectLight),
    asc_lord_condition: ascLordCondition,
    lot_lords_condition: (!timeUnknown && input.lots)
      ? {
        fortune: conditionOf(input.lots.fortune_lord, input),
        spirit: conditionOf(input.lots.spirit_lord, input),
      }
      : null,
    out_of_sect_malefic: conditionFor(input.isDay === null ? null : (input.isDay ? "Mars" : "Saturn")),
    in_sect_benefic: conditionFor(input.isDay === null ? null : (input.isDay ? "Jupiter" : "Venus")),
    house_conditions: houseConditions,
    aversions_to_ascendant: aversions,
    joys,
    reading_order: order,
    thresholds: THRESHOLDS,
  };
}
