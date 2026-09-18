/**
 * 古典的アスペクト（プトレマイオス5種）、モイエティ合算のオーブ、
 * アプライ／セパレート、レセプション。natal_classical.py の対応関数を写す。
 */
import { essentialDignity } from "./dignity.ts";
import {
  CLASSICAL_ASPECTS, MOIETY, PARTILE_ORB, POINT_MOIETY, type TriplicityRow,
} from "./tables.ts";
import { roundTo, signedSep } from "./util.ts";

export interface AspectBody {
  name: string;
  nameJa?: string;
  longitude: number;
  speed: number;
  isPoint?: boolean;
}

export interface ClassicalAspect {
  planet1: string;
  planet2: string;
  aspect: string;
  orb: number;
  max_orb: number;
  partile: boolean;
  state: "applying" | "separating";
  direction: "sinister" | "dexter";
  reception_1to2: string[];
  reception_2to1: string[];
  mutual_reception: boolean;
}

/** 離角の絶対値の時間変化から接近・分離を判定する */
export function aspectState(
  lon1: number, spd1: number, lon2: number, spd2: number, angle: number,
): "applying" | "separating" {
  const delta = signedSep(lon2, lon1);
  const actual = Math.abs(delta);
  const rel = spd1 - spd2;
  const dActual = delta >= 0 ? rel : -rel;
  if (actual > angle) return dActual < 0 ? "applying" : "separating";
  return dActual > 0 ? "applying" : "separating";
}

/**
 * p1 が p2 を、どの品位で受容しているか。
 * トリプリシティは関与星による受容も認める（METHOD §3：得点はしないが判定には使う）。
 */
export function receptionBetween(
  p1: string, lon1: number, p2: string, lon2: number, isDay: boolean,
  tripTable?: Record<string, TriplicityRow>,
): string[] {
  const ed = essentialDignity(lon2, p1, isDay, { tripTable });
  const labels = [...ed.labels];
  if (!labels.includes("triplicity") && ed.triplicity_rulers.participating === p1) {
    const pos = ["domicile", "exaltation"].filter((l) => labels.includes(l)).length;
    labels.splice(pos, 0, "triplicity");
  }
  return labels;
}

/** オーブ内の古典アスペクトを検出する。オーブは両天体のモイエティの和 */
export function findClassicalAspects(
  bodies: AspectBody[], isDay: boolean, tripTable?: Record<string, TriplicityRow>,
): ClassicalAspect[] {
  const aspects: ClassicalAspect[] = [];
  for (let i = 0; i < bodies.length; i++) {
    for (let j = i + 1; j < bodies.length; j++) {
      const b1 = bodies[i];
      const b2 = bodies[j];
      const diff = Math.abs(signedSep(b1.longitude, b2.longitude));
      const m1 = b1.isPoint ? POINT_MOIETY : MOIETY[b1.name];
      const m2 = b2.isPoint ? POINT_MOIETY : MOIETY[b2.name];
      const maxOrb = m1 + m2;

      for (const { angle, name } of CLASSICAL_ASPECTS) {
        const dev = Math.abs(diff - angle);
        if (dev > maxOrb) continue;
        const state = aspectState(b1.longitude, b1.speed, b2.longitude, b2.speed, angle);
        const forward = signedSep(b1.longitude, b2.longitude) > 0;
        let rec1: string[] = [];
        let rec2: string[] = [];
        if (!b1.isPoint && !b2.isPoint) {
          rec1 = receptionBetween(b1.name, b1.longitude, b2.name, b2.longitude, isDay, tripTable);
          rec2 = receptionBetween(b2.name, b2.longitude, b1.name, b1.longitude, isDay, tripTable);
        }
        aspects.push({
          planet1: b1.name,
          planet2: b2.name,
          aspect: name,
          orb: roundTo(dev, 2),
          max_orb: roundTo(maxOrb, 2),
          partile: dev <= PARTILE_ORB,
          state,
          direction: forward ? "sinister" : "dexter",
          reception_1to2: rec1,
          reception_2to1: rec2,
          mutual_reception: rec1.length > 0 && rec2.length > 0,
        });
      }
    }
  }
  aspects.sort((a, b) => (Number(!a.partile) - Number(!b.partile)) || (a.orb - b.orb));
  return aspects;
}

const SOFTENING_ASPECTS = ["square", "opposition"];
const MAJOR_RECEPTIONS = ["domicile", "exaltation"];

/**
 * レセプションがアスペクトを和らげるか（要件書 I-2、プロジェクト慣行）。
 * スクエア／オポジションで、相互受容またはドミサイル／イグザルテーションによる
 * 片受容があれば softens。ターム／フェイスだけの受容は minor に分ける。
 */
export function receptionSoftening(
  aspect: Pick<ClassicalAspect, "aspect" | "reception_1to2" | "reception_2to1" | "mutual_reception">,
): { softens: boolean; minor: boolean } {
  const all = [...aspect.reception_1to2, ...aspect.reception_2to1];
  if (!all.length) return { softens: false, minor: false };
  const hasMajor = all.some((r) => MAJOR_RECEPTIONS.includes(r));
  if (!SOFTENING_ASPECTS.includes(aspect.aspect)) {
    return { softens: false, minor: !hasMajor };
  }
  const softens = aspect.mutual_reception || hasMajor;
  return { softens, minor: !softens };
}

/** アンティシャ（蟹0°／山羊0°軸の鏡像）と反アンティシャ */
export function antiscia(lon: number): { antiscion: number; contraAntiscion: number } {
  return {
    antiscion: ((180 - lon) % 360 + 360) % 360,
    contraAntiscion: ((360 - lon) % 360 + 360) % 360,
  };
}
