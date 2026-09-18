/**
 * 曜日主星（Lord of the Day）と時刻主星（Lord of the Hour）。
 * natal_classical.planetary_hour を写す（commit e88df93 の現地時刻対応を含む）。
 *
 * 日出没の定義は Python に合わせる：視位置（大気差あり、1013.25 hPa・0 ℃）・
 * 太陽の円盤中心・海抜 0 m。JS は SearchAltitude に較正済みの高度 −0.610° を渡す。
 */
import { sunRiseSet } from "./ephemeris.ts";
import { HOUR_ORDER, WEEKDAY_RULERS } from "./tables.ts";
import { formatLocalDateTime, weekdayOfLocal } from "./time.ts";

export interface PlanetaryHour {
  day_ruler: string;
  hour_ruler: string;
  hour_index: number;
  is_daytime: boolean;
  sunrise: string;
  sunset: string;
}

export function planetaryHour(
  jd: number, lat: number, geoLon: number, tzOffset: number,
): PlanetaryHour | null {
  const sunrisePrev = sunRiseSet(jd - 1.0, lat, geoLon, true);
  const sunriseNext = sunRiseSet(jd, lat, geoLon, true);
  if (sunrisePrev === null || sunriseNext === null) return null;

  let sunrise: number;
  let nextSunrise: number | null;
  if (sunriseNext <= jd) {
    sunrise = sunriseNext;
    nextSunrise = sunRiseSet(sunrise + 0.5, lat, geoLon, true);
  } else {
    sunrise = sunrisePrev;
    nextSunrise = sunriseNext;
  }
  if (nextSunrise === null) return null;

  const sunset = sunRiseSet(sunrise, lat, geoLon, false);
  if (sunset === null || sunset <= sunrise) return null;

  let isDaytime: boolean;
  let index: number;
  if (jd < sunset) {
    isDaytime = true;
    index = Math.floor((jd - sunrise) / ((sunset - sunrise) / 12));
  } else {
    isDaytime = false;
    index = 12 + Math.floor((jd - sunset) / ((nextSunrise - sunset) / 12));
  }
  index = Math.max(0, Math.min(23, index));

  const dayRuler = WEEKDAY_RULERS[weekdayOfLocal(sunrise, tzOffset)];
  const hourRuler = HOUR_ORDER[(HOUR_ORDER.indexOf(dayRuler) + index) % 7];

  return {
    day_ruler: dayRuler,
    hour_ruler: hourRuler,
    hour_index: index + 1,
    is_daytime: isDaytime,
    sunrise: formatLocalDateTime(sunrise, tzOffset),
    sunset: formatLocalDateTime(sunset, tzOffset),
  };
}
