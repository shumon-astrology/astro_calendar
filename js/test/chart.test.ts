/**
 * GT-1 の残り（決定 C・惑星時・セクト・サンプル図）と GT-2（ゴールデン比較）。
 * 期待値は tests/test_natal_classical.py と同一。
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { compareAll } from "../cli/compare.ts";
import { solarPhase } from "../src/accidental.ts";
import { isDayChart, sectInfo } from "../src/lots.ts";
import { computeChart } from "../src/index.ts";
import { UNDER_BEAMS_ORB } from "../src/tables.ts";
import { localToJd } from "../src/time.ts";
import { lon, minutesFrom } from "./helpers.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const golden = (name: string) =>
  JSON.parse(readFileSync(join(HERE, "golden", `${name}.json`), "utf8"));

const TOKYO = {
  year: 1985, month: 7, day: 21, hour: 14, minute: 30,
  latitude: 35.6895, longitude: 139.6917, tzOffset: 9,
};

describe("決定 C：太陽との関係は同一サインを要する", () => {
  it("別サインなら光線下の範囲でも free", () => {
    const sun = lon("Cap", 10 + 26 / 60);
    const jup = lon("Sag", 29 + 36 / 60);
    expect(Math.abs(((jup - sun + 540) % 360) - 180)).toBeLessThan(UNDER_BEAMS_ORB);
    const sp = solarPhase(jup, sun, "Jupiter");
    expect(sp.state).toBe("free");
    expect(sp.same_sign_as_sun).toBe(false);
  });

  it("燃焼のオーブ内でも別サインなら free", () => {
    const sun = lon("Leo", 1);
    const ven = lon("Can", 28);
    expect(solarPhase(ven, sun, "Venus").distance).toBeCloseTo(3.0, 6);
    expect(solarPhase(ven, sun, "Venus").state).toBe("free");
    expect(solarPhase(lon("Leo", 4), sun, "Venus").state).toBe("combust");
  });

  it("同サインの判定は従来どおり", () => {
    const sun = lon("Can", 28 + 24 / 60);
    expect(solarPhase(lon("Can", 27 + 26 / 60), sun, "Mars").state).toBe("combust");
    expect(solarPhase(lon("Can", 28 + 30 / 60), sun, "Mercury").state).toBe("cazimi");
    expect(solarPhase(lon("Can", 18), sun, "Mercury").state).toBe("under_beams");
  });

  it("試験図 A の木星は free", () => {
    const c = computeChart({
      year: 1996, month: 1, day: 1, hour: 23, minute: 7,
      latitude: 33.6, longitude: 130.4167, tzOffset: 9,
    }) as any;
    const jup = c.planets.find((p: any) => p.name === "Jupiter");
    expect(jup.position).toBe("Sag 29°36'");
    expect(jup.accidental_dignity.solar_phase).toBe("free");
    expect(jup.accidental_dignity.distance_from_sun).toBeGreaterThan(8.5);
    expect(jup.accidental_dignity.distance_from_sun).toBeLessThan(17.0);
    const codes = jup.accidental_dignity.items.map((i: any) => i.code);
    expect(codes).toContain("free_of_beams");
    expect(codes).not.toContain("under_beams");
  });
});

describe("惑星時（現地時刻で扱う）", () => {
  const phOf = (input: Parameters<typeof computeChart>[0]) =>
    (computeChart(input) as any).planetary_day_hour;

  it("ストックホルム UTC+1", () => {
    const ph = phOf({
      year: 1915, month: 8, day: 29, hour: 3, minute: 30,
      latitude: 59.3333, longitude: 18.05, tzOffset: 1,
    });
    // Python は 04:33、JS は 04:34（分の切り捨て境界。差は 1 分以内で GT-2 の許容内）
    expect(minutesFrom(ph.sunrise, "1915-08-28 04:33")).toBeLessThanOrEqual(2);
    expect(ph.sunset).toBe("1915-08-28 19:02");
    expect(ph.day_ruler).toBe("Saturn");
    expect(ph.is_daytime).toBe(false);
    expect(ph.sunset.split(" ")[1] >= "16:00" && ph.sunset.split(" ")[1] < "20:00").toBe(true);
  });

  it("シドニー UTC+10", () => {
    const ph = phOf({
      year: 1968, month: 10, day: 12, hour: 13, minute: 0,
      latitude: -33.8667, longitude: 151.2167, tzOffset: 10,
    });
    expect(ph.sunrise).toBe("1968-10-12 05:19");
    expect(ph.day_ruler).toBe("Saturn");
    expect(ph.is_daytime).toBe(true);
    const [srDate, srTime] = ph.sunrise.split(" ");
    const [ssDate, ssTime] = ph.sunset.split(" ");
    expect(srDate).toBe("1968-10-12");
    expect(ssDate).toBe("1968-10-12");
    expect(srTime >= "05:00" && srTime < "08:00").toBe(true);
    expect(ssTime >= "16:00" && ssTime < "20:00").toBe(true);
  });

  it("曜日主星は現地の日付で決まる（ホノルル UTC−10）", () => {
    const ph = phOf({
      year: 2000, month: 3, day: 1, hour: 5, minute: 0,
      latitude: 21.3, longitude: -157.85, tzOffset: -10,
    });
    expect(ph.sunrise.split(" ")[0]).toBe("2000-02-29");
    expect(ph.day_ruler).toBe("Mars");
  });

  it("東京は従来どおり", () => {
    const ph = phOf(TOKYO);
    expect([ph.sunrise, ph.sunset, ph.day_ruler])
      .toEqual(["1985-07-21 04:41", "1985-07-21 18:53", "Sun"]);
  });
});

describe("セクト", () => {
  it("地平線基準", () => {
    const asc = lon("Sco", 28);
    expect(isDayChart(lon("Can", 28), asc)).toBe(true);
    expect(isDayChart(lon("Sag", 10), asc)).toBe(false);
  });

  it("東京のサンプルは borderline ではない", () => {
    const c = computeChart(TOKYO) as any;
    expect(c.sect.method).toBe("horizon_asc_dsc");
    expect(c.sect.is_day).toBe(true);
    expect(c.sect.sun_altitude).toBeGreaterThan(0);
    expect(c.sect.borderline).toBe(false);
  });

  it("極圏の白夜は borderline", () => {
    const jd = localToJd(2020, 6, 21, 0, 0, 1);
    const info = sectInfo(
      (computeChart({
        year: 2020, month: 6, day: 21, hour: 0, minute: 0,
        latitude: 78.2, longitude: 15.6, tzOffset: 1,
      }) as any).planets.find((p: any) => p.name === "Sun").longitude,
      (computeChart({
        year: 2020, month: 6, day: 21, hour: 0, minute: 0,
        latitude: 78.2, longitude: 15.6, tzOffset: 1,
      }) as any).angles.ascendant.longitude,
      jd, 78.2, 15.6,
    );
    expect(info.is_day).toBe(false);
    expect(info.sun_altitude).toBeGreaterThan(10);
    expect(info.altitude_is_day).toBe(true);
    expect(info.borderline).toBe(true);
  });
});

describe("サンプル図（Python のゴールデンと同じ値）", () => {
  it("v1 の主要キーが一致する", () => {
    const c = computeChart(TOKYO) as any;
    const g = golden("sample_tokyo_1985");
    expect(c.angles.ascendant.position).toBe(g.angles.ascendant.position);
    expect(c.almuten_figuris.almutens).toEqual(g.almuten_figuris.almutens);
    // 黄経は 0.02° 以内。度分の文字列は分の切り捨て境界で 1 分ずれることがある
    // （このサンプルでは火星 Can 27°26'/27' が該当。差は 0.0002°）
    c.planets.forEach((p: any, i: number) => {
      const q = g.planets[i];
      expect(p.name).toBe(q.name);
      expect(Math.abs(p.longitude - q.longitude)).toBeLessThanOrEqual(0.02);
      expect(p.sign).toBe(q.sign);
    });
    expect(c.planets.map((p: any) => p.total_score))
      .toEqual(g.planets.map((p: any) => p.total_score));
    expect(c.aspects.map((a: any) => [a.from, a.to, a.aspect]))
      .toEqual(g.aspects.map((a: any) => [a.from, a.to, a.aspect]));
  });

  it("tables_used の宣言", () => {
    const c = computeChart(TOKYO) as any;
    expect(c.tables_used.terms).toBe("egyptian");
    expect(c.tables_used.terms_audit).toBe("ptolemaic_lilly");
    expect(c.tables_used.triplicity).toBe("dorothean");
    expect(c.tables_used.house_system).toEqual({ code: "R", name: "Regiomontanus" });
    expect(c.tables_used.ephemeris.frame).toBe("true ecliptic of date");
  });
});

describe("GT-2：Python ゴールデンとの差分", () => {
  const { diffs, charts } = compareAll();

  it("10 図を比較している", () => {
    expect(charts).toHaveLength(10);
  });

  it("合否に数える差分が無い（numeric / discrete / time）", () => {
    const failing = diffs.filter((d) => ["numeric", "discrete", "time"].includes(d.kind));
    expect(failing.map((d) => `${d.chart}${d.path}: py=${d.python} js=${d.js}`)).toEqual([]);
  });

  it("恒星の差は Spica だけ（方式の混在。報告のみ）", () => {
    const stars = new Set(diffs.filter((d) => d.kind === "fixed_star")
      .map((d) => d.path.split("/")[2]));
    expect([...stars]).toEqual(["Spica"]);
  });
});
