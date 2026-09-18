/**
 * ★共通の品位エンジン（要件書 I-1-2）。
 * ネイタルも適職（Phase 4）もこのファイルの戻り値だけを見る（決定 B）。
 * 表は tables.ts 経由でのみ参照する。
 *
 * 規則の出所：METHOD_本質的品位表_v1.md v1.2
 *   §3 トリプリシティ（得点はセクト主星のみ +3）
 *   §8.2 決定①〜③（ペレグリン −5／ミューチュアル・レセプションで解除／重複加算禁止）
 *   §10 決定④（単一度数の同点はハウス位置）・決定⑤（フィギュリスの同点は共同）
 */
import {
  DEFAULT_TERMS, DEFAULT_TRIPLICITY, DETRIMENT_BY_SIGN, DIGNITY_SCORE, DOMICILE_BY_SIGN,
  EXALT_BY_SIGN, FACES, FALL_BY_SIGN, PEREGRINE_SCORE_NOTE, TERMS_AUDIT, TERMS_TABLES,
  TRIPLICITY_TABLES, ANGULAR_HOUSES, SUCCEDENT_HOUSES, type TermCell, type TriplicityRow,
} from "./tables.ts";
import { PLANET_NAMES, degInSign, elementOf, signOf } from "./util.ts";

export type MutualReceptionType =
  | "mutual_reception_sign"
  | "mutual_reception_exaltation"
  | "mutual_reception_mixed";

export interface MutualReception {
  with: string;
  type: MutualReceptionType;
}

export interface TriplicityRulers {
  day: string;
  night: string;
  participating: string | null;
  sect_ruler: string | null;
}

export interface TermAudit {
  table: string;
  ruler: string;
  differs: boolean;
  has_term: boolean;
}

export type AlmutenTieMode = "house_order" | "vocation_2b" | "none";

export interface EssentialDignity {
  sign: number;
  degree: number;
  labels: string[];
  debilities: string[];
  peregrine: boolean | null;
  peregrine_cancelled_by: MutualReceptionType | null;
  peregrine_scored: boolean;
  /** セクト不明（time_known:false）で、そのサインの昼／夜主星のためペレグリンが決まらない */
  peregrine_uncertain: boolean;
  has_dignity: boolean;
  mutual_receptions: MutualReception[];
  score: number;
  score_note: string | null;
  rulers: {
    domicile: string;
    exaltation: string | null;
    triplicity: string | null;
    term: string;
    face: string;
  };
  triplicity_rulers: TriplicityRulers;
  term_audit: TermAudit;
}

/** タームの主星。既定はエジプト式 */
export function termRuler(lon: number, table: TermCell[][] = TERMS_TABLES[DEFAULT_TERMS]): string {
  const si = signOf(lon);
  const d = degInSign(lon);
  for (const cell of table[si]) {
    if (d < cell.until) return cell.ruler;
  }
  return table[si][table[si].length - 1].ruler;
}

/** フェイス（デカン）の主星 */
export function faceRuler(lon: number): string {
  return FACES[signOf(lon)][Math.floor(degInSign(lon) / 10)];
}

/** サインのトリプリシティ主星（昼・夜・関与）。既定はドロテウス式 */
export function triplicityRulers(
  signIndex: number, table: Record<string, TriplicityRow> = TRIPLICITY_TABLES[DEFAULT_TRIPLICITY],
): TriplicityRow {
  return table[elementOf(signIndex)];
}

/** planet がサイン si に対して持つ「サイン」「イグザルテーション」の品位 */
export function signDignityKinds(planet: string, signIndex: number): ("sign" | "exaltation")[] {
  const kinds: ("sign" | "exaltation")[] = [];
  if (DOMICILE_BY_SIGN[signIndex] === planet) kinds.push("sign");
  if (EXALT_BY_SIGN[String(signIndex)]?.planet === planet) kinds.push("exaltation");
  return kinds;
}

const MR_ORDER: MutualReceptionType[] = [
  "mutual_reception_sign", "mutual_reception_exaltation", "mutual_reception_mixed",
];

/**
 * サインまたはイグザルテーションによるミューチュアル・レセプション（決定②）。
 * mixed（サイン×イグザルテーション）も含める（METHOD §8.2 v1.2）。
 * アスペクトの有無は問わない（プロジェクト慣行）。
 */
export function mutualReceptions(
  planet: string, positions: Record<string, number>,
): MutualReception[] {
  const mySign = signOf(positions[planet]);
  const found: MutualReception[] = [];
  for (const [other, otherLon] of Object.entries(positions)) {
    if (other === planet) continue;
    const mine = signDignityKinds(planet, signOf(otherLon));
    const theirs = signDignityKinds(other, mySign);
    const types = new Set<MutualReceptionType>();
    for (const a of mine) {
      for (const b of theirs) {
        types.add(("mutual_reception_" + (a === b ? a : "mixed")) as MutualReceptionType);
      }
    }
    if (types.size) {
      const type = [...types].sort((x, y) => MR_ORDER.indexOf(x) - MR_ORDER.indexOf(y))[0];
      found.push({ with: other, type });
    }
  }
  found.sort((a, b) =>
    MR_ORDER.indexOf(a.type) - MR_ORDER.indexOf(b.type)
    || PLANET_NAMES.indexOf(a.with) - PLANET_NAMES.indexOf(b.with));
  return found;
}

export interface EssentialOptions {
  tripTable?: Record<string, TriplicityRow>;
  /** 体系差分（I-3-9）で監査用のターム表に差し替えるときだけ渡す */
  termTable?: TermCell[][];
  receptions?: MutualReception[];
  /** セクト不明（time_known:false）。Phase 3 で使う */
  sectUnknown?: boolean;
}

/** ある黄経における惑星の本質的品位 */
export function essentialDignity(
  lon: number, planet: string, isDay: boolean, options: EssentialOptions = {},
): EssentialDignity {
  const tripTable = options.tripTable ?? TRIPLICITY_TABLES[DEFAULT_TRIPLICITY];
  const receptions = options.receptions ?? [];
  const si = signOf(lon);
  const d = degInSign(lon);

  const trip = triplicityRulers(si, tripTable);
  const sectRuler = options.sectUnknown ? null : (isDay ? trip.day : trip.night);
  const term = termRuler(lon, options.termTable);
  const auditRuler = termRuler(lon, TERMS_TABLES[TERMS_AUDIT]);
  const face = faceRuler(lon);

  const labels: string[] = [];
  if (DOMICILE_BY_SIGN[si] === planet) labels.push("domicile");
  if (EXALT_BY_SIGN[String(si)]?.planet === planet) labels.push("exaltation");
  if (sectRuler !== null && planet === sectRuler) labels.push("triplicity");
  if (term === planet) labels.push("term");
  if (face === planet) labels.push("face");

  const debilities: string[] = [];
  if (DETRIMENT_BY_SIGN[si] === planet) debilities.push("detriment");
  if (FALL_BY_SIGN[String(si)]?.planet === planet) debilities.push("fall");

  let peregrine: boolean | null = labels.length === 0;
  let cancelledBy: MutualReceptionType | null = null;
  let scoreNote: string | null = options.sectUnknown
    ? "sect unknown: triplicity not scored" : null;
  let peregrineUncertain = false;
  if (peregrine && receptions.length) {
    peregrine = false;
    cancelledBy = receptions[0].type;
  }
  if (peregrine && options.sectUnknown && (planet === trip.day || planet === trip.night)) {
    // セクトが決まればトリプリシティで +3 を得るかもしれない天体（I-4）
    peregrine = null;
    peregrineUncertain = true;
  }
  if (peregrine) {
    if (debilities.length) scoreNote = PEREGRINE_SCORE_NOTE;
    else debilities.push("peregrine");
  }

  const score = [...labels, ...debilities].reduce((sum, key) => sum + DIGNITY_SCORE[key], 0);

  return {
    sign: si,
    degree: d,
    labels,
    debilities,
    peregrine,
    peregrine_cancelled_by: cancelledBy,
    peregrine_scored: debilities.includes("peregrine"),
    peregrine_uncertain: peregrineUncertain,
    has_dignity: labels.length > 0,
    mutual_receptions: receptions,
    score,
    score_note: scoreNote,
    rulers: {
      domicile: DOMICILE_BY_SIGN[si],
      exaltation: EXALT_BY_SIGN[String(si)]?.planet ?? null,
      triplicity: sectRuler,
      term,
      face,
    },
    triplicity_rulers: {
      day: trip.day,
      night: trip.night,
      participating: trip.participating,
      sect_ruler: sectRuler,
    },
    term_audit: {
      table: TERMS_AUDIT,
      ruler: auditRuler,
      differs: auditRuler !== term,
      has_term: auditRuler === planet,
    },
  };
}

/** アルムテン用の品位点（プラスのみ） */
export function dignityPoints(
  lon: number, planet: string, isDay: boolean, tripTable?: Record<string, TriplicityRow>,
): number {
  const ed = essentialDignity(lon, planet, isDay, { tripTable });
  return ed.labels.reduce((sum, key) => sum + DIGNITY_SCORE[key], 0);
}

/** アングル＝3、サクシーデント＝2、ケーデント＝1（不明は 0） */
export function houseAngularity(house: number | null | undefined): number {
  if (house == null) return 0;
  if (ANGULAR_HOUSES.includes(house)) return 3;
  if (SUCCEDENT_HOUSES.includes(house)) return 2;
  return 1;
}

export interface AlmutenResult {
  almuten: string | null;
  almuten_tie: boolean;
  candidates: string[];
  tie_break: string | null;
  scores: Record<string, number>;
}

/**
 * 単一度数のアルムテン（決定④）。
 * 同点はハウス位置（アングル＞サクシーデント＞ケーデント）、なお同点なら tie。
 */
export interface AlmutenTieContext {
  /** 同点処理の方式。house_order＝決定④、vocation_2b＝手順書 §2 ②-B、none＝決定⑤ */
  mode?: AlmutenTieMode;
  houseOf?: Record<string, number | null>;
  /** vocation_2b 用：品位の高さ（本質的得点）、アングルからの近さ、セクト適合 */
  dignityRank?: Record<string, number>;
  angleProximity?: Record<string, number>;
  inSect?: Record<string, boolean>;
}

export function resolveAlmuten(
  scores: Record<string, number>,
  houseOfOrContext: Record<string, number | null> | AlmutenTieContext = {},
): Omit<AlmutenResult, "scores"> {
  const context: AlmutenTieContext = isTieContext(houseOfOrContext)
    ? houseOfOrContext
    : { mode: "house_order", houseOf: houseOfOrContext };
  const mode: AlmutenTieMode = context.mode ?? "house_order";
  const houseOf = context.houseOf ?? {};
  const values = Object.values(scores);
  if (!values.length || Math.max(...values) <= 0) {
    return { almuten: null, almuten_tie: false, candidates: [], tie_break: null };
  }
  const top = Math.max(...values);
  const candidates = PLANET_NAMES.filter((n) => scores[n] === top);
  if (candidates.length === 1) {
    return { almuten: candidates[0], almuten_tie: false, candidates, tie_break: null };
  }
  if (mode === "none") {
    // 決定⑤：同点は決着させない（呼び出し側が共同アルムテンとして扱う）
    return { almuten: null, almuten_tie: true, candidates, tie_break: null };
  }
  if (mode === "vocation_2b") {
    return resolveVocation2B(candidates, context);
  }
  const best = Math.max(...candidates.map((n) => houseAngularity(houseOf[n])));
  const finalists = candidates.filter((n) => houseAngularity(houseOf[n]) === best);
  if (finalists.length === 1 && best > 0) {
    return {
      almuten: finalists[0], almuten_tie: false, candidates, tie_break: "house_angularity",
    };
  }
  return {
    almuten: null,
    almuten_tie: true,
    candidates: finalists,
    tie_break: best > 0 ? "house_angularity" : null,
  };
}

function isTieContext(v: unknown): v is AlmutenTieContext {
  return !!v && typeof v === "object"
    && ("mode" in v || "houseOf" in v || "dignityRank" in v || "angleProximity" in v
      || "inSect" in v);
}

/**
 * 手順書 §2 ②-B の同点処理：品位の高い方 → アングルに近い方 → セクトに合う方 → tie。
 * Phase 4 の適職で使う。
 */
function resolveVocation2B(
  candidates: string[], context: AlmutenTieContext,
): Omit<AlmutenResult, "scores"> {
  const steps: { key: string; rank: (n: string) => number }[] = [
    { key: "dignity_rank", rank: (n) => context.dignityRank?.[n] ?? 0 },
    { key: "angle_proximity", rank: (n) => -(context.angleProximity?.[n] ?? Infinity) },
    { key: "sect", rank: (n) => (context.inSect?.[n] ? 1 : 0) },
  ];
  let pool = [...candidates];
  for (const step of steps) {
    const best = Math.max(...pool.map(step.rank));
    if (!Number.isFinite(best)) continue;
    const next = pool.filter((n) => step.rank(n) === best);
    if (next.length === 1) {
      return { almuten: next[0], almuten_tie: false, candidates, tie_break: step.key };
    }
    if (next.length) pool = next;
  }
  return { almuten: null, almuten_tie: true, candidates: pool, tie_break: null };
}

/** ルール④専用のモイエティ（月のオーブ 12°30′ の半分）。一般オーブとは別の規則 */
export const MOON_MOIETY_DEG = 6.25;

/**
 * ルール④：月とのアスペクトが月のモイエティ（6°15′）以内か。
 * 測るのは「アスペクトのオーブ」であって天体間の離角ではない。候補星側の moiety は
 * 加算しない（CA III l.7780 を文字どおり。手順書 v10 §2）。
 * 較正例 No.001 の金星（月からのディソシエイトなスクエア、オーブ 6°04′）が
 * この規則に該当すると較正メモが記しており、オーブで測ることの裏づけになる。
 */
export function withinMoonMoiety(aspectOrbDeg: number): boolean {
  return aspectOrbDeg <= MOON_MOIETY_DEG;
}

export function almutenOfDegree(
  lon: number, isDay: boolean,
  tripTable?: Record<string, TriplicityRow>,
  houseOf: Record<string, number | null> = {},
): AlmutenResult {
  const scores: Record<string, number> = {};
  for (const name of PLANET_NAMES) {
    const s = dignityPoints(lon, name, isDay, tripTable);
    if (s) scores[name] = s;
  }
  return { ...resolveAlmuten(scores, houseOf), scores };
}

export interface FigurisRow {
  asc: number; sun: number; moon: number; fortune: number; syzygy: number;
  total: number; accidental: number; house: number | null;
}

export interface FigurisResult {
  almutens: string[];
  almuten: string | null;
  almuten_tie: boolean;
  table: Record<string, FigurisRow>;
  ranked: string[];
}

/**
 * アルムテン・フィギュリス（決定⑤）。
 * 同点はハウス位置で決着させず、最高点の全天体を共同アルムテンとする。
 */
export function almutenFiguris(
  places: Record<string, number | null>,
  isDay: boolean,
  accidentalScores: Record<string, number> = {},
  tripTable?: Record<string, TriplicityRow>,
  houseOf: Record<string, number | null> = {},
): FigurisResult {
  const table: Record<string, FigurisRow> = {};
  for (const name of PLANET_NAMES) {
    const row: Record<string, number> = {};
    let total = 0;
    for (const [key, lon] of Object.entries(places)) {
      const s = lon === null ? 0 : dignityPoints(lon, name, isDay, tripTable);
      row[key] = s;
      total += s;
    }
    table[name] = {
      asc: row.asc ?? 0, sun: row.sun ?? 0, moon: row.moon ?? 0,
      fortune: row.fortune ?? 0, syzygy: row.syzygy ?? 0,
      total,
      accidental: accidentalScores[name] ?? 0,
      house: houseOf[name] ?? null,
    };
  }
  const ranked = [...PLANET_NAMES].sort((a, b) => table[b].total - table[a].total);
  const top = table[ranked[0]].total;
  const almutens = top > 0 ? ranked.filter((n) => table[n].total === top) : [];
  return {
    almutens,
    almuten: almutens.length === 1 ? almutens[0] : null,
    almuten_tie: almutens.length > 1,
    table,
    ranked,
  };
}
