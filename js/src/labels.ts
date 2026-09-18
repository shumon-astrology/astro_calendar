/**
 * 偶発的品位の項目の英語ラベル（`accidental_dignity.items[].label_en`）。
 * 日本語ラベル（Python 由来）は label_ja として残す。ハウスの項目だけは
 * コードから組み立てる（house_1 … house_12）。
 */
const FIXED: Record<string, string> = {
  direct: "direct motion",
  retrograde: "retrograde",
  swift: "swift (faster than mean motion)",
  slow: "slow (slower than mean motion)",
  oriental: "oriental",
  occidental: "occidental",
  increasing_light: "increasing in light",
  decreasing_light: "decreasing in light",
  cazimi: "cazimi",
  combust: "combust",
  under_beams: "under the Sun's beams",
  free_of_beams: "free of the beams",
  partile_conjunction_north_node: "partile conjunction with the North Node",
  partile_conjunction_south_node: "partile conjunction with the South Node",
  besieged_saturn_mars: "besieged between Saturn and Mars",
  conjunct_regulus: "conjunct Regulus",
  conjunct_spica: "conjunct Spica",
  conjunct_algol: "conjunct Algol (within 5°)",
};

const PLANET_EN: Record<string, string> = {
  jupiter: "Jupiter", venus: "Venus", saturn: "Saturn", mars: "Mars",
  mercury: "Mercury", sun: "the Sun", moon: "the Moon",
};

const ASPECT_EN: Record<string, string> = {
  conjunction: "conjunction",
  trine: "trine",
  sextile: "sextile",
  opposition: "opposition",
  square: "square",
};

function partileLabel(code: string): string | null {
  const m = code.match(/^partile_(conjunction|trine|sextile|opposition|square)_(\w+)$/);
  if (!m || !PLANET_EN[m[2]]) return null;
  return `partile ${ASPECT_EN[m[1]]} with ${PLANET_EN[m[2]]}`;
}

export const ACCIDENTAL_LABELS_EN: Record<string, string> = new Proxy(FIXED, {
  get(target, prop: string) {
    if (prop in target) return target[prop];
    const house = prop.match(/^house_(\d+)$/);
    if (house) return `in house ${house[1]}`;
    return partileLabel(prop) ?? undefined;
  },
  has(target, prop: string) {
    return prop in target || /^house_\d+$/.test(prop) || partileLabel(prop) !== null;
  },
});
