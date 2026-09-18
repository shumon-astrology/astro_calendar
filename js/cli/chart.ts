/**
 * 出生図の JSON（SCHEMA_chart_v2）を標準出力に書く CLI。
 *
 *   node --experimental-strip-types cli/chart.ts \
 *     --date 1985-07-21 --time 14:30 --tz Asia/Tokyo --lat 35.6895 --lon 139.6917 --pretty
 *
 * --tz は IANA 名（Asia/Tokyo）でも数値のオフセット（9 や -5.5）でもよい。
 * --time-unknown を付けると現地正午で計算し、時刻に依存する項目を null にする。
 */
import { computeChart } from "../src/index.ts";

function parseArgs(argv: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    if (!key.startsWith("--")) continue;
    const next = argv[i + 1];
    out[key.slice(2)] = next && !next.startsWith("--") ? (i++, next) : "true";
  }
  return out;
}

const args = parseArgs(process.argv.slice(2));
const usage = `使い方:
  node --experimental-strip-types cli/chart.ts --date YYYY-MM-DD [--time HH:MM] \\
    --tz <IANA 名 または UTC からの時差> --lat <緯度> --lon <経度> \\
    [--place "Tokyo"] [--house R|W] [--time-unknown] [--generated-at ISO8601] [--pretty]`;

if (!args.date || !args.lat || !args.lon) {
  console.error(usage);
  process.exit(2);
}

const [year, month, day] = args.date.split("-").map(Number);
const timeKnown = args["time-unknown"] !== "true";
const [hour, minute] = (args.time ?? "12:00").split(":").map(Number);

const tz = args.tz ?? "9";
const numericTz = Number(tz);
const isNumericTz = tz.trim() !== "" && Number.isFinite(numericTz);

const chart = computeChart({
  year, month, day,
  hour: timeKnown ? hour : undefined,
  minute: timeKnown ? minute : undefined,
  latitude: Number(args.lat),
  longitude: Number(args.lon),
  tzOffset: isNumericTz ? numericTz : undefined,
  timezoneId: isNumericTz ? undefined : tz,
  place: args.place,
  timeKnown,
  houseSystem: (args.house as "R" | "W") ?? "R",
  generatedAt: args["generated-at"],
});

process.stdout.write(JSON.stringify(chart, null, args.pretty ? 2 : 0) + "\n");
