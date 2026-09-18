/**
 * 品位表・オーブ・偶発点の読み込み。
 * 値は scripts/export_tables.py が natal_classical.py の定数から機械書き出ししたもの。
 * このファイル以外で data/*.json を読んではならない（表の二重管理を防ぐ）。
 */
import dignityData from "../data/tables_dignity.json" with { type: "json" };
import orbsData from "../data/orbs.json" with { type: "json" };
import accidentalData from "../data/accidental_points.json" with { type: "json" };
import sourcesData from "../data/table_sources.json" with { type: "json" };

export type TermCell = { until: number; ruler: string };

export const DOMICILE_BY_SIGN = dignityData.domicile_by_sign as string[];
export const DETRIMENT_BY_SIGN = dignityData.detriment_by_sign as string[];
export const EXALT_BY_SIGN = dignityData.exalt_by_sign as Record<string, { planet: string; degree: number }>;
export const FALL_BY_SIGN = dignityData.fall_by_sign as Record<string, { planet: string; degree: number }>;
export const FACES = dignityData.faces as string[][];
export const DIGNITY_SCORE = dignityData.dignity_scores as Record<string, number>;
export const ANGULAR_HOUSES = dignityData.angular_houses as number[];
export const SUCCEDENT_HOUSES = dignityData.succedent_houses as number[];

export const TERMS_TABLES = dignityData.terms.tables as Record<string, TermCell[][]>;
export const DEFAULT_TERMS = dignityData.terms.default as string;
export const TERMS_AUDIT = dignityData.terms.audit as string;

export type TriplicityRow = { day: string; night: string; participating: string | null };
export const TRIPLICITY_TABLES = dignityData.triplicity.tables as Record<string, Record<string, TriplicityRow>>;
export const DEFAULT_TRIPLICITY = dignityData.triplicity.default as string;

export const PLANET_ORB = orbsData.planet_orb as Record<string, number>;
export const MOIETY = orbsData.moiety as Record<string, number>;
export const POINT_MOIETY = orbsData.point_moiety as number;
export const PARTILE_ORB = orbsData.partile_orb as number;
export const CAZIMI_ORB = orbsData.cazimi_orb as number;
export const COMBUST_ORB = orbsData.combust_orb as number;
export const UNDER_BEAMS_ORB = orbsData.under_beams_orb as number;
export const MEAN_MOTION = orbsData.mean_motion as Record<string, number>;
export const CLASSICAL_ASPECTS = orbsData.aspects as { angle: number; name: string; abbrev: string; name_ja: string }[];
export const CUSP_THRESHOLD = orbsData.cusp_threshold as number;

export const HOUSE_SCORE = accidentalData.house_score as Record<string, number>;
export const BENEFICS = accidentalData.benefics as string[];
export const MALEFICS = accidentalData.malefics as string[];
export const LUMINARIES = accidentalData.luminaries as string[];
export const DIURNAL_PLANETS = accidentalData.diurnal_planets as string[];
export const NOCTURNAL_PLANETS = accidentalData.nocturnal_planets as string[];
export const WEEKDAY_RULERS = accidentalData.weekday_rulers as string[];
export const HOUR_ORDER = accidentalData.hour_order as string[];
export const FIXED_STARS_J2000 = accidentalData.fixed_stars_j2000 as Record<string, number>;
export const PRECESSION_PER_YEAR = accidentalData.precession_per_year as number;
export const PLANET_JA = accidentalData.planet_ja as Record<string, string>;

export const TABLE_SOURCES = sourcesData.table_sources as Record<string, unknown>;
export const SECT_METHOD = sourcesData.sect_method as string;
export const PEREGRINE_SCORE_NOTE = sourcesData.peregrine_score_note as string;
