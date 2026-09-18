/**
 * GT-3：`derived` と `summary` を planets[]・houses[]・aspects[]・lots から
 * 独立に組み立て直し、出力と一致することを確かめる。
 * ここでは src/derived.ts を使わず、JSON だけを材料に素朴に計算する。
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { computeChart } from "../src/index.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(HERE, "golden", "manifest.json"), "utf8"));
const FIXED_TIME = "2026-09-19T00:00:00.000Z";

const ANGULAR = [1, 4, 7, 10];
const SUCCEDENT = [2, 5, 8, 11];
const angularity = (house: number | null) =>
  house === null ? 0 : ANGULAR.includes(house) ? 3 : SUCCEDENT.includes(house) ? 2 : 1;
const houseClass = (house: number | null) =>
  house === null ? null : ANGULAR.includes(house) ? "angular"
    : SUCCEDENT.includes(house) ? "succedent" : "cadent";
const classify = (essential: number, accidental: number | null) => {
  if (accidental === null) return "neutral";
  if (essential >= 3 && accidental >= 5) return "favoured";
  if (essential <= -4 && accidental <= 0) return "effort";
  return "neutral";
};
const aversion = (a: number, b: number) => [1, 5, 7, 11].includes(((a - b) % 12 + 12) % 12);

/** JSON だけから derived を組み立て直す（実装とは別経路） */
function recomputeDerived(doc: any) {
  const timeUnknown = !doc.birth_data.time_known;
  const score = (p: any) => (timeUnknown ? p.essential_dignity.score : p.total_score);
  const planets: any[] = doc.planets;
  const sorted = [...planets].sort((a, b) =>
    (score(b) - score(a)) || (angularity(b.house) - angularity(a.house)));

  const ranking = sorted.map((p, i) => {
    const prev = i > 0 ? sorted[i - 1] : null;
    const next = i + 1 < sorted.length ? sorted[i + 1] : null;
    const same = (x: any) => x !== null && score(x) === score(p)
      && angularity(x.house) === angularity(p.house);
    return {
      planet: p.name,
      tiedWithPrev: same(prev),
      tie: same(prev) || same(next),
      total_score: timeUnknown ? null : p.total_score,
      essential_score: p.essential_dignity.score,
      accidental_score: p.accidental_dignity ? p.accidental_dignity.score : null,
      house: p.house,
      house_class: houseClass(p.house),
    };
  });
  const ranks: number[] = [];
  ranking.forEach((r, i) => ranks.push(r.tiedWithPrev ? ranks[i - 1] : i + 1));

  const extreme = (index: number) => {
    const target = ranking[index];
    const s = score(planets.find((p) => p.name === target.planet));
    const co = ranking.filter((r) => r.planet !== target.planet
      && score(planets.find((p) => p.name === r.planet)) === s).map((r) => r.planet);
    return { planet: target.planet, total_score: target.total_score,
      essential_score: target.essential_score, tie: co.length > 0, co };
  };

  const contacts = (planet: string, by: string[], aspects: string[]) =>
    doc.aspects.filter((a: any) => aspects.includes(a.aspect)
      && ((a.from === planet && by.includes(a.to)) || (a.to === planet && by.includes(a.from))))
      .map((a: any) => ({
        by: a.from === planet ? a.to : a.from,
        aspect: a.aspect, orb: a.orb, partile: a.partile,
        reception_softens: a.reception_softens,
      }));

  const condition = (name: string) => {
    const p = planets.find((x: any) => x.name === name);
    return {
      planet: p.name,
      sign: p.sign,
      position: p.position,
      house: p.house,
      house_class: houseClass(p.house),
      essential_score: p.essential_dignity.score,
      accidental_score: p.accidental_dignity ? p.accidental_dignity.score : null,
      total_score: p.total_score,
      dignities: p.essential_dignity.dignities,
      debilities: p.essential_dignity.debilities,
      peregrine: p.essential_dignity.peregrine,
      peregrine_cancelled_by: p.essential_dignity.peregrine_cancelled_by,
      retrograde: p.retrograde,
      solar_phase: p.accidental_dignity ? p.accidental_dignity.solar_phase : "sun",
      in_sect: p.sect ? p.sect.in_sect : null,
      afflicted_by: contacts(name, ["Saturn", "Mars"], ["conjunction", "square", "opposition"]),
      assisted_by: contacts(name, ["Jupiter", "Venus"], ["conjunction", "trine", "sextile"]),
      classification: classify(p.essential_dignity.score,
        p.accidental_dignity ? p.accidental_dignity.score : null),
    };
  };

  const isDay = doc.sect ? doc.sect.is_day : null;
  const light = isDay === null ? null : (isDay ? "Sun" : "Moon");
  const ascLord = doc.angles ? doc.angles.ascendant.lord : null;
  const ascAlmuten = doc.angles ? doc.angles.ascendant.almuten : null;

  return {
    mode: timeUnknown ? "time_unknown" : "full",
    ranking_basis: timeUnknown ? "essential_score" : "total_score",
    dignity_ranking: ranking.map((r, i) => ({
      rank: ranks[i], planet: r.planet, total_score: r.total_score,
      essential_score: r.essential_score, accidental_score: r.accidental_score,
      house: r.house, house_class: r.house_class, tie: r.tie,
    })),
    strongest_planet: extreme(0),
    weakest_planet: extreme(ranking.length - 1),
    lord_of_geniture: {
      primary: doc.almuten_figuris ? doc.almuten_figuris.almutens : [],
      primary_basis: "almuten_figuris",
      primary_tie: doc.almuten_figuris ? doc.almuten_figuris.almuten_tie : false,
      secondary: extreme(0).planet,
      secondary_basis: "total_score",
    },
    sect_light_condition: (!timeUnknown && light) ? condition(light) : null,
    asc_lord_condition: (!timeUnknown && ascLord)
      ? {
        ...condition(ascLord),
        co_significator: ascAlmuten && ascAlmuten !== ascLord ? condition(ascAlmuten) : null,
      }
      : null,
    lot_lords_condition: (!timeUnknown && doc.lots)
      ? { fortune: condition(doc.lots.fortune.lord), spirit: condition(doc.lots.spirit.lord) }
      : null,
    out_of_sect_malefic: (!timeUnknown && isDay !== null)
      ? condition(isDay ? "Mars" : "Saturn") : null,
    in_sect_benefic: (!timeUnknown && isDay !== null)
      ? condition(isDay ? "Jupiter" : "Venus") : null,
    house_conditions: (!timeUnknown && doc.houses)
      ? doc.houses.map((h: any) => {
        const lord = planets.find((p: any) => p.name === h.lord);
        return {
          house: h.house, lord: h.lord, lord_house: lord.house,
          essential_score: lord.essential_dignity.score,
          accidental_score: lord.accidental_dignity ? lord.accidental_dignity.score : null,
          classification: classify(lord.essential_dignity.score,
            lord.accidental_dignity ? lord.accidental_dignity.score : null),
          lord_in_aversion: aversion(lord.sign_index, h.sign_index),
        };
      })
      : null,
    aversions_to_ascendant: (!timeUnknown && doc.angles)
      ? planets.filter((p: any) => aversion(p.sign_index, doc.angles.ascendant.sign_index))
        .map((p: any) => p.name)
      : null,
  };
}

/** JSON だけから summary を組み立て直す */
function recomputeSummary(doc: any): string {
  const na = "n/a (birth time unknown)";
  const signed = (n: number | null) => n === null ? "n/a" : (n >= 0 ? `+${n}` : `${n}`);
  const degrees = (position: string) => position.split(" ")[1];
  const planets: any[] = doc.planets;
  const find = (name: string) => planets.find((p) => p.name === name);
  const derived = doc.derived;
  const lines: string[] = [];

  if (doc.sect) {
    const light = doc.sect.sect_light.light;
    const p = find(light);
    lines.push(`${doc.sect.is_day ? "Diurnal" : "Nocturnal"} chart (sect by ASC–DSC horizon`
      + `${doc.sect.borderline ? "; borderline" : ""}). Sect light ${light} in ${p.sign} `
      + `(${p.house}h), essential ${signed(p.essential_dignity.score)}, `
      + `accidental ${signed(p.accidental_dignity.score)}.`);
  } else lines.push(na);

  if (doc.angles) {
    const asc = doc.angles.ascendant;
    const lord = find(asc.lord);
    const dignities = lord.essential_dignity.dignities.length
      ? lord.essential_dignity.dignities.join(", ")
      : (lord.essential_dignity.peregrine ? "peregrine" : "no dignity");
    const co = asc.almuten && asc.almuten !== asc.lord ? " (co-significator)" : "";
    lines.push(`Ascendant ${asc.sign} ${degrees(asc.position)}; lord ${asc.lord} in `
      + `${lord.sign} (${lord.house}h), ${dignities}; almuten ${asc.almuten ?? "none"}${co}.`);
  } else lines.push(na);

  const primary = derived.lord_of_geniture.primary;
  const figurisScore = doc.almuten_figuris && primary.length
    ? doc.almuten_figuris.scores[primary[0]].total : null;
  const secondaryScore = derived.strongest_planet.total_score
    ?? derived.strongest_planet.essential_score;
  lines.push(`Lord of the Geniture: ${primary.length ? primary.join(", ") : "none"} `
    + `(almuten figuris ${figurisScore ?? "n/a"}); highest total score `
    + `${derived.lord_of_geniture.secondary ?? "none"} (${signed(secondaryScore)}).`);

  const weakestScore = derived.weakest_planet.total_score
    ?? derived.weakest_planet.essential_score;
  lines.push(`Strongest planet ${derived.strongest_planet.planet} (${signed(secondaryScore)}); `
    + `weakest ${derived.weakest_planet.planet} (${signed(weakestScore)}).`);

  if (doc.sect) {
    const m = find(doc.sect.is_day ? "Mars" : "Saturn");
    lines.push(`Out-of-sect malefic ${m.name} in ${m.sign} (${m.house}h), `
      + `${classify(m.essential_dignity.score, m.accidental_dignity.score)}.`);
  } else lines.push(na);

  if (doc.lots) {
    const f = doc.lots.fortune;
    const s = doc.lots.spirit;
    lines.push(`Fortune ${f.sign} ${degrees(f.position)} (${f.house}h, lord ${f.lord}); `
      + `Spirit ${s.sign} ${degrees(s.position)} (${s.house}h, lord ${s.lord})`
      + `${f.sect_reversed ? "; night formula (Dorotheus)" : ""}.`);
  } else lines.push(na);

  const flags = doc.boundary_warnings.map((w: any) => w.id);
  lines.push(`Flags: ${flags.length ? flags.join(", ") : "none"}.`);
  lines.push(`Birth time ${doc.birth_data.time_known ? "known" : "unknown"}; schema v2; `
    + `${doc.generator}.`);
  return lines.join("\n");
}

describe("GT-3：derived と summary の整合", () => {
  const charts = Object.entries(manifest.charts) as [string, any][];

  it.each(charts)("%s の derived が raw から再計算できる", (_name, spec) => {
    const doc = computeChart({
      year: spec.year, month: spec.month, day: spec.day,
      hour: spec.hour, minute: spec.minute,
      latitude: spec.latitude, longitude: spec.longitude, tzOffset: spec.tz_offset,
      generatedAt: FIXED_TIME,
    }) as any;
    const { thresholds, reading_order, ...rest } = doc.derived;
    expect(rest).toEqual(recomputeDerived(doc));
  });

  it.each(charts)("%s の summary が raw から再計算できる", (_name, spec) => {
    const doc = computeChart({
      year: spec.year, month: spec.month, day: spec.day,
      hour: spec.hour, minute: spec.minute,
      latitude: spec.latitude, longitude: spec.longitude, tzOffset: spec.tz_offset,
      generatedAt: FIXED_TIME,
    }) as any;
    expect(doc.summary).toBe(recomputeSummary(doc));
  });

  it("time_unknown でも derived と summary が再計算できる", () => {
    const doc = computeChart({
      year: 1985, month: 7, day: 21, latitude: 35.6895, longitude: 139.6917,
      timezoneId: "Asia/Tokyo", timeKnown: false, generatedAt: FIXED_TIME,
    }) as any;
    const { thresholds, reading_order, ...rest } = doc.derived;
    expect(rest).toEqual(recomputeDerived(doc));
    expect(doc.summary).toBe(recomputeSummary(doc));
  });

  it("reading_order は決定 12 の順序（重複は先勝ち）", () => {
    const doc = computeChart({
      year: 1985, month: 7, day: 21, hour: 14, minute: 30,
      latitude: 35.6895, longitude: 139.6917, tzOffset: 9, generatedAt: FIXED_TIME,
    }) as any;
    const order: string[] = doc.derived.reading_order;
    expect(new Set(order).size).toBe(order.length);
    expect(order).toHaveLength(7);
    expect(order[0]).toBe(doc.sect.sect_light.light);
    expect(order[1]).toBe(doc.angles.ascendant.lord);
    // 先勝ちなので、ASC 主星とセクト外凶星が同じ天体なら前の位置に 1 度だけ入る
    expect(order).toContain(doc.derived.lord_of_geniture.primary[0]);
    expect(order).toContain(doc.sect.is_day ? "Mars" : "Saturn");
    expect(order.slice(0, 3)).toContain(doc.sect.is_day ? "Mars" : "Saturn");
  });
});
