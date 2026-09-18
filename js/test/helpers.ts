/** テスト用の小道具（テストファイル間で共有する。ここにテストは書かない） */
const SIGN: Record<string, number> = {
  Ari: 0, Tau: 1, Gem: 2, Can: 3, Leo: 4, Vir: 5,
  Lib: 6, Sco: 7, Sag: 8, Cap: 9, Aqu: 10, Pis: 11,
};

/** サイン名と度数から黄経を作る */
export const lon = (sign: string, deg: number): number => SIGN[sign] * 30 + deg;

/** "YYYY-MM-DD HH:MM" 同士の差（分） */
export const minutesFrom = (a: string, b: string): number => {
  const parse = (s: string) => {
    const m = s.match(/(\d+)-(\d+)-(\d+) (\d+):(\d+)/)!;
    return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]) / 60000;
  };
  return Math.abs(parse(a) - parse(b));
};
