/**
 * `vocation` ブロック（要件書 I-3。SKU 3）。
 *
 * 前提（決定 B）：このファイルは品位表を直接引かない。品位は dignity.ts の
 * 戻り値だけを見る。表引きが要るのは data/vocation_rules.json（組合せ表・サイン属性）と、
 * 体系差分のための監査表（dignity.ts に渡すだけ）に限る。
 *
 * 規則：古典職業鑑定マニュアル v11 §2・§4・§5・§6・§8 7-1
 *       ＋ 適職手順書_再基底化差分_20260918（決定 A〜D）
 */
import rules from "../data/vocation_rules.json" with { type: "json" };
import type { Condition } from "./derived.ts";
import {
  MOON_MOIETY_DEG, almutenOfDegree, dignityPoints, essentialDignity, houseAngularity,
  resolveAlmuten, triplicityRulers, withinMoonMoiety, type AlmutenResult, type EssentialDignity,
} from "./dignity.ts";
import {
  CAZIMI_ORB, COMBUST_ORB, DOMICILE_BY_SIGN, TERMS_TABLES, TRIPLICITY_TABLES,
  UNDER_BEAMS_ORB, type TriplicityRow,
} from "./tables.ts";
import { PLANET_NAMES, SIGN_FULL, degInSign, elementOf, signOf, signedSep } from "./util.ts";

export const CANDIDATES = ["Mars", "Venus", "Mercury"] as const;
export type Candidate = (typeof CANDIDATES)[number];

export const RULES_VERSION =
  "古典職業鑑定マニュアル v11 (2026-08-09) + 再基底化差分 2026-09-18 (決定 A・B) "
  + "+ 決定 C・D (2026-09-18/19)";

const RULE4_CITATION =
  "CA III l.7780 'within the mediety of her Orbs' — Moon's orb 12°30' halved; "
  + "candidate's moiety NOT added (手順書 v10 §2)";
const GENERAL_ORB_NOTE =
  "aspects[].max_orb (sum of moieties, CA I) is a different rule and is not used for rule 4";

const MALEFIC_ASPECTS = ["conjunction", "square", "opposition"];
const GOOD_ASPECTS = ["conjunction", "trine", "sextile"];
const RULE3_PRIORITY = ["conjunction", "trine", "sextile", "square", "opposition"];

/** 呼び出し側（index.ts）が渡す、計算済みの材料 */
export interface VocationSource {
  isDay: boolean;
  tripTable: Record<string, TriplicityRow>;
  planets: {
    name: string;
    longitude: number;
    sign: string;
    signIndex: number;
    position: string;
    house: number | null;
    houseRaw: number | null;
    nearNextCusp: boolean | null;
    retrograde: boolean;
    essential: EssentialDignity;
    accidentalScore: number | null;
    totalScore: number | null;
    solar: {
      state: string;
      distance: number;
      sameSign: boolean;
      orientality: "oriental" | "occidental" | null;
    };
  }[];
  aspects: {
    from: string;
    to: string;
    aspect: string;
    orb: number;
    partile: boolean;
    condition: string;
    direction: string;
    mutual_reception: boolean;
    reception_from_to: string[];
    reception_to_from: string[];
  }[];
  mcLongitude: number;
  ascLongitude: number;
  houses: { house: number; lord: string; signIndex: number }[];
  lots: { fortune: { lord: string }; spirit: { lord: string } };
  houseOf: Record<string, number | null>;
  conditionOf: (planet: string) => Condition;
  stars: Record<string, number>;
  weakestPlanet: string | null;
  moonLongitude: number;
  sunLongitude: number;
}

interface CandidateState {
  planet: Candidate;
  position: string;
  house: number | null;
  house_raw: number | null;
  near_next_cusp: boolean | null;
  essential: {
    dignities: string[];
    debilities: string[];
    score: number;
    has_dignity: boolean;
    peregrine: boolean | null;
    peregrine_cancelled_by: string | null;
  };
  solar: {
    distance_from_sun: number;
    same_sign_as_sun: boolean;
    cazimi: boolean;
    combust: boolean;
    under_beams: boolean;
    orientality: "oriental" | "occidental" | null;
  };
  angular: boolean | null;
  in_house_10_1_7: boolean | null;
  retrograde: boolean;
  malefic_afflictions: { by: string; aspect: string; orb: number; partile: boolean }[];
  moon_aspect: {
    aspect: string; orb: number; partile: boolean; within_moon_moiety: boolean;
    dissociate: boolean; direction: string;
  } | null;
  eligibility: Record<string, boolean>;
  eligibility_reasons: Record<string, string | null>;
}

const dms = (deg: number) => {
  const d = Math.floor(deg);
  const m = Math.round((deg - d) * 60);
  return `${d}°${String(m).padStart(2, "0")}'`;
};

/** 度数で成立していてもサイン関係が合わないアスペクト（ディソシエイト） */
function isDissociate(lonA: number, lonB: number, aspectAngle: number): boolean {
  const signDistance = ((signOf(lonB) - signOf(lonA)) % 12 + 12) % 12;
  const expected = Math.round(aspectAngle / 30);
  return signDistance !== expected && signDistance !== (12 - expected) % 12;
}

const ASPECT_ANGLE: Record<string, number> = {
  conjunction: 0, sextile: 60, square: 90, trine: 120, opposition: 180,
};

export function buildVocation(src: VocationSource): Record<string, unknown> {
  const planetOf = (name: string) => src.planets.find((p) => p.name === name)!;
  const mcSign = signOf(src.mcLongitude);
  const mcLord = DOMICILE_BY_SIGN[mcSign];

  // --- 候補星の状態 -------------------------------------------------------
  const candidates: CandidateState[] = CANDIDATES.map((name) => {
    const p = planetOf(name);
    const malefics = src.aspects
      .filter((a) => MALEFIC_ASPECTS.includes(a.aspect)
        && ((a.from === name && ["Saturn", "Mars"].includes(a.to))
          || (a.to === name && ["Saturn", "Mars"].includes(a.from))))
      .map((a) => ({
        by: a.from === name ? a.to : a.from,
        aspect: a.aspect,
        orb: a.orb,
        partile: a.partile,
      }));

    const moonAspects = src.aspects.filter((a) =>
      (a.from === name && a.to === "Moon") || (a.to === name && a.from === "Moon"));
    moonAspects.sort((x, y) => x.orb - y.orb);
    const closest = moonAspects[0];
    const moon_aspect = closest
      ? {
        aspect: closest.aspect,
        orb: closest.orb,
        partile: closest.partile,
        within_moon_moiety: withinMoonMoiety(closest.orb),
        dissociate: isDissociate(p.longitude, src.moonLongitude, ASPECT_ANGLE[closest.aspect]),
        direction: closest.direction,
      }
      : null;

    return {
      planet: name,
      position: p.position,
      house: p.house,
      house_raw: p.houseRaw,
      near_next_cusp: p.nearNextCusp,
      essential: {
        dignities: p.essential.labels,
        debilities: p.essential.debilities,
        score: p.essential.score,
        has_dignity: p.essential.has_dignity,
        peregrine: p.essential.peregrine,
        peregrine_cancelled_by: p.essential.peregrine_cancelled_by,
      },
      solar: {
        distance_from_sun: p.solar.distance,
        same_sign_as_sun: p.solar.sameSign,
        cazimi: p.solar.state === "cazimi",
        combust: p.solar.state === "combust",
        under_beams: p.solar.state === "under_beams",
        orientality: p.solar.orientality,
      },
      angular: p.house === null ? null : houseAngularity(p.house) === 3,
      in_house_10_1_7: p.house === null ? null : [10, 1, 7].includes(p.house),
      retrograde: p.retrograde,
      malefic_afflictions: malefics,
      moon_aspect,
      eligibility: {},
      eligibility_reasons: {},
    };
  });
  const candidateOf = (name: string) => candidates.find((c) => c.planet === name)!;

  // --- MC のアルムーテン ---------------------------------------------------
  const mcAlmutenAll = almutenOfDegree(src.mcLongitude, src.isDay, src.tripTable, src.houseOf);
  const threeScores: Record<string, number> = {};
  for (const name of CANDIDATES) {
    threeScores[name] = dignityPoints(src.mcLongitude, name, src.isDay, src.tripTable);
  }
  const angleProximity: Record<string, number> = {};
  const inSectMap: Record<string, boolean> = {};
  const dignityRank: Record<string, number> = {};
  for (const name of CANDIDATES) {
    const p = planetOf(name);
    dignityRank[name] = p.essential.score;
    angleProximity[name] = p.house === null ? Infinity : 3 - houseAngularity(p.house);
    inSectMap[name] = src.isDay ? name === "Mars" ? false : true : name === "Mars";
  }
  const threeResolved = resolveAlmuten(threeScores, {
    mode: "vocation_2b", houseOf: src.houseOf, dignityRank, angleProximity, inSect: inSectMap,
  });
  const winnerScore = threeResolved.almuten ? threeScores[threeResolved.almuten] : null;
  const mcAlmutenThree = {
    scores: threeScores,
    winner: threeResolved.almuten,
    tie: threeResolved.almuten_tie,
    tie_break_used: threeResolved.tie_break,
    winner_score: winnerScore,
    exaltation_or_better: winnerScore !== null && winnerScore >= 4,
  };

  // --- 選定ルール ①〜⑤ ----------------------------------------------------
  const reasons: Record<string, Record<string, string[]>> = {};
  const note = (planet: string, rule: string, codes: string[]) => {
    (reasons[planet] ??= {})[rule] = codes;
  };

  // ルール①
  const rule1 = candidates.filter((c) => {
    const codes: string[] = [];
    if (!c.in_house_10_1_7) codes.push("not_in_10_1_7");
    if (!c.essential.has_dignity) codes.push("no_essential_dignity");
    if (c.solar.combust) codes.push("combust");
    if (c.solar.under_beams) codes.push("under_beams");
    if (codes.length) note(c.planet, "1", codes);
    c.eligibility.rule1 = codes.length === 0;
    c.eligibility_reasons.rule1 = codes.length ? codes.join(", ") : null;
    return codes.length === 0;
  });

  // ルール②-A
  const rule2a = candidates.filter((c) => {
    const codes: string[] = [];
    if (c.planet !== mcLord) codes.push("not_mc_domicile_lord");
    if (!c.essential.has_dignity) codes.push("no_essential_dignity");
    if (c.essential.debilities.includes("fall")) codes.push("in_fall");
    if (codes.length) note(c.planet, "2A", codes);
    c.eligibility.rule2a = codes.length === 0;
    c.eligibility_reasons.rule2a = codes.length ? codes.join(", ") : null;
    return codes.length === 0;
  });

  // ルール②-B
  const rule2b = candidates.filter((c) => {
    const codes: string[] = [];
    if (mcAlmutenThree.winner !== c.planet) codes.push("not_mc_almuten_three");
    else if ((winnerScore ?? 0) < 4) codes.push("score_below_4");
    if (!c.essential.has_dignity) codes.push("no_essential_dignity");
    if (codes.length) note(c.planet, "2B", codes);
    c.eligibility.rule2b = codes.length === 0;
    c.eligibility_reasons.rule2b = codes.length ? codes.join(", ") : null;
    return codes.length === 0;
  });

  // ルール③（決定 D のパーティル）
  const rule3 = candidates.filter((c) => {
    const ok = !!c.moon_aspect && c.moon_aspect.partile;
    if (!ok) note(c.planet, "3", ["no_partile_moon_aspect"]);
    c.eligibility.rule3 = ok;
    c.eligibility_reasons.rule3 = ok ? null : "no_partile_moon_aspect";
    return ok;
  });

  // ルール④（月のモイエティ 6°15′。凶星から合・矩・衝で傷つけられていないこと）
  const rule4 = candidates.filter((c) => {
    const codes: string[] = [];
    if (!c.moon_aspect || !c.moon_aspect.within_moon_moiety) codes.push("outside_moon_moiety");
    if (c.malefic_afflictions.length) codes.push("afflicted_by_malefic");
    if (codes.length) note(c.planet, "4", codes);
    c.eligibility.rule4 = codes.length === 0;
    c.eligibility_reasons.rule4 = codes.length ? codes.join(", ") : null;
    return codes.length === 0;
  });

  // ルール⑤（プトレマイオス法）
  const orientalCandidates = candidates
    .filter((c) => c.solar.orientality === "oriental")
    .sort((a, b) => a.solar.distance_from_sun - b.solar.distance_from_sun);
  const risingBeforeSun = orientalCandidates.length ? orientalCandidates[0].planet : null;
  const mcOccupants = src.planets
    .filter((p) => p.house === 10).map((p) => p.name);
  const mcLordOrOccupant = [...new Set([mcLord, ...mcOccupants])];
  const ptolemyCandidates = CANDIDATES.filter((n) => mcLordOrOccupant.includes(n));
  const agree = risingBeforeSun !== null && ptolemyCandidates.includes(risingBeforeSun);
  const ptolemyResult = agree ? risingBeforeSun
    : (risingBeforeSun ?? (ptolemyCandidates.length === 1 ? ptolemyCandidates[0] : null));
  const rule5 = candidates.filter((c) => {
    const ok = ptolemyResult === c.planet;
    if (!ok) note(c.planet, "5", ["ptolemy_no_candidate"]);
    c.eligibility.rule5 = ok;
    c.eligibility_reasons.rule5 = ok ? null : "ptolemy_no_candidate";
    return ok;
  });

  // --- どのルールが発火したか ---------------------------------------------
  const RULE_LABELS: Record<string, string> = {
    "1": "Candidate in house 10, 1 or 7 with its own essential dignity, not combust and not under the beams",
    "2A": "Domicile lord of the MC sign with its own essential dignity, not in fall",
    "2B": "MC-degree almuten restricted to Mars/Venus/Mercury (project extension)",
    "3": "Partile aspect to the Moon",
    "4": "Aspect within the Moon's moiety (6°15'), unafflicted by a malefic",
    "5": "Ptolemy's method (rising before the Sun / lord or occupant of the MC)",
  };
  const stages: [string, CandidateState[]][] = [
    ["1", rule1], ["2A", rule2a], ["2B", rule2b], ["3", rule3], ["4", rule4], ["5", rule5],
  ];
  const fired = stages.find(([, list]) => list.length > 0);
  const ruleFired = fired ? fired[0] : null;
  const qualified = fired ? fired[1] : [];

  let significatorPlanet: string | null = null;
  let tie = false;
  let multipleQualified: string[] = [];
  if (qualified.length === 1) {
    significatorPlanet = qualified[0].planet;
  } else if (qualified.length > 1) {
    multipleQualified = qualified.map((c) => c.planet);
    if (ruleFired === "3") {
      // 合 → トライン → セクスタイル → スクエア → オポジション、次に orb 小、次に sinister
      const sorted = [...qualified].sort((a, b) => {
        const pa = RULE3_PRIORITY.indexOf(a.moon_aspect!.aspect);
        const pb = RULE3_PRIORITY.indexOf(b.moon_aspect!.aspect);
        if (pa !== pb) return pa - pb;
        if (a.moon_aspect!.orb !== b.moon_aspect!.orb) {
          return a.moon_aspect!.orb - b.moon_aspect!.orb;
        }
        const da = a.moon_aspect!.direction === "sinister" ? 0 : 1;
        const db = b.moon_aspect!.direction === "sinister" ? 0 : 1;
        return da - db;
      });
      significatorPlanet = sorted[0].planet;
    } else {
      // ①・②-A ほかは total_score 最高（プロジェクト慣行）。同点は tie
      const scored = qualified.map((c) => ({
        planet: c.planet, score: planetOf(c.planet).totalScore ?? planetOf(c.planet).essential.score,
      })).sort((a, b) => b.score - a.score);
      if (scored.length > 1 && scored[0].score === scored[1].score) {
        tie = true;
        significatorPlanet = null;
      } else {
        significatorPlanet = scored[0].planet;
      }
    }
  }

  const excluded = candidates
    .filter((c) => c.planet !== significatorPlanet)
    .map((c) => {
      const failedRule = ["1", "2A", "2B", "3", "4", "5"]
        .find((r) => reasons[c.planet]?.[r]?.length);
      if (!failedRule) return null;
      const codes = reasons[c.planet][failedRule];
      let value: string | null = null;
      if (codes.includes("combust") || codes.includes("under_beams")) {
        value = dms(c.solar.distance_from_sun);
      } else if (codes.includes("score_below_4")) {
        value = String(mcAlmutenThree.scores[c.planet]);
      }
      return {
        planet: c.planet,
        rule: failedRule,
        reason: codes,
        value,
        debilities: c.essential.debilities,
      };
    })
    .filter((x): x is NonNullable<typeof x> => x !== null);

  const settlementTier = ruleFired === null ? null
    : (["1", "2A"].includes(ruleFired) ? "A" : ruleFired === "2B" ? "B" : "C");

  // 主星以外で、太陽による排除（燃焼・光線下）を受けていない候補。
  // excluded[] は監査用でこの判定には使わない（要件書 I-3-4、Phase 4 報告 b）
  const notExcluded = CANDIDATES.filter((n) => {
    if (n === significatorPlanet) return false;
    const c = candidateOf(n);
    return !c.solar.combust && !c.solar.under_beams;
  });

  const significator = {
    planet: significatorPlanet,
    rule_fired: ruleFired,
    rule_label: ruleFired ? RULE_LABELS[ruleFired] : "no rule settled the significator",
    basis: significatorPlanet
      ? {
        has_dignity: candidateOf(significatorPlanet).essential.has_dignity,
        dignities: candidateOf(significatorPlanet).essential.dignities,
        almuten_score: ruleFired === "2B" ? winnerScore : null,
        competitors: ruleFired === "2B"
          ? Object.fromEntries(Object.entries(mcAlmutenThree.scores)
            .filter(([n]) => n !== significatorPlanet))
          : {},
        tie_break_used: ruleFired === "2B" ? mcAlmutenThree.tie_break_used : null,
      }
      : {},
    excluded,
    multiple_qualified: multipleQualified,
    citations: ["CA III pp.140–141 ll.7766–7802", "Bonatti Liber Astronomiae ch.XV (almuten concept)"],
    extension_flag: ruleFired === "2B",
    notes: [
      "rule 3 priority order and rule 4 affliction orb are project conventions",
      "rule 3 uses decision D (partile = same degree)",
    ],
    tie,
  };

  // --- 併記する別系統 ------------------------------------------------------
  const h10 = src.houses.find((h) => h.house === 10)!;
  const h10Lord = h10.lord;
  const h10Occupants = src.planets.filter((p) => p.house === 10).map((p) => p.name);
  const goodAspectToH10Lord = CANDIDATES.filter((n) => src.aspects.some((a) =>
    GOOD_ASPECTS.includes(a.aspect)
    && ((a.from === n && a.to === h10Lord) || (a.to === n && a.from === h10Lord))));
  const coleyResult: string[] = [...new Set<string>([
    ...CANDIDATES.filter((n) => h10Occupants.includes(n)),
    ...goodAspectToH10Lord,
  ])];

  // --- 結合・不在・特殊条件 -------------------------------------------------
  const combos = rules.combinations as { rule_key: string; pair: string[]; citation: string }[];
  const aspectBetween = (a: string, b: string) => src.aspects.find((x) =>
    (x.from === a && x.to === b) || (x.from === b && x.to === a));
  const combinations: Record<string, unknown>[] = [];
  const absent: Record<string, unknown>[] = [];
  for (const combo of combos) {
    if (!significatorPlanet || !combo.pair.includes(significatorPlanet)) continue;
    const others = combo.pair.filter((n) => n !== significatorPlanet);
    const found = others.map((o) => aspectBetween(significatorPlanet, o));
    if (found.every((f) => f !== undefined)) {
      const first = found[0]!;
      const other = others[0];
      combinations.push({
        pair: combo.pair,
        aspect: first.aspect,
        orb: first.orb,
        applying: first.condition === "applying",
        partile: first.partile,
        same_sign: signOf(planetOf(significatorPlanet).longitude)
          === signOf(planetOf(other).longitude),
        rule_key: combo.rule_key,
        citation: combo.citation,
      });
    } else {
      absent.push({ pair: combo.pair, rule_key: combo.rule_key, citation: combo.citation });
    }
  }

  const mercury = planetOf("Mercury");
  const venus = planetOf("Venus");
  const mars = planetOf("Mars");
  const mercuryMarsGood = src.aspects.some((a) =>
    GOOD_ASPECTS.includes(a.aspect)
    && ((a.from === "Mercury" && a.to === "Mars") || (a.to === "Mercury" && a.from === "Mars")));
  const mercuryMoonAspect = aspectBetween("Mercury", "Moon");
  const mercurySign = SIGN_FULL[signOf(mercury.longitude)];
  const specialConditions = {
    mercury_yields_to_mars: significatorPlanet === "Mercury" && mercuryMarsGood,
    mercury_retro_conj_venus_same_sign: mercury.retrograde
      && signOf(mercury.longitude) === signOf(venus.longitude)
      && aspectBetween("Mercury", "Venus")?.aspect === "conjunction",
    mercury_moon_by_sign: (["Virgo", "Scorpio"].includes(mercurySign) && mercuryMoonAspect)
      ? { sign: mercurySign, applying: mercuryMoonAspect.condition === "applying" }
      : null,
    venus_combust: venus.solar.state === "combust",
    venus_cazimi: venus.solar.state === "cazimi",
    mars_with_saturn: !!src.aspects.find((a) =>
      a.aspect === "conjunction"
      && ((a.from === "Mars" && a.to === "Saturn") || (a.to === "Mars" && a.from === "Saturn"))),
    mercury_jupiter_aspect: !!aspectBetween("Mercury", "Jupiter"),
  };

  // --- サイン属性 ----------------------------------------------------------
  const attrs = rules.sign_attributes as any;
  const signAttributes = significatorPlanet
    ? (() => {
      const sign = SIGN_FULL[signOf(planetOf(significatorPlanet).longitude)];
      const mode = (["movable", "fixed", "common"] as const)
        .find((m) => attrs.modes[m].includes(sign))!;
      return {
        sign,
        element: elementOf(signOf(planetOf(significatorPlanet).longitude)),
        mode: mode === "movable" ? "cardinal" : mode === "common" ? "mutable" : "fixed",
        humane: attrs.humane.includes(sign),
        four_footed: attrs.four_footed.includes(sign),
        water_or_earth_group: attrs.water_or_earth_group.includes(sign),
        voice: null,
        note: "attributes only; the selection of professions belongs to the prompt (LEXICON)",
      };
    })()
    : null;

  // --- 成功度 --------------------------------------------------------------
  const success = significatorPlanet
    ? (() => {
      const c = candidateOf(significatorPlanet);
      const partileMalefic = c.malefic_afflictions.filter((m) => m.partile);
      const conditions = {
        strong_essential: c.essential.score >= 3,
        not_afflicted_partile_malefic: partileMalefic.length === 0,
        angular: c.angular === true,
        oriental: c.solar.orientality === "oriental",
      };
      const met = Object.values(conditions).filter(Boolean).length;
      return {
        conditions,
        conditions_met: met,
        of: 4,
        grade: met === 4 ? "high" : met >= 2 ? "mid" : "low",
        malefic_afflictions: partileMalefic,
        citation: "CA III pp.146–147 ll.7964–7981",
      };
    })()
    : null;

  // --- 補助の場所 ----------------------------------------------------------
  const lordOfHouse = (house: number) => src.houses.find((h) => h.house === house)!.lord;
  const auxiliary = {
    h10: src.conditionOf(lordOfHouse(10)),
    h2: src.conditionOf(lordOfHouse(2)),
    h6: src.conditionOf(lordOfHouse(6)),
    h11: src.conditionOf(lordOfHouse(11)),
    fortune: src.conditionOf(src.lots.fortune.lord),
    spirit: src.conditionOf(src.lots.spirit.lord),
    moon: src.conditionOf("Moon"),
    sun: src.conditionOf("Sun"),
  };

  // --- 在住サインの支配星（dispositors） -----------------------------------
  const dispositors = CANDIDATES.map((n) =>
    src.conditionOf(DOMICILE_BY_SIGN[signOf(planetOf(n).longitude)]));

  // --- 恒星（候補星と最弱天体。v1 の 3 星のみ） ----------------------------
  const STAR_ORB = 2.0;        // 参考の上限
  const STAR_JUDGING_ORB = 1.0; // 判定用の上限
  const starBodies = [...new Set([...CANDIDATES, ...(src.weakestPlanet ? [src.weakestPlanet] : [])])];
  const fixedStars: Record<string, unknown>[] = [];
  for (const [star, starLon] of Object.entries(src.stars)) {
    for (const body of starBodies) {
      const orb = Math.abs(signedSep(planetOf(body).longitude, starLon));
      if (orb <= STAR_ORB) {
        fixedStars.push({
          star,
          body,
          orb: Math.round(orb * 100) / 100,
          orb_dms: dms(orb),
          grade: orb <= STAR_JUDGING_ORB ? "judging" : "reference",
          body_is_weakest: body === src.weakestPlanet,
        });
      }
    }
  }

  // --- 警告（機械判定 4 種のみ） -------------------------------------------
  const warningCitations = rules.warning_citations as Record<string, string[]>;
  const warnings: { id: string; citations: string[] }[] = [];
  if (!specialConditions.mercury_jupiter_aspect) {
    warnings.push({ id: "mercury_jupiter_no_aspect",
      citations: warningCitations.mercury_jupiter_no_aspect });
  }
  if (specialConditions.venus_combust) {
    warnings.push({ id: "venus_combust_no_profession",
      citations: warningCitations.venus_combust_no_profession });
  }
  if (specialConditions.mars_with_saturn) {
    warnings.push({ id: "mars_saturn_loses_rule",
      citations: warningCitations.mars_saturn_loses_rule });
  }
  if (specialConditions.mercury_yields_to_mars) {
    warnings.push({ id: "mercury_yields_to_mars",
      citations: warningCitations.mercury_yields_to_mars });
  }

  // --- durability_layer（得点に算入しない） --------------------------------
  const mcElement = elementOf(mcSign);
  const trip = triplicityRulers(mcSign, src.tripTable);
  const ordered = src.isDay
    ? [{ role: "day", planet: trip.day }, { role: "night", planet: trip.night },
      { role: "participating", planet: trip.participating }]
    : [{ role: "night", planet: trip.night }, { role: "day", planet: trip.day },
      { role: "participating", planet: trip.participating }];
  const durability = {
    verified: false,
    note: "Bonatti ll.3012–3016 via Dorotheus I.1 ordered triplicity; NOT added to any score",
    mc_sign: SIGN_FULL[mcSign],
    element: mcElement,
    lords: ordered.filter((o) => o.planet).map((o, index) => {
      const p = planetOf(o.planet as string);
      return {
        rank: index + 1,
        role: o.role,
        planet: o.planet,
        house: p.house,
        essential_score: p.essential.score,
        accidental_score: p.accidentalScore,
        retrograde: p.retrograde,
        combust: p.solar.state === "combust",
        malefic_afflictions: src.aspects
          .filter((a) => MALEFIC_ASPECTS.includes(a.aspect)
            && ((a.from === o.planet && ["Saturn", "Mars"].includes(a.to))
              || (a.to === o.planet && ["Saturn", "Mars"].includes(a.from))))
          .map((a) => ({
            by: a.from === o.planet ? a.to : a.from,
            aspect: a.aspect, orb: a.orb, partile: a.partile,
          })),
      };
    }),
  };

  // --- 体系差分（プトレマイオス式の監査表で並行計算） ----------------------
  const auditTrip = TRIPLICITY_TABLES.lilly;
  const auditTerms = TERMS_TABLES.ptolemaic_lilly;
  const auditEssential = (name: string) => essentialDignity(
    planetOf(name).longitude, name, src.isDay,
    { tripTable: auditTrip, termTable: auditTerms },
  );
  const auditScores: Record<string, number> = {};
  for (const name of CANDIDATES) {
    const ed = essentialDignity(src.mcLongitude, name, src.isDay,
      { tripTable: auditTrip, termTable: auditTerms });
    auditScores[name] = ed.labels.reduce((sum, key) =>
      sum + ({ domicile: 5, exaltation: 4, triplicity: 3, term: 2, face: 1 }[key] ?? 0), 0);
  }
  const auditWinner = resolveAlmuten(auditScores, {
    mode: "vocation_2b", houseOf: src.houseOf, dignityRank, angleProximity, inSect: inSectMap,
  });
  const differences: Record<string, unknown>[] = [];
  for (const name of CANDIDATES) {
    const operative = planetOf(name).essential;
    const audit = auditEssential(name);
    if (operative.rulers.term !== audit.rulers.term) {
      differences.push({
        field: `candidates.${name}.term_ruler`,
        operative: operative.rulers.term,
        ptolemaic: audit.rulers.term,
        level: 1,
        note: `${name} at ${planetOf(name).position}`,
      });
    }
    if (operative.has_dignity !== audit.has_dignity) {
      differences.push({
        field: `candidates.${name}.has_dignity`,
        operative: operative.has_dignity,
        ptolemaic: audit.has_dignity,
        level: 2,
        note: "the eligibility of rules 1 and 2A depends on this",
      });
    } else if (operative.score !== audit.score) {
      differences.push({
        field: `candidates.${name}.essential_score`,
        operative: operative.score,
        ptolemaic: audit.score,
        level: 1,
        note: "score only; the rules use has_dignity",
      });
    }
  }
  if (auditWinner.almuten !== mcAlmutenThree.winner) {
    differences.push({
      field: "mc_almuten_three.winner",
      operative: mcAlmutenThree.winner,
      ptolemaic: auditWinner.almuten,
      level: 2,
      note: "rule 2B would fire for a different candidate",
    });
  }
  const divergenceLevel = differences.length
    ? Math.max(...differences.map((d) => d.level as number)) : 0;
  const systemDivergence = {
    level: divergenceLevel,
    compared_against: {
      bounds: "ptolemaic",
      triplicity: "ptolemaic",
      source: "体系差分検出_実装仕様_20260808.md §5.3（tables_used.sources.triplicity_audit）",
    },
    differences,
    significator_ptolemaic: null as string | null,
    settlement_tier_ptolemaic: null as string | null,
  };

  // --- 適職固有の境界警告 --------------------------------------------------
  const boundaryWarnings: Record<string, unknown>[] = [];
  for (const c of candidates) {
    if (Math.abs(c.solar.distance_from_sun - COMBUST_ORB) <= 0.5 && c.solar.same_sign_as_sun) {
      boundaryWarnings.push({
        id: "combust_boundary", level: 2, target: c.planet,
        value: c.solar.distance_from_sun, threshold: COMBUST_ORB,
        message_en: `${c.planet} is within half a degree of the combustion limit (8°30').`,
      });
    }
    if (Math.abs(c.solar.distance_from_sun - UNDER_BEAMS_ORB) <= 0.5 && c.solar.same_sign_as_sun) {
      boundaryWarnings.push({
        id: "under_beams_boundary", level: 2, target: c.planet,
        value: c.solar.distance_from_sun, threshold: UNDER_BEAMS_ORB,
        message_en: `${c.planet} is within half a degree of the limit of the Sun's beams (17°).`,
      });
    }
    if (c.moon_aspect && Math.abs(c.moon_aspect.orb - MOON_MOIETY_DEG) <= 0.5) {
      boundaryWarnings.push({
        id: "rule4_boundary", level: 2, target: c.planet,
        value: c.moon_aspect.orb, threshold: MOON_MOIETY_DEG,
        message_en: `${c.planet} is within half a degree of the Moon's moiety (6°15').`,
      });
    }
    if (c.near_next_cusp) {
      boundaryWarnings.push({
        id: "planet_near_cusp", level: 2, target: c.planet,
        value: null, threshold: 5,
        message_en: `${c.planet} is a vocational candidate within 5° of the next cusp.`,
      });
    }
  }
  if (significatorPlanet === null) {
    boundaryWarnings.push({
      id: "no_significator", level: 3, target: "significator", value: null, threshold: null,
      message_en: "No rule settled the vocational significator; a human review is required.",
    });
  }
  if (divergenceLevel >= 2) {
    boundaryWarnings.push({
      id: "system_divergence", level: divergenceLevel, target: "vocation",
      value: divergenceLevel, threshold: 2,
      message_en: "The Ptolemaic audit tables would change the vocational judgement.",
    });
  }

  return {
    rules_version: RULES_VERSION,
    thresholds: {
      combust_deg: COMBUST_ORB,
      under_beams_deg: UNDER_BEAMS_ORB,
      cazimi_deg: Math.round(CAZIMI_ORB * 10000) / 10000,
      rule4_moiety_deg: MOON_MOIETY_DEG,
      rule4_citation: RULE4_CITATION,
      general_orb_note: GENERAL_ORB_NOTE,
    },
    candidates,
    mc_almuten_all: {
      almuten: mcAlmutenAll.almuten,
      almuten_tie: mcAlmutenAll.almuten_tie,
      almuten_candidates: mcAlmutenAll.candidates,
      almuten_tie_break: mcAlmutenAll.tie_break,
      almuten_scores: mcAlmutenAll.scores,
    },
    mc_almuten_three: mcAlmutenThree,
    significator,
    settlement_tier: settlementTier,
    not_excluded: notExcluded,
    ptolemy_method: {
      rising_before_sun: risingBeforeSun,
      mc_lord_or_occupant: mcLordOrOccupant,
      agree,
      result: ptolemyResult,
    },
    coley_method: {
      h10_cusp_sign: SIGN_FULL[src.houses.find((h) => h.house === 10)!.signIndex],
      h10_lord: h10Lord,
      h10_occupants: h10Occupants,
      candidates_in_h10: CANDIDATES.filter((n) => h10Occupants.includes(n)),
      candidates_good_aspect_to_h10_lord: goodAspectToH10Lord,
      result: coleyResult.length ? coleyResult : [h10Lord],
      agrees_with_lilly: significatorPlanet !== null && coleyResult.includes(significatorPlanet),
    },
    anima_124: {
      h10_lord: h10Lord,
      asc_lord: DOMICILE_BY_SIGN[signOf(src.ascLongitude)],
      note: "reference only (Anima Astrologiae 124)",
    },
    combinations,
    absent_combinations: absent,
    special_conditions: specialConditions,
    sign_attributes: signAttributes,
    success,
    auxiliary,
    dispositors,
    fixed_stars: fixedStars,
    warnings,
    durability_layer: durability,
    system_divergence: systemDivergence,
    boundary_warnings: boundaryWarnings,
    timing_slice: null,
  };
}
