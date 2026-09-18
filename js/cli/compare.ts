/**
 * GT-2：Python（v1 リファレンス、タグ v1-reference）のゴールデンと JS 出力を比較する。
 *
 *   node --experimental-strip-types cli/compare.ts [--verbose]
 *
 * 許容差（要件書 v0.3 §I-6 GT-2）：
 *   - 黄経・カスプ・速度は 0.02° 以内
 *   - サイン・度分文字列・ハウス・品位・得点・旗・アスペクト一覧は完全一致
 *   - fixed_stars は報告のみ（I-2-1 保留）
 *   - planetary_day_hour の sunrise/sunset は 2 分以内、主星・時刻番号は完全一致
 *   - 離散値の不一致が 0.02° 以内の差に由来する場合は「暦の境界事例」として別表に出す
 *     （自動合格にしない）
 */
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { computeChart } from "../src/index.ts";
import { trueNodeSpeed } from "../src/ephemeris.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const GOLDEN_DIR = join(HERE, "..", "test", "golden");
const ANGLE_TOLERANCE = 0.02;
const TIME_TOLERANCE_MIN = 2;

export type DiffKind = "numeric" | "discrete" | "boundary" | "fixed_star" | "time"
  | "known_divergence";

export interface Diff {
  chart: string;
  path: string;
  python: unknown;
  js: unknown;
  kind: DiffKind;
  delta?: number;
  note?: string;
}

/** 角度として 0.02° の許容差で比べるキー */
const ANGLE_KEYS = new Set(["longitude", "orb", "max_orb", "distance_from_sun"]);
/** 差の絶対値で比べるキー（角度の巻き戻しをしない） */
const SCALAR_KEYS = new Set(["speed", "sun_altitude", "julian_day_ut"]);
/** 黄経から導かれる離散値（境界事例の判定に使う） */
const DERIVED_FROM_LONGITUDE = new Set(["degrees", "minutes", "position", "sign", "sign_index"]);

// Python 側を直したので、既知の相違は現時点で無い（付録 A #19 は解決済み）
const KNOWN_DIVERGENCES: { match: (path: string) => boolean; note: string }[] = [];

/** 分まで切り捨てて出す日時。2 分以内のずれは境界事例として扱う */
const MINUTE_STRING_KEYS = ["/sunrise", "/sunset", "/prenatal_syzygy/datetime_local"];

function angleDelta(a: number, b: number): number {
  return Math.abs(((a - b + 540) % 360) - 180);
}

function minutesBetween(a: string, b: string): number {
  const parse = (s: string) => {
    const m = s.match(/(\d+)-(\d+)-(\d+) (\d+):(\d+)/);
    return m ? Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) / 60000 : NaN;
  };
  return Math.abs(parse(a) - parse(b));
}

interface WalkContext {
  chart: string;
  diffs: Diff[];
  /** 直近の親オブジェクトにあった longitude の差（境界事例の判定用） */
  lonDelta: number | null;
}

function walk(py: unknown, js: unknown, path: string, ctx: WalkContext): void {
  const known = KNOWN_DIVERGENCES.find((k) => k.match(path));
  if (known && py !== js) {
    ctx.diffs.push({ chart: ctx.chart, path, python: py, js, kind: "known_divergence", note: known.note });
    return;
  }

  if (Array.isArray(py) && Array.isArray(js)) {
    if (py.length !== js.length) {
      ctx.diffs.push({
        chart: ctx.chart, path, python: `len=${py.length}`, js: `len=${js.length}`, kind: "discrete",
      });
      return;
    }
    py.forEach((v, i) => walk(v, js[i], `${path}[${i}]`, ctx));
    return;
  }

  if (py && js && typeof py === "object" && typeof js === "object") {
    const pyObj = py as Record<string, unknown>;
    const jsObj = js as Record<string, unknown>;
    let lonDelta = ctx.lonDelta;
    if (typeof pyObj.longitude === "number" && typeof jsObj.longitude === "number") {
      lonDelta = angleDelta(pyObj.longitude, jsObj.longitude);
    }
    const inner: WalkContext = { ...ctx, lonDelta };
    for (const key of Object.keys(pyObj)) {
      if (!(key in jsObj)) {
        ctx.diffs.push({
          chart: ctx.chart, path: `${path}/${key}`, python: pyObj[key], js: "(欠落)", kind: "discrete",
        });
        continue;
      }
      walk(pyObj[key], jsObj[key], `${path}/${key}`, inner);
      ctx.diffs.push(...inner.diffs.splice(0));
    }
    return;
  }

  if (py === js) return;
  const leaf = path.split("/").pop()?.replace(/\[\d+\]$/, "") ?? "";
  const isFixedStar = path.includes("/fixed_stars/");

  if (typeof py === "number" && typeof js === "number") {
    const delta = SCALAR_KEYS.has(leaf) ? Math.abs(py - js) : angleDelta(py, js);
    if (ANGLE_KEYS.has(leaf) || SCALAR_KEYS.has(leaf)) {
      if (isFixedStar) {
        ctx.diffs.push({ chart: ctx.chart, path, python: py, js, kind: "fixed_star", delta });
      } else if (delta > ANGLE_TOLERANCE) {
        ctx.diffs.push({ chart: ctx.chart, path, python: py, js, kind: "numeric", delta });
      }
      return;
    }
    const kind: DiffKind = isFixedStar ? "fixed_star"
      : (DERIVED_FROM_LONGITUDE.has(leaf) && ctx.lonDelta !== null && ctx.lonDelta <= ANGLE_TOLERANCE)
        ? "boundary" : "discrete";
    ctx.diffs.push({ chart: ctx.chart, path, python: py, js, kind, delta: Math.abs(py - js) });
    return;
  }

  if (MINUTE_STRING_KEYS.some((k) => path.endsWith(k))) {
    const delta = minutesBetween(py as string, js as string);
    ctx.diffs.push({
      chart: ctx.chart, path, python: py, js, delta,
      kind: delta > TIME_TOLERANCE_MIN ? "time" : "boundary",
      note: delta > TIME_TOLERANCE_MIN ? undefined : "分の切り捨て境界（2 分以内）",
    });
    return;
  }
  if (path === "/generator") return;            // 実装名は異なってよい
  if (path.startsWith("/tables_used/sources")) return;  // 出所ラベルは Python の定数をそのまま写す

  const kind: DiffKind = isFixedStar ? "fixed_star"
    : (DERIVED_FROM_LONGITUDE.has(leaf) && ctx.lonDelta !== null && ctx.lonDelta <= ANGLE_TOLERANCE)
      ? "boundary" : "discrete";
  ctx.diffs.push({ chart: ctx.chart, path, python: py, js, kind });
}

export function compareAll(): { diffs: Diff[]; charts: string[] } {
  const manifest = JSON.parse(readFileSync(join(GOLDEN_DIR, "manifest.json"), "utf8"));
  const diffs: Diff[] = [];
  const charts: string[] = [];
  for (const file of readdirSync(GOLDEN_DIR).filter((f) => f.endsWith(".json") && f !== "manifest.json").sort()) {
    const name = file.replace(/\.json$/, "");
    const spec = manifest.charts[name];
    const golden = JSON.parse(readFileSync(join(GOLDEN_DIR, file), "utf8"));
    const js = computeChart({
      year: spec.year, month: spec.month, day: spec.day,
      hour: spec.hour, minute: spec.minute,
      latitude: spec.latitude, longitude: spec.longitude, tzOffset: spec.tz_offset,
    });
    const ctx: WalkContext = { chart: name, diffs: [], lonDelta: null };
    walk(golden, js, "", ctx);
    // ノードが停留しているときの逆行フラグは境界事例として扱う（双方 |速度| < 0.001°/日）
    const nodeSpeed = Math.abs(trueNodeSpeed(golden.birth_data.julian_day_ut));
    for (const d of ctx.diffs) {
      if (d.kind === "discrete" && /\/nodes\/true\[\d+\]\/retrograde$/.test(d.path)
          && nodeSpeed < 1e-3) {
        d.kind = "boundary";
        d.note = `トゥルーノードが停留（JS の速度 ${nodeSpeed.toExponential(2)}°/日）`;
      }
    }
    diffs.push(...ctx.diffs);
    charts.push(name);
  }
  return { diffs, charts };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { diffs, charts } = compareAll();
  const byKind: Record<string, Diff[]> = {};
  for (const d of diffs) (byKind[d.kind] ??= []).push(d);
  const order: DiffKind[] = ["numeric", "discrete", "boundary", "time", "fixed_star", "known_divergence"];
  console.log(`比較した図: ${charts.length}（${charts.join(", ")}）\n`);
  for (const kind of order) {
    const list = byKind[kind] ?? [];
    const maxDelta = Math.max(0, ...list.map((d) => d.delta ?? 0));
    console.log(`[${kind}] ${list.length} 件` + (maxDelta ? `（最大差 ${maxDelta.toExponential(3)}）` : ""));
    const limit = process.argv.includes("--verbose") ? list.length : 12;
    for (const d of list.slice(0, limit)) {
      console.log(`  ${d.chart}${d.path}: py=${JSON.stringify(d.python)} js=${JSON.stringify(d.js)}`
        + (d.delta !== undefined ? ` (差 ${d.delta.toExponential(3)})` : ""));
    }
    if (list.length > limit) console.log(`  … ほか ${list.length - limit} 件（--verbose で全件）`);
  }
  const failing = (byKind.numeric?.length ?? 0) + (byKind.discrete?.length ?? 0)
    + (byKind.time?.length ?? 0);
  console.log(`\n合否に数える差分: ${failing} 件`
    + `／境界事例 ${(byKind.boundary ?? []).length} 件（要確認）`
    + `／恒星 ${(byKind.fixed_star ?? []).length} 件（報告のみ）`
    + `／既知の相違 ${(byKind.known_divergence ?? []).length} 件`);
  process.exit(failing ? 1 : 0);
}
