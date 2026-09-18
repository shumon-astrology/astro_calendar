/**
 * IANA タイムゾーンの解決（要件書 II-3・Phase 3 手順 4）。
 * `Intl.DateTimeFormat` が持つ tzdata から「壁時計 → UT」を反復で解く。
 * 外部通信はしない。ICU が歴史規則を持たない環境では呼び出し側が数値のオフセットに
 * フォールバックし、`timezone_id` を null にする。
 */

const MS_PER_HOUR = 3600000;

/** 指定した瞬間（UTC ミリ秒）における、そのゾーンの UTC からのオフセット（時間） */
export function offsetAt(utcMs: number, timeZone: string): number {
  const dtf = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour12: false,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
  const parts: Record<string, number> = {};
  for (const p of dtf.formatToParts(new Date(utcMs))) {
    if (p.type !== "literal") parts[p.type] = Number(p.value);
  }
  const asUtc = Date.UTC(
    parts.year, parts.month - 1, parts.day,
    parts.hour % 24, parts.minute, parts.second,
  );
  return (asUtc - Math.floor(utcMs / 1000) * 1000) / MS_PER_HOUR;
}

export interface ResolvedTimezone {
  /** UTC からの時差（時間）。壁時計をこの値で UT に直す */
  tzOffset: number;
  /** その日付で夏時間が効いているか（標準時との比較） */
  dstApplied: boolean;
  /** 解決に使った IANA 名。解決できなければ null */
  timezoneId: string | null;
}

/**
 * 現地の壁時計と IANA 名から、その瞬間のオフセットを求める。
 * 夏時間の切り替えで存在しない／重複する時刻は、前方（先に来る方）のオフセットを採る。
 */
export function resolveTimezone(
  year: number, month: number, day: number, hour: number, minute: number, timeZone: string,
): ResolvedTimezone {
  const wall = Date.UTC(year, month - 1, day, hour, minute);
  let offset = offsetAt(wall, timeZone);
  for (let i = 0; i < 3; i++) {
    const next = offsetAt(wall - offset * MS_PER_HOUR, timeZone);
    if (next === offset) break;
    offset = next;
  }
  const utcMs = wall - offset * MS_PER_HOUR;
  // その年の 1 月と 7 月のオフセットのうち小さい方を標準時とみなす
  const january = offsetAt(Date.UTC(year, 0, 15), timeZone);
  const july = offsetAt(Date.UTC(year, 6, 15), timeZone);
  const standard = Math.min(january, july);
  return {
    tzOffset: offset,
    dstApplied: offset !== standard,
    timezoneId: timeZone,
  };
}

/** IANA 名がこの環境で使えるか */
export function isKnownTimezone(timeZone: string): boolean {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone });
    return true;
  } catch {
    return false;
  }
}
