/**
 * 惑星の Joy（喜悦）。ヘレニズム由来の固定表。
 * Lilly は各ハウスの章で joy に触れるが、偶発品位の表には入れていない
 * （典拠は METHOD 側で確定中。2026-09-21 時点で [未照合]）。
 * したがって **得点には一切加算しない**。出方を示す記述層である。
 */
import joysData from "../data/joys.json" with { type: "json" };

export const JOYS = joysData.joys as Record<string, number>;

/** house は 5°規則の適用後（houseEffective）を渡すこと。 */
export function isInJoy(planet: string, house: number | null): boolean | null {
  if (house == null) return null;
  const j = JOYS[planet];
  return j === undefined ? false : house === j;
}
