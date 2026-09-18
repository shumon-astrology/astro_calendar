/**
 * v2 で新設した出所ラベル（`tables_used.sources` の追加分）。
 * 既存 16 項目は Python の TABLE_SOURCES をそのまま写す（tables.ts）。
 * 形は既存と同じ {table, table_ja, label, citation, verified, reference, note}。
 */
import { RISE_SET_ALTITUDE_DEG } from "./ephemeris.ts";
import { SPICA_NOTE } from "./fixed_stars.ts";
import { THRESHOLDS } from "./derived.ts";

const METHOD_NATAL = "METHOD_natal_v1.md v1.3";

export const JS_TABLE_SOURCES: Record<string, unknown> = {
  lots: {
    table: "Lots of Fortune and Spirit (sect-reversed)",
    table_ja: "フォーチュン／スピリット（夜図で反転）",
    label: "プロジェクト慣行",
    citation: `${METHOD_NATAL} STEP 8-6`,
    verified: true,
    reference: "Dorotheus I.28,11 / I.9,1 (Dykes)",
    note: "昼： ASC ＋ ☽ − ☉／夜： ASC ＋ ☉ − ☽（スピリットはその逆）。"
      + "昼式をそのまま使った値も non_reversed_longitude に併記する（決定 6）",
  },
  fixed_stars: {
    table: "Fixed stars (Regulus, Spica, Algol)",
    table_ja: "恒星 3 星（レグルス・スピカ・アルゴル）",
    label: "プロジェクト慣行",
    citation: null,
    verified: false,
    reference: "natal_classical.py の FIXED_STARS_J2000（J2000 黄経＋歳差 50.29″/年）",
    note: SPICA_NOTE,
  },
  star_catalog: {
    table: "Star catalogue (reserved)",
    table_ja: "恒星カタログ（予約）",
    label: "プロジェクト慣行",
    citation: null,
    verified: false,
    reference: "—",
    note: "新しい星集合（ロイヤルスター 6＋その他 4〜6）は METHOD 側で確定してから。"
      + "v2 rev.1 では fixed_star_contacts は null",
  },
  triplicity_order: {
    table: "Ordered Dorothean triplicity rulers (1st / 2nd / participating)",
    table_ja: "ドロテウス式トリプリシティの順序組",
    label: "プロジェクト慣行",
    citation: null,
    verified: false,
    reference: "Dorotheus Carmen I.1, 4–7（古典職業鑑定マニュアル v11 §2）",
    note: "得点は第 1 位（セクト主星）のみ +3。順序組は rank/role として出すだけで、"
      + "durability_layer（Phase 4）が読む",
  },
  triplicity_audit: {
    table: "Ptolemaic triplicity table (audit only)",
    table_ja: "プトレマイオス式トリプリシティ（監査用）",
    label: "リリー本文",
    citation: null,
    verified: false,
    reference: "体系差分検出_実装仕様_20260808.md §5.3",
    note: "体系差分（Phase 4）の並行計算用。判定には使わない。v2 rev.1 では未実装",
  },
  vocation_rules: {
    table: "Vocational combination table and sign attributes",
    table_ja: "適職の組合せ表・サイン属性表",
    label: "プロジェクト慣行",
    citation: null,
    verified: false,
    reference: "古典職業鑑定マニュアル_20260809_v11.md §4-1・§5",
    note: "Phase 4 で data/vocation_rules.json に写す。職業語は入れない",
  },
  derived_thresholds: {
    table: "Thresholds for derived.classification",
    table_ja: "derived の分類の閾値",
    label: "プロジェクト慣行",
    citation: `${METHOD_NATAL} 決定 5`,
    verified: false,
    reference: "—",
    note: `暫定運用値：favoured は本質 ≥ ${THRESHOLDS.favoured.essential_min} かつ偶発 `
      + `≥ ${THRESHOLDS.favoured.accidental_min}、effort は本質 ≤ `
      + `${THRESHOLDS.effort.essential_max} かつ偶発 ≤ ${THRESHOLDS.effort.accidental_max}。`
      + "試験図 3 図の後に見直す",
  },
  planetary_hours: {
    table: "Sunrise and sunset used for the planetary day and hour",
    table_ja: "惑星時に使う日の出・日の入の定義",
    label: "プロジェクト慣行",
    citation: null,
    verified: false,
    reference: "natal_classical.py（swe.rise_trans, BIT_DISC_CENTER）",
    note: "視位置（大気差あり、1013.25 hPa・0 ℃）・太陽の円盤中心・海抜 0 m。"
      + `JS は Astronomy Engine の SearchAltitude に較正値 ${RISE_SET_ALTITUDE_DEG}° を渡し、`
      + "Python との差は最大 1.6 秒。CA Book I の日出の定義との照合は未了",
  },
};
