/**
 * 出生図の JSON を標準出力に書く CLI。
 *
 *   node --experimental-strip-types cli/chart.ts \
 *     --date 1985-07-21 --time 14:30 --tz 9 --lat 35.6895 --lon 139.6917
 *
 * Phase 2 では v1 相当の出力（--tz は数値のオフセット）。
 * IANA タイムゾーン（--timezone Asia/Tokyo）と --time-unknown は Phase 3。
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
  node --experimental-strip-types cli/chart.ts --date YYYY-MM-DD --time HH:MM \\
    --tz <UTCからの時差> --lat <緯度> --lon <経度> [--house R|W] [--pretty]`;

if (!args.date || !args.lat || !args.lon) {
  console.error(usage);
  process.exit(2);
}

const [year, month, day] = args.date.split("-").map(Number);
const [hour, minute] = (args.time ?? "12:00").split(":").map(Number);

const chart = computeChart({
  year, month, day, hour, minute,
  latitude: Number(args.lat),
  longitude: Number(args.lon),
  tzOffset: args.tz === undefined ? 9 : Number(args.tz),
  houseSystem: (args.house as "R" | "W") ?? "R",
});

process.stdout.write(JSON.stringify(chart, null, args.pretty ? 2 : 0) + "\n");
