/**
 * summary・reading_notes・provenance・boundary_warnings（要件書 I-2-2・I-3-8）。
 * summary の文言はテンプレートとして固定し、実装間で一字一句一致させる。解釈語は入れない。
 */
import type { Condition, Derived } from "./derived.ts";

export const GENERATOR = "traditionalchart-js 0.1.0";

export const CITE_AS = "AmanJyoshi — traditionalchart.com";
export const METHOD_DOCS = [
  "METHOD_本質的品位表_v1 v1.2",
  "METHOD_natal_v1 v1.3",
  "古典職業鑑定マニュアル v11 + 再基底化差分 20260918",
];

export const READING_NOTES = [
  "All positions, dignities, scores, houses and aspects in this file are computed. Do not recompute or re-derive any of them; quote `position` strings verbatim.",
  "If `summary` or `derived` appears to disagree with a raw field, the raw field is correct. Report the discrepancy; do not resolve it by reasoning.",
  "`terms_audit`, `term_audit`, `system_divergence` and any table marked verified:false are audit information. Never use them as grounds for a judgement.",
  "`sect.borderline`, `planets[].near_next_cusp`, `angles.*.sign_change_within_minutes` and `boundary_warnings[]` mark where a small error in birth time changes the chart. Mention them only where they affect a statement.",
  "`vocation.rule4_moiety_deg` (6.25°) is a rule-specific threshold for the vocational rule 4 and is unrelated to `aspects[].max_orb`.",
];

export const TIME_UNKNOWN_NOTE =
  "Birth time is unknown: houses, angles, lots, sect and planetary hours are null; the Moon's position is given as a range. Do not infer any of them.";

export const NOT_AVAILABLE = "n/a (birth time unknown)";

export interface BoundaryWarning {
  id: string;
  level: number;
  target: string;
  value: number | string | null;
  threshold: number | string | null;
  message_en: string;
}

/** +5 / -4 のように符号を必ず付ける */
export function signed(n: number | null): string {
  if (n === null) return "n/a";
  return n >= 0 ? `+${n}` : `${n}`;
}

/** "Scorpio 28°22'" 形式（summary 用。サインは正式名） */
export function signAndDegrees(sign: string, position: string): string {
  return `${sign} ${position.split(" ")[1]}`;
}

export interface SummaryInput {
  timeKnown: boolean;
  isDay: boolean | null;
  borderline: boolean;
  sectLight: { planet: string; sign: string; house: number | null;
    essential: number; accidental: number | null } | null;
  ascendant: { sign: string; position: string; lord: string; lordSign: string;
    lordHouse: number | null; lordDignities: string[]; lordPeregrine: boolean | null;
    almuten: string | null; almutenIsCoSignificator: boolean } | null;
  lordOfGeniture: { primary: string[]; score: number | null;
    secondary: string | null; secondaryScore: number | null };
  strongest: { planet: string | null; score: number | null };
  weakest: { planet: string | null; score: number | null };
  outOfSectMalefic: Condition | null;
  lots: { fortuneSign: string; fortunePosition: string; fortuneHouse: number | null;
    fortuneLord: string; spiritSign: string; spiritPosition: string;
    spiritHouse: number | null; spiritLord: string; sectReversed: boolean } | null;
  flags: string[];
  generator: string;
}

/**
 * I-2-2 の 8 行。行頭に番号は付けない（番号は要件書の列挙のため）。
 * time_known:false のときは 1・2・5・6 行を n/a にする。
 */
export function buildSummary(input: SummaryInput): string {
  const lines: string[] = [];

  if (input.timeKnown && input.sectLight && input.isDay !== null) {
    const sect = input.isDay ? "Diurnal" : "Nocturnal";
    const borderline = input.borderline ? "; borderline" : "";
    lines.push(
      `${sect} chart (sect by ASC–DSC horizon${borderline}). `
      + `Sect light ${input.sectLight.planet} in ${input.sectLight.sign} `
      + `(${input.sectLight.house}h), essential ${signed(input.sectLight.essential)}, `
      + `accidental ${signed(input.sectLight.accidental)}.`,
    );
  } else {
    lines.push(NOT_AVAILABLE);
  }

  if (input.timeKnown && input.ascendant) {
    const a = input.ascendant;
    const dignities = a.lordDignities.length ? a.lordDignities.join(", ")
      : (a.lordPeregrine ? "peregrine" : "no dignity");
    const co = a.almutenIsCoSignificator ? " (co-significator)" : "";
    lines.push(
      `Ascendant ${signAndDegrees(a.sign, a.position)}; `
      + `lord ${a.lord} in ${a.lordSign} (${a.lordHouse}h), ${dignities}; `
      + `almuten ${a.almuten ?? "none"}${co}.`,
    );
  } else {
    lines.push(NOT_AVAILABLE);
  }

  const log = input.lordOfGeniture;
  lines.push(
    `Lord of the Geniture: ${log.primary.length ? log.primary.join(", ") : "none"} `
    + `(almuten figuris ${log.score ?? "n/a"}); `
    + `highest total score ${log.secondary ?? "none"} (${signed(log.secondaryScore)}).`,
  );

  lines.push(
    `Strongest planet ${input.strongest.planet ?? "none"} (${signed(input.strongest.score)}); `
    + `weakest ${input.weakest.planet ?? "none"} (${signed(input.weakest.score)}).`,
  );

  if (input.timeKnown && input.outOfSectMalefic) {
    const m = input.outOfSectMalefic;
    lines.push(
      `Out-of-sect malefic ${m.planet} in ${m.sign} (${m.house}h), ${m.classification}.`,
    );
  } else {
    lines.push(NOT_AVAILABLE);
  }

  if (input.timeKnown && input.lots) {
    const l = input.lots;
    const night = l.sectReversed ? "; night formula (Dorotheus)" : "";
    lines.push(
      `Fortune ${signAndDegrees(l.fortuneSign, l.fortunePosition)} `
      + `(${l.fortuneHouse}h, lord ${l.fortuneLord}); `
      + `Spirit ${signAndDegrees(l.spiritSign, l.spiritPosition)} `
      + `(${l.spiritHouse}h, lord ${l.spiritLord})${night}.`,
    );
  } else {
    lines.push(NOT_AVAILABLE);
  }

  lines.push(`Flags: ${input.flags.length ? input.flags.join(", ") : "none"}.`);
  lines.push(
    `Birth time ${input.timeKnown ? "known" : "unknown"}; schema v2; ${input.generator}.`,
  );

  return lines.join("\n");
}

export function buildReadingNotes(timeKnown: boolean): string[] {
  return timeKnown ? [...READING_NOTES] : [...READING_NOTES, TIME_UNKNOWN_NOTE];
}

export function buildProvenance(generatedAt: string, referenceGenerator: string | null) {
  return {
    cite_as: CITE_AS,
    license: null,
    method_docs: [...METHOD_DOCS],
    generated_at: generatedAt,
    generator: GENERATOR,
    reference_generator: referenceGenerator,
  };
}

/** derived から summary の材料を取り出すときに使う小道具 */
export function summaryFlags(warnings: BoundaryWarning[]): string[] {
  return warnings.map((w) => w.id);
}

export function readingOrderOf(derived: Derived): string[] {
  return derived.reading_order;
}
