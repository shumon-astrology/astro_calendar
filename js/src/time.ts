/**
 * 時刻の変換。astro_calendar.datetime_local_to_jd / natal_classical.jd_to_local_datetime を写す。
 * タイムゾーンは Phase 2 では数値のオフセット（tz_offset）だけを受ける。
 * IANA タイムゾーンの解決は Phase 3（birth_data.timezone_id）で足す。
 */

/** グレゴリオ暦の日付 → ユリウス日（UT の 0 時基準、swe.julday と同じ） */
export function julday(year: number, month: number, day: number, hourUt: number): number {
  let y = year;
  let m = month;
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  const a = Math.floor(y / 100);
  const b = 2 - a + Math.floor(a / 4);
  return (
    Math.floor(365.25 * (y + 4716)) +
    Math.floor(30.6001 * (m + 1)) +
    day +
    b -
    1524.5 +
    hourUt / 24
  );
}

/** 現地の壁時計 → ユリウス日（UT）＝ astro_calendar.datetime_local_to_jd */
export function localToJd(
  year: number, month: number, day: number,
  hour: number, minute: number, tzOffset: number,
): number {
  let hourUt = hour + minute / 60 - tzOffset;
  let y = year;
  let m = month;
  let d = day;
  if (hourUt < 0) {
    hourUt += 24;
    ({ y, m, d } = addDays(y, m, d, -1));
  } else if (hourUt >= 24) {
    hourUt -= 24;
    ({ y, m, d } = addDays(y, m, d, 1));
  }
  return julday(y, m, d, hourUt);
}

function addDays(y: number, m: number, d: number, delta: number) {
  const ms = Date.UTC(y, m - 1, d) + delta * 86400000;
  const dt = new Date(ms);
  return { y: dt.getUTCFullYear(), m: dt.getUTCMonth() + 1, d: dt.getUTCDate() };
}

export interface DateParts {
  year: number; month: number; day: number; hour: number; minute: number;
}

/** ユリウス日（UT） → 現地時刻の年月日時分（分は切り捨て。Python と同じ） */
export function jdToLocalParts(jd: number, tzOffset: number): DateParts {
  const ms = (jd - 2440587.5) * 86400000 + tzOffset * 3600000;
  // 丸め誤差で 59.9999 秒が翌分に落ちないよう、ミリ秒の丸めは Python と同じ切り捨てにする
  const dt = new Date(Math.round(ms));
  return {
    year: dt.getUTCFullYear(),
    month: dt.getUTCMonth() + 1,
    day: dt.getUTCDate(),
    hour: dt.getUTCHours(),
    minute: dt.getUTCMinutes(),
  };
}

const pad2 = (n: number) => String(n).padStart(2, "0");

/** "1985-07-21 04:41" 形式＝ astro_calendar.format_date_file2 */
export function formatLocalDateTime(jd: number, tzOffset: number): string {
  const p = jdToLocalParts(jd, tzOffset);
  return `${p.year}-${pad2(p.month)}-${pad2(p.day)} ${pad2(p.hour)}:${pad2(p.minute)}`;
}

/** 曜日（0=月曜 … 6=日曜。Python の datetime.weekday() と同じ） */
export function weekdayOfLocal(jd: number, tzOffset: number): number {
  const ms = (jd - 2440587.5) * 86400000 + tzOffset * 3600000;
  const dt = new Date(Math.round(ms));
  return (dt.getUTCDay() + 6) % 7;
}
