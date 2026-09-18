/**
 * GT-1：tests/test_natal_classical.py の移植（表・トリプリシティ・ペレグリン・アルムテン）。
 * 期待値は Python 版と同一。METHOD_本質的品位表_v1.md v1.2 が正本。
 */
import { describe, expect, it } from "vitest";
import {
  almutenFiguris, almutenOfDegree, essentialDignity, mutualReceptions, resolveAlmuten,
  termRuler,
} from "../src/dignity.ts";
import { receptionBetween } from "../src/aspects.ts";
import { TERMS_TABLES, UNDER_BEAMS_ORB } from "../src/tables.ts";
import { lon } from "./helpers.ts";

const PTOLEMAIC = TERMS_TABLES.ptolemaic_lilly;
const SIGN_INDEX: Record<string, number> = {
  Ari: 0, Tau: 1, Gem: 2, Can: 3, Leo: 4, Vir: 5,
  Lib: 6, Sco: 7, Sag: 8, Cap: 9, Aqu: 10, Pis: 11,
};

// METHOD §4.1 エジプト式ターム（転記）
const METHOD_TERMS_EGYPTIAN: Record<string, [string, number][]> = {
  Ari: [["Jupiter", 6], ["Venus", 12], ["Mercury", 20], ["Mars", 25], ["Saturn", 30]],
  Tau: [["Venus", 8], ["Mercury", 14], ["Jupiter", 22], ["Saturn", 27], ["Mars", 30]],
  Gem: [["Mercury", 6], ["Jupiter", 12], ["Venus", 17], ["Mars", 24], ["Saturn", 30]],
  Can: [["Mars", 7], ["Venus", 13], ["Mercury", 19], ["Jupiter", 26], ["Saturn", 30]],
  Leo: [["Jupiter", 6], ["Venus", 11], ["Saturn", 18], ["Mercury", 24], ["Mars", 30]],
  Vir: [["Mercury", 7], ["Venus", 17], ["Jupiter", 21], ["Mars", 28], ["Saturn", 30]],
  Lib: [["Saturn", 6], ["Mercury", 14], ["Jupiter", 21], ["Venus", 28], ["Mars", 30]],
  Sco: [["Mars", 7], ["Venus", 11], ["Mercury", 19], ["Jupiter", 24], ["Saturn", 30]],
  Sag: [["Jupiter", 12], ["Venus", 17], ["Mercury", 21], ["Saturn", 26], ["Mars", 30]],
  Cap: [["Mercury", 7], ["Jupiter", 14], ["Venus", 22], ["Saturn", 26], ["Mars", 30]],
  Aqu: [["Mercury", 7], ["Venus", 13], ["Jupiter", 20], ["Mars", 25], ["Saturn", 30]],
  Pis: [["Venus", 12], ["Jupiter", 16], ["Mercury", 19], ["Mars", 28], ["Saturn", 30]],
};

describe("ターム表", () => {
  it("エジプト式は METHOD §4.1 と全12行一致する", () => {
    for (const [sign, row] of Object.entries(METHOD_TERMS_EGYPTIAN)) {
      const expected = row.map(([ruler, until]) => ({ until, ruler }));
      expect(TERMS_TABLES.egyptian[SIGN_INDEX[sign]]).toEqual(expected);
    }
  });

  it("表の形が整っている（末尾は 30°・火星か土星・昇順・5 主星）", () => {
    for (const table of [TERMS_TABLES.egyptian, PTOLEMAIC]) {
      for (const row of table) {
        expect(row[row.length - 1].until).toBe(30);
        expect(["Mars", "Saturn"]).toContain(row[row.length - 1].ruler);
        const ends = row.map((c) => c.until);
        expect(ends).toEqual([...ends].sort((a, b) => a - b));
        expect(row.map((c) => c.ruler).sort()).toEqual(
          ["Jupiter", "Mars", "Mercury", "Saturn", "Venus"],
        );
      }
    }
  });

  it("境界はタームの終わりの度数", () => {
    expect(termRuler(lon("Ari", 5.99))).toBe("Jupiter");
    expect(termRuler(lon("Ari", 6.0))).toBe("Venus");
    expect(termRuler(lon("Ari", 29.99))).toBe("Saturn");
  });

  it("Case003 の2例（エジプト式とプトレマイオス式の差）", () => {
    const mercury = lon("Sco", 15 + 41 / 60);
    const mars = lon("Cap", 28 + 30 / 60);
    expect(termRuler(mercury)).toBe("Mercury");
    expect(termRuler(mercury, PTOLEMAIC)).toBe("Venus");
    expect(termRuler(mars)).toBe("Mars");
    expect(termRuler(mars, PTOLEMAIC)).toBe("Saturn");
  });

  it("プトレマイオス式は監査専用で得点に使わない", () => {
    const ed = essentialDignity(lon("Sco", 15 + 41 / 60), "Mercury", true);
    expect(ed.labels).toContain("term");
    expect(ed.score).toBe(2);
    expect(ed.term_audit).toEqual({
      table: "ptolemaic_lilly", ruler: "Venus", differs: true, has_term: false,
    });
    const venus = essentialDignity(lon("Ari", 13), "Venus", true);
    expect(venus.labels).not.toContain("term");
    expect(venus.term_audit.has_term).toBe(true);
  });
});

describe("トリプリシティ", () => {
  it("昼図の風サインの木星（関与星）は +3 を受けない", () => {
    const day = essentialDignity(lon("Aqu", 26), "Jupiter", true);
    expect(day.labels).not.toContain("triplicity");
    expect(day.score).toBe(-5);
    expect(day.triplicity_rulers).toEqual({
      day: "Saturn", night: "Mercury", participating: "Jupiter", sect_ruler: "Saturn",
    });
    const night = essentialDignity(lon("Aqu", 26), "Jupiter", false);
    expect(night.labels).not.toContain("triplicity");
    expect(night.triplicity_rulers.sect_ruler).toBe("Mercury");
  });

  it("セクト主星だけが加点される", () => {
    expect(essentialDignity(lon("Lib", 20), "Mercury", true).labels).toEqual([]);
    const night = essentialDignity(lon("Lib", 20), "Mercury", false);
    expect(night.labels).toEqual(["triplicity"]);
    expect(night.score).toBe(3);
    expect(essentialDignity(lon("Lib", 20), "Saturn", true).labels).toContain("triplicity");
    expect(essentialDignity(lon("Lib", 20), "Saturn", false).labels).not.toContain("triplicity");
  });

  it("METHOD §8.1 の例：昼図の太陽＠獅子＝+8", () => {
    expect(essentialDignity(lon("Leo", 2), "Sun", true).score).toBe(8);
    expect(essentialDignity(lon("Leo", 2), "Sun", false).score).toBe(5);
  });

  it("アルムテンは関与星を数えない", () => {
    const res = almutenOfDegree(lon("Aqu", 26), true);
    expect(res.scores.Jupiter).toBeUndefined();
    expect(res.scores.Saturn).toBe(5 + 3 + 2);
  });

  it("レセプション判定には関与星も用いる", () => {
    expect(receptionBetween("Jupiter", 0, "Mercury", lon("Aqu", 26), true)).toEqual(["triplicity"]);
  });
});

describe("ペレグリン（決定①〜③）", () => {
  it("決定①：ペレグリンは −5", () => {
    const ed = essentialDignity(lon("Aqu", 26), "Jupiter", true);
    expect(ed.peregrine).toBe(true);
    expect(ed.debilities).toEqual(["peregrine"]);
    expect(ed.peregrine_cancelled_by).toBeNull();
    expect(ed.score).toBe(-5);
  });

  it("決定②：サインのミューチュアル・レセプションで解除", () => {
    const positions = { Jupiter: lon("Ari", 25.5), Mars: lon("Pis", 10) };
    const mr = mutualReceptions("Jupiter", positions);
    expect(mr).toEqual([{ with: "Mars", type: "mutual_reception_sign" }]);
    const ed = essentialDignity(positions.Jupiter, "Jupiter", true, { receptions: mr });
    expect(ed.peregrine).toBe(false);
    expect(ed.peregrine_cancelled_by).toBe("mutual_reception_sign");
    expect(ed.debilities).toEqual([]);
    expect(ed.score).toBe(0);
    expect(essentialDignity(positions.Jupiter, "Jupiter", true).score).toBe(-5);
  });

  it("決定②：イグザルテーションのミューチュアル・レセプションで解除", () => {
    const positions = { Mercury: lon("Tau", 25), Moon: lon("Vir", 25) };
    const mr = mutualReceptions("Mercury", positions);
    expect(mr).toEqual([{ with: "Moon", type: "mutual_reception_exaltation" }]);
    const ed = essentialDignity(positions.Mercury, "Mercury", true, { receptions: mr });
    expect(ed.peregrine).toBe(false);
    expect(ed.peregrine_cancelled_by).toBe("mutual_reception_exaltation");
    expect(ed.score).toBe(0);
  });

  it("決定②：mixed（サイン×イグザルテーション）", () => {
    const positions = { Sun: lon("Cap", 20), Mars: lon("Leo", 20) };
    expect(mutualReceptions("Sun", positions)).toEqual([
      { with: "Mars", type: "mutual_reception_mixed" },
    ]);
  });

  it("タームによる相互受容では解除しない", () => {
    const positions = { Jupiter: lon("Ari", 25.5), Saturn: lon("Sag", 5) };
    const mr = mutualReceptions("Jupiter", positions);
    expect(mr).toEqual([]);
    const ed = essentialDignity(positions.Jupiter, "Jupiter", true, { receptions: mr });
    expect(ed.peregrine).toBe(true);
    expect(ed.score).toBe(-5);
  });

  it("決定③：デトリメントと重複加算しない", () => {
    const ed = essentialDignity(lon("Lib", 16), "Mars", true);
    expect(ed.peregrine).toBe(true);
    expect(ed.debilities).toEqual(["detriment"]);
    expect(ed.score).toBe(-5);
    expect(ed.score_note).not.toBeNull();
  });

  it("決定③：フォールと重複加算しない", () => {
    const ed = essentialDignity(lon("Can", 28), "Mars", true);
    expect(ed.peregrine).toBe(true);
    expect(ed.debilities).toEqual(["fall"]);
    expect(ed.score).toBe(-4);
    const night = essentialDignity(lon("Can", 28), "Mars", false);
    expect(night.peregrine).toBe(false);
    expect(night.score_note).toBeNull();
    expect(night.score).toBe(-1);
  });

  it("決定②と③の組み合わせ", () => {
    const positions = { Mars: lon("Lib", 16), Venus: lon("Ari", 16) };
    const mr = mutualReceptions("Mars", positions);
    const ed = essentialDignity(positions.Mars, "Mars", true, { receptions: mr });
    expect(ed.peregrine).toBe(false);
    expect(ed.peregrine_cancelled_by).toBe("mutual_reception_sign");
    expect(ed.debilities).toEqual(["detriment"]);
    expect(ed.score_note).toBeNull();
    expect(ed.score).toBe(-5);
  });

  it("デトリメントでもタームを持てばペレグリンではない", () => {
    const ed = essentialDignity(lon("Lib", 29), "Mars", true);
    expect(ed.peregrine).toBe(false);
    expect(ed.score).toBe(-5 + 2);
  });
});

describe("アルムテンの同点処理", () => {
  it("単独の勝者", () => {
    const res = resolveAlmuten({ Venus: 5, Mars: 3 });
    expect(res.almuten).toBe("Venus");
    expect(res.almuten_tie).toBe(false);
    expect(res.tie_break).toBeNull();
  });

  it("決定④：同点はハウス位置で決める", () => {
    const res = resolveAlmuten({ Jupiter: 6, Moon: 6, Venus: 3 }, { Jupiter: 3, Moon: 10, Venus: 1 });
    expect(res.almuten).toBe("Moon");
    expect(res.almuten_tie).toBe(false);
    expect(res.candidates).toEqual(["Jupiter", "Moon"]);
    expect(res.tie_break).toBe("house_angularity");
  });

  it("サクシーデントはケーデントに勝つ", () => {
    expect(resolveAlmuten({ Saturn: 4, Mars: 4 }, { Saturn: 12, Mars: 11 }).almuten).toBe("Mars");
  });

  it("ハウス位置でも決まらなければ tie", () => {
    const res = resolveAlmuten({ Saturn: 4, Mars: 4, Sun: 4 }, { Saturn: 1, Mars: 7, Sun: 3 });
    expect(res.almuten).toBeNull();
    expect(res.almuten_tie).toBe(true);
    expect(res.candidates).toEqual(["Saturn", "Mars"]);
  });

  it("ハウス情報が無ければ tie", () => {
    const res = resolveAlmuten({ Saturn: 4, Mars: 4 });
    expect(res.almuten_tie).toBe(true);
    expect(res.almuten).toBeNull();
  });

  it("単一度数のアルムテンはハウス位置を使う", () => {
    const res = almutenOfDegree(lon("Can", 25 + 19 / 60), true, undefined, { Jupiter: 3, Moon: 10 });
    expect(res.scores.Jupiter).toBe(6);
    expect(res.scores.Moon).toBe(6);
    expect(res.almuten).toBe("Moon");
  });

  it("決定⑤：フィギュリスの同点は共同アルムテン", () => {
    const res = almutenFiguris({ asc: lon("Can", 25 + 19 / 60) }, true, { Jupiter: 99 },
      undefined, { Jupiter: 3, Moon: 10 });
    expect(res.almuten_tie).toBe(true);
    expect(res.almutens).toEqual(["Jupiter", "Moon"]);
    expect(res.almuten).toBeNull();
    expect(res).not.toHaveProperty("tie_break");
  });

  it("フィギュリスの単独勝者", () => {
    const res = almutenFiguris({ asc: lon("Leo", 2), sun: lon("Leo", 2) }, true, {}, undefined,
      { Sun: 12 });
    expect(res.almuten_tie).toBe(false);
    expect(res.almutens).toEqual(["Sun"]);
    expect(res.almuten).toBe("Sun");
  });
});

// UNDER_BEAMS_ORB は solar_phase.test.ts でも使うのでここで型を確かめておく
it("定数が Python の書き出しから読めている", () => {
  expect(UNDER_BEAMS_ORB).toBe(17.0);
});
