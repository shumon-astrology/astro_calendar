/**
 * GT-6（SCHEMA_chart_v2.json による検証）・GT-7（決定性）・GT-5(a)(b)。
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Ajv2020 } from "ajv/dist/2020.js";
import { beforeAll, describe, expect, it } from "vitest";
import { computeChart, type ChartInput } from "../src/index.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const SCHEMA_PATH = join(HERE, "..", "..", "schema", "SCHEMA_chart_v2.json");
const manifest = JSON.parse(readFileSync(join(HERE, "golden", "manifest.json"), "utf8"));

const FIXED_TIME = "2026-09-19T00:00:00.000Z";

let validate: ReturnType<InstanceType<typeof Ajv2020>["compile"]>;

beforeAll(() => {
  const schema = JSON.parse(readFileSync(SCHEMA_PATH, "utf8"));
  const ajv = new Ajv2020({ strict: true, allErrors: true, allowUnionTypes: true });
  // x- で始まる注記キーワードはスキーマの付帯情報（ajv strict の未知キーワード対策）
  for (const key of Object.keys(schema).filter((k) => k.startsWith("x-"))) {
    ajv.addKeyword({ keyword: key, valid: true });
  }
  validate = ajv.compile(schema);
});

const errorsFor = (doc: unknown): string[] => {
  validate(doc);
  return (validate.errors ?? []).map(
    (e: { instancePath: string; message?: string }) => `${e.instancePath || "(root)"}: ${e.message}`,
  );
};

const inputFor = (spec: Record<string, number>): ChartInput => ({
  year: spec.year, month: spec.month, day: spec.day,
  hour: spec.hour, minute: spec.minute,
  latitude: spec.latitude, longitude: spec.longitude, tzOffset: spec.tz_offset,
  generatedAt: FIXED_TIME,
});

describe("GT-6：SCHEMA_chart_v2.json（ajv strict）", () => {
  it("ゴールデン 10 図の出力が通る", () => {
    for (const [name, spec] of Object.entries(manifest.charts) as [string, any][]) {
      expect(errorsFor(computeChart(inputFor(spec))), name).toEqual([]);
    }
  });

  it("time_unknown の出力が通る", () => {
    const doc = computeChart({
      year: 1985, month: 7, day: 21, latitude: 35.6895, longitude: 139.6917,
      timezoneId: "Asia/Tokyo", timeKnown: false, generatedAt: FIXED_TIME,
    });
    expect(errorsFor(doc)).toEqual([]);
  });

  it("1949 年東京（夏時刻）の出力が通る", () => {
    const doc = computeChart({
      year: 1949, month: 6, day: 1, hour: 12, minute: 0,
      latitude: 35.6895, longitude: 139.6917, timezoneId: "Asia/Tokyo",
      generatedAt: FIXED_TIME,
    });
    expect(errorsFor(doc)).toEqual([]);
  });
});

describe("GT-5(a)：歴史的な夏時刻", () => {
  it("1949-06-01 12:00 Asia/Tokyo は tz_offset 10・dst_applied true", () => {
    const doc = computeChart({
      year: 1949, month: 6, day: 1, hour: 12, minute: 0,
      latitude: 35.6895, longitude: 139.6917, timezoneId: "Asia/Tokyo",
      generatedAt: FIXED_TIME,
    }) as any;
    expect(doc.birth_data.tz_offset).toBe(10);
    expect(doc.birth_data.dst_applied).toBe(true);
    expect(doc.birth_data.timezone_id).toBe("Asia/Tokyo");
    expect(doc.birth_data.time_source).toBe("entered");
  });

  it("IANA 名が使えない環境では数値のオフセットに落ちる", () => {
    const doc = computeChart({
      year: 1985, month: 7, day: 21, hour: 14, minute: 30,
      latitude: 35.6895, longitude: 139.6917, tzOffset: 9,
      timezoneId: "Not/AZone", generatedAt: FIXED_TIME,
    }) as any;
    expect(doc.birth_data.timezone_id).toBeNull();
    expect(doc.birth_data.tz_offset).toBe(9);
    expect(doc.birth_data.dst_applied).toBeNull();
  });
});

describe("GT-5(b)：time_unknown", () => {
  const doc = computeChart({
    year: 1985, month: 7, day: 21, latitude: 35.6895, longitude: 139.6917,
    timezoneId: "Asia/Tokyo", timeKnown: false, generatedAt: FIXED_TIME,
  }) as any;

  it("I-4 の一覧どおりに null になる", () => {
    expect(doc.sect).toBeNull();
    expect(doc.angles).toBeNull();
    expect(doc.houses).toBeNull();
    expect(doc.houses_summary).toBeNull();
    expect(doc.lots).toBeNull();
    expect(doc.planetary_day_hour).toBeNull();
    expect(doc.almuten_figuris).toBeNull();
    expect(doc.vocation).toBeNull();
    expect(doc.vocation_blocked_reason).toBe("birth time unknown");
    for (const p of doc.planets) {
      for (const key of ["house", "house_raw", "near_next_cusp", "above_horizon",
        "accidental_dignity", "sect", "total_score"]) {
        expect(p[key], `${p.name}.${key}`).toBeNull();
      }
    }
    for (const kind of ["mean", "true"]) {
      for (const n of doc.nodes[kind]) expect(n.house).toBeNull();
    }
  });

  it("現地正午で計算し、月の範囲を併記する", () => {
    expect(doc.birth_data.time_known).toBe(false);
    expect(doc.birth_data.time_source).toBe("noon_default");
    expect(doc.birth_data.hour).toBe(12);
    expect(doc.moon_range.sign_at_00_00).toBe("Virgo");
    expect(doc.moon_range.sign_change).toBe(false);
    expect(doc.moon_range.longitude_at_23_59)
      .toBeGreaterThan(doc.moon_range.longitude_at_00_00);
  });

  it("トリプリシティは得点せず、当該天体は peregrine_uncertain", () => {
    for (const p of doc.planets) {
      expect(p.essential_dignity.dignities).not.toContain("triplicity");
      expect(p.essential_dignity.triplicity_rulers.sect_ruler).toBeNull();
    }
    const venus = doc.planets.find((p: any) => p.name === "Venus");
    expect(venus.essential_dignity.score_note).toBe("sect unknown: triplicity not scored");
    const uncertain = doc.planets.filter((p: any) => p.essential_dignity.peregrine_uncertain);
    expect(uncertain.length).toBeGreaterThan(0);
    for (const p of uncertain) expect(p.essential_dignity.peregrine).toBeNull();
  });

  it("アスペクトは天体どうしのみで、注意書きが立つ", () => {
    for (const a of doc.aspects) {
      expect(["ASC", "MC", "Fortune"]).not.toContain(a.from);
      expect(["ASC", "MC", "Fortune"]).not.toContain(a.to);
      expect(a.time_unknown_caveat).toBe(true);
    }
  });

  it("derived は essential_score を序列の基準にし、condition 群は null", () => {
    expect(doc.derived.mode).toBe("time_unknown");
    expect(doc.derived.ranking_basis).toBe("essential_score");
    expect(doc.derived.sect_light_condition).toBeNull();
    expect(doc.derived.asc_lord_condition).toBeNull();
    expect(doc.derived.lot_lords_condition).toBeNull();
    expect(doc.derived.house_conditions).toBeNull();
    expect(doc.derived.aversions_to_ascendant).toBeNull();
    expect(doc.derived.dignity_ranking).toHaveLength(7);
    for (const row of doc.derived.dignity_ranking) expect(row.total_score).toBeNull();
  });

  it("summary の 1・2・5・6 行目が n/a、reading_notes は 6 行", () => {
    const lines = doc.summary.split("\n");
    for (const i of [0, 1, 4, 5]) expect(lines[i]).toBe("n/a (birth time unknown)");
    expect(lines[7]).toContain("Birth time unknown");
    expect(doc.reading_notes).toHaveLength(6);
    expect(doc.reading_notes[5]).toContain("Birth time is unknown");
  });
});

describe("GT-7：決定性", () => {
  it("同一入力は generated_at を除いて byte 一致する", () => {
    const input: ChartInput = {
      year: 1985, month: 7, day: 21, hour: 14, minute: 30,
      latitude: 35.6895, longitude: 139.6917, timezoneId: "Asia/Tokyo", place: "Tokyo",
    };
    const a = JSON.stringify(computeChart({ ...input, generatedAt: FIXED_TIME }));
    const b = JSON.stringify(computeChart({ ...input, generatedAt: FIXED_TIME }));
    expect(a).toBe(b);
    const c = computeChart(input) as any;
    const d = computeChart(input) as any;
    const strip = (x: any) => {
      const copy = { ...x, provenance: { ...x.provenance, generated_at: null } };
      return JSON.stringify(copy);
    };
    expect(strip(c)).toBe(strip(d));
  });

  it("キーの順序がスキーマの properties と同じ", () => {
    const schema = JSON.parse(readFileSync(SCHEMA_PATH, "utf8"));
    const doc = computeChart({
      year: 1985, month: 7, day: 21, hour: 14, minute: 30,
      latitude: 35.6895, longitude: 139.6917, tzOffset: 9, generatedAt: FIXED_TIME,
    });
    expect(Object.keys(doc)).toEqual(Object.keys(schema.properties));
  });
});

describe("v2 のサンプル", () => {
  it("test/golden/sample_chart_v2.json は現在の実装の出力と一致する", () => {
    const saved = readFileSync(join(HERE, "golden", "sample_chart_v2.json"), "utf8");
    const doc = computeChart({
      year: 1985, month: 7, day: 21, hour: 14, minute: 30,
      latitude: 35.6895, longitude: 139.6917, timezoneId: "Asia/Tokyo",
      place: "Tokyo, Japan", generatedAt: "2026-09-19T00:00:00.000Z",
    });
    expect(JSON.stringify(doc, null, 2) + "\n").toBe(saved);
  });

  it("summary は 8 行、reading_notes は 5 行（時刻が分かる図）", () => {
    const doc = computeChart({
      year: 1985, month: 7, day: 21, hour: 14, minute: 30,
      latitude: 35.6895, longitude: 139.6917, tzOffset: 9, generatedAt: FIXED_TIME,
    }) as any;
    expect(doc.summary.split("\n")).toHaveLength(8);
    expect(doc.reading_notes).toHaveLength(5);
    expect(doc.provenance.license).toBeNull();
    expect(doc.provenance.cite_as).toBe("AmanJyoshi — traditionalchart.com");
    expect(doc.tables_used.ephemeris).toEqual({
      library: "astronomy-engine", version: "2.1.19", frame: "true ecliptic of date",
    });
    expect(doc.tables_used.sources.planetary_hours.verified).toBe(false);
    expect(doc.tables_used.sources.planetary_hours.note).toContain("-0.61");
    expect(doc.fixed_star_contacts).toBeNull();
  });
});
