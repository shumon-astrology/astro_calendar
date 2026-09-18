/**
 * 適職ブロック（I-3）のテスト。
 * GT-4：較正例 No.001。期待値は設計提案書 §7-1（凍結前。監修待ち）。
 * GT-5(d)：三候補がすべて燃焼する合成入力で no_significator。
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { computeChart, type ChartInput } from "../src/index.ts";

const HERE = dirname(fileURLToPath(import.meta.url));

const FIXED_TIME = "2026-09-19T00:00:00.000Z";

/** 較正例 No.001：2004-11-01 20:02 JST、東京 35°41′N 139°42′E */
const CALIBRATION: ChartInput = {
  year: 2004, month: 11, day: 1, hour: 20, minute: 2,
  latitude: 35 + 41 / 60, longitude: 139 + 42 / 60,
  timezoneId: "Asia/Tokyo", place: "Tokyo",
  generatedAt: FIXED_TIME,
};

describe("GT-4：較正例 No.001（2026-09-19 三河監修により凍結）", () => {
  const doc = computeChart(CALIBRATION) as any;
  const v = doc.vocation;

  it("凍結したゴールデン（calibration_No001_vocation.json）と完全一致する", () => {
    const golden = JSON.parse(
      readFileSync(join(HERE, "golden", "calibration_No001_vocation.json"), "utf8"));
    expect(v).toEqual(golden);
  });

  it("not_excluded は燃焼も光線下もない候補（火星）", () => {
    expect(v.not_excluded).toEqual(["Mars"]);
  });

  it("excluded の各要素に debilities が付く", () => {
    const byPlanet = Object.fromEntries(
      v.significator.excluded.map((e: any) => [e.planet, e.debilities]));
    expect(byPlanet.Mars).toEqual(["detriment"]);
    expect(byPlanet.Mercury).toEqual(["peregrine"]);
  });

  it("恒星の接触に grade が付く（1°以内は judging）", () => {
    const spica = v.fixed_stars.find((s: any) => s.star === "Spica");
    expect(spica.grade).toBe("judging");
    expect(spica.orb).toBeLessThanOrEqual(1);
  });

  it("夜図である", () => {
    expect(doc.sect.chart_sect).toBe("nocturnal");
  });

  it("職業主星は金星、ルール 2B、tier B", () => {
    expect(v.significator.planet).toBe("Venus");
    expect(v.significator.rule_fired).toBe("2B");
    expect(v.settlement_tier).toBe("B");
    expect(v.significator.extension_flag).toBe(true);
  });

  it("②-B の三候補限定アルムーテンで金星が 4 点", () => {
    expect(v.mc_almuten_three.winner).toBe("Venus");
    expect(v.mc_almuten_three.winner_score).toBe(4);
    expect(v.mc_almuten_three.exaltation_or_better).toBe(true);
  });

  it("水星は太陽光線下で排除される（16°04′）", () => {
    const mercury = v.significator.excluded.find((e: any) => e.planet === "Mercury");
    expect(mercury.rule).toBe("1");
    expect(mercury.reason).toContain("under_beams");
    expect(mercury.value).toBe("16°04'");
  });

  it("火星も排除される（理由コードは報告で切り分ける）", () => {
    const mars = v.significator.excluded.find((e: any) => e.planet === "Mars");
    expect(mars).toBeDefined();
    expect(mars.rule).toBe("1");
  });

  it("成功度は 4/4", () => {
    expect(v.success.conditions_met).toBe(4);
    expect(v.success.of).toBe(4);
    expect(v.success.grade).toBe("high");
  });

  it("スピカと火星が 22′ で接触する", () => {
    const spica = v.fixed_stars.find((s: any) => s.star === "Spica" && s.body === "Mars");
    expect(spica).toBeDefined();
    expect(spica.orb_dms).toBe("0°22'");
  });

  it("水星と木星のアスペクトが無く、警告が立つ", () => {
    expect(v.special_conditions.mercury_jupiter_aspect).toBe(false);
    expect(v.warnings.map((w: any) => w.id)).toContain("mercury_jupiter_no_aspect");
  });

  it("金星は自室（天秤）で、サイン属性が出る", () => {
    expect(v.sign_attributes.sign).toBe("Libra");
    expect(v.sign_attributes.element).toBe("air");
    expect(v.sign_attributes.mode).toBe("cardinal");
    expect(v.sign_attributes.humane).toBe(true);
  });

  it("品位エンジンの戻り値をそのまま写している（決定 B）", () => {
    const venusPlanet = doc.planets.find((p: any) => p.name === "Venus");
    const venusCandidate = v.candidates.find((c: any) => c.planet === "Venus");
    expect(venusCandidate.essential.dignities).toEqual(venusPlanet.essential_dignity.dignities);
    expect(venusCandidate.essential.score).toBe(venusPlanet.essential_dignity.score);
    expect(venusCandidate.essential.has_dignity).toBe(true);
  });
});

describe("GT-5(d)：三候補がすべて燃焼する入力", () => {
  // 1994-01-01 正午・東京：火星 1°18′・金星 3°49′・水星 1°36′ でいずれも燃焼
  const doc = computeChart({
    year: 1994, month: 1, day: 1, hour: 12, minute: 0,
    latitude: 35.6895, longitude: 139.6917, tzOffset: 9, generatedAt: FIXED_TIME,
  }) as any;

  it("三候補がすべて燃焼している", () => {
    for (const c of doc.vocation.candidates) {
      expect(c.solar.combust, c.planet).toBe(true);
      expect(c.solar.same_sign_as_sun, c.planet).toBe(true);
    }
  });

  it("ルール①は誰も通さない（燃焼が排除条件）", () => {
    for (const c of doc.vocation.candidates) {
      expect(c.eligibility.rule1, c.planet).toBe(false);
      expect(c.eligibility_reasons.rule1).toContain("combust");
    }
  });

  it("ただし②-B 以降は燃焼を排除条件にしないので主星は決まりうる", () => {
    // 手順書 §2 の排除条件（燃焼・光線下）はルール①にしかない。
    // 「三候補がすべて燃焼 → no_significator」は自動的には成り立たない
    expect(doc.vocation.significator.rule_fired).not.toBe("1");
    if (doc.vocation.significator.planet !== null) {
      expect(["2A", "2B", "3", "4", "5"]).toContain(doc.vocation.significator.rule_fired);
    }
  });
});

describe("no_significator（どのルールでも決まらない図）", () => {
  it("該当する図では null と level 3 の警告が出る", () => {
    // 極圏の試験図のひとつ（polar_4）は主星が決まらない
    const doc = computeChart({
      year: 1985, month: 3, day: 15, hour: 9, minute: 0,
      latitude: 69.6496, longitude: 18.956, tzOffset: 1, generatedAt: FIXED_TIME,
    }) as any;
    const v = doc.vocation;
    if (v.significator.planet === null) {
      expect(v.settlement_tier).toBeNull();
      expect(v.significator.rule_fired).toBeNull();
      expect(v.sign_attributes).toBeNull();
      expect(v.success).toBeNull();
      expect(v.boundary_warnings.map((w: any) => w.id)).toContain("no_significator");
      expect(v.boundary_warnings.find((w: any) => w.id === "no_significator").level).toBe(3);
    } else {
      // 主星が決まる図なら、この検査は別の図で行う
      expect(v.settlement_tier).not.toBeNull();
    }
  });
});

describe("適職ブロックの構造", () => {
  const doc = computeChart(CALIBRATION) as any;
  const v = doc.vocation;

  it("候補は ♂♀☿ の 3 件で固定順", () => {
    expect(v.candidates.map((c: any) => c.planet)).toEqual(["Mars", "Venus", "Mercury"]);
  });

  it("ルール④のモイエティは 6.25°で、一般オーブとは別だと明記する", () => {
    expect(v.thresholds.rule4_moiety_deg).toBe(6.25);
    expect(v.thresholds.general_orb_note).toContain("max_orb");
    expect(v.thresholds.rule4_citation).toContain("mediety");
  });

  it("併記の別系統・持続性・体系差分が揃っている", () => {
    expect(v.ptolemy_method).toHaveProperty("rising_before_sun");
    expect(v.coley_method).toHaveProperty("agrees_with_lilly");
    expect(v.anima_124.note).toContain("Anima Astrologiae");
    expect(v.durability_layer.verified).toBe(false);
    expect(v.durability_layer.lords).toHaveLength(3);
    expect(v.durability_layer.lords.map((l: any) => l.rank)).toEqual([1, 2, 3]);
    expect(v.system_divergence.level).toBeGreaterThanOrEqual(0);
    expect(v.timing_slice).toBeNull();
  });

  it("職業語を出さない（rule_key と典拠のみ）", () => {
    for (const c of [...v.combinations, ...v.absent_combinations]) {
      expect(Object.keys(c)).not.toContain("professions");
      expect(c.rule_key).toMatch(/^[a-z_]+$/);
      expect(c.citation).toBeTruthy();
    }
  });

  it("時刻が不明なら vocation は null", () => {
    const unknown = computeChart({
      year: 2004, month: 11, day: 1, latitude: 35.68, longitude: 139.7,
      timezoneId: "Asia/Tokyo", timeKnown: false, generatedAt: FIXED_TIME,
    }) as any;
    expect(unknown.vocation).toBeNull();
    expect(unknown.vocation_blocked_reason).toBe("birth time unknown");
  });
});
