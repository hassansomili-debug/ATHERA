import { expect, test } from "@playwright/test";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

/**
 * سياسةُ المتصفّح = ما يُفتِّحه الخادم | The policy must equal the server's.
 *
 * **وقائمةٌ مكتوبةٌ بيدٍ تتخلّف عن الخادم بصمت.** لو فُتِّح مسارٌ جديدٌ في
 * الـAPI ونُسي هنا، لخرجت طلباتُه بلا مفتاح ولانتفت الحمايةُ دون أن يحمرّ
 * فحصٌ واحد. فتُشتقّ قائمةُ الخادم من مصدرِه في كلِّ تشغيلة، ويُطلب
 * التطابقُ في الاتجاهين.
 *
 * والمسارُ المُفتَّح يُعرف بعلامةٍ في جسمِ معالِجه — أو في جسمِ الدالّة
 * التي يُفوّض إليها (`*_body`)، فشطرُ الجسم لا يُسقط مسارًا من الحساب.
 */

const API = join(process.cwd(), "..", "api", "athera_api", "routers");
const WEB = join(process.cwd(), "src", "lib", "idempotency.ts");

const MARKERS = [
  "idempotency.begin", "begin_leased_in", "is_keyed(",
  "fingerprint_extra", "finalize_extra",
];
const MUTATING = ["post", "put", "patch", "delete"];

interface Route { method: string; path: string; source: string }

/** كلُّ `async def NAME` في الملفّ مع جسمه — الجسمُ إلى الـ`def` التالية. */
function functionBlocks(src: string): Map<string, string> {
  const blocks = new Map<string, string>();
  const re = /^(?:async\s+)?def\s+(\w+)\s*\(/gm;
  const starts: Array<[string, number]> = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) starts.push([m[1], m.index]);
  starts.forEach(([name, at], i) => {
    const end = i + 1 < starts.length ? starts[i + 1][1] : src.length;
    blocks.set(name, src.slice(at, end));
  });
  return blocks;
}

function keyed(name: string, blocks: Map<string, string>, depth = 0): boolean {
  if (depth > 3) return false;
  const body = blocks.get(name);
  if (!body) return false;
  if (MARKERS.some((mark) => body.includes(mark))) return true;
  for (const other of blocks.keys()) {
    if (other !== name && new RegExp(`\\b${other}\\s*\\(`).test(body)
        && keyed(other, blocks, depth + 1)) return true;
  }
  return false;
}

function backendKeyedRoutes(): Route[] {
  const found: Route[] = [];
  for (const file of readdirSync(API).filter((f) => f.endsWith(".py"))) {
    const src = readFileSync(join(API, file), "utf-8");
    const prefix = /APIRouter\([^)]*prefix\s*=\s*"([^"]*)"/s.exec(src)?.[1] ?? "";
    const blocks = functionBlocks(src);
    const deco = new RegExp(
      `@router\\.(${MUTATING.join("|")})\\(\\s*"([^"]*)"[\\s\\S]*?\\n(?:async\\s+)?def\\s+(\\w+)\\s*\\(`,
      "g");
    let m: RegExpExecArray | null;
    while ((m = deco.exec(src)) !== null) {
      const [, method, sub, handler] = m;
      if (keyed(handler, blocks)) {
        found.push({ method: method.toUpperCase(), path: prefix + sub,
                     source: `${file}:${handler}` });
      }
    }
  }
  return found;
}

/** المسارُ الصوريُّ: `{param}` يصير جزءًا حقيقيًّا يُختبَر به النمط. */
const concrete = (path: string) =>
  path.replace(/\{[^}]+\}/g, "b7f0c1d2-0000-4000-8000-000000000000");

function webPatterns(): RegExp[] {
  const src = readFileSync(WEB, "utf-8");
  const block = /const PROTECTED_ROUTES[^=]*=\s*\[([\s\S]*?)\n\];/.exec(src);
  expect(block, "PROTECTED_ROUTES لم تُقرأ من المصدر").not.toBeNull();
  const literals = block![1].match(/\/\^[^,\n]*?\$\//g) ?? [];
  return literals.map((lit) => new RegExp(lit.slice(1, -1)));
}

test.describe("Stage 6 — the browser policy mirrors the server", () => {
  test("every backend route that honours a key is protected in the browser",
    () => {
      const routes = backendKeyedRoutes();
      // حارسُ الحارس: مشتقٌّ فارغٌ يجعل الفحصَ يمرّ بلا معنى.
      expect(routes.length, "اشتقاقُ مسارات الخادم أنتج لا شيء")
        .toBeGreaterThanOrEqual(20);
      const patterns = webPatterns();
      const unprotected = routes.filter(
        (r) => !patterns.some((p) => p.test(concrete(r.path))));
      expect(unprotected.map((r) => `${r.method} ${r.path} (${r.source})`))
        .toEqual([]);
    });

  test("no browser pattern claims a route the server does not key", () => {
    const routes = backendKeyedRoutes().map((r) => concrete(r.path));
    const patterns = webPatterns();
    const idle = patterns.filter((p) => !routes.some((r) => p.test(r)));
    expect(idle.map(String),
      "نمطٌ يَعِد بحمايةٍ لا يقابلها تفتيحٌ في الخادم").toEqual([]);
  });

  test("the derivation is honest: removing the marker unprotects its route",
    () => {
      // لدغةُ الاشتقاق: دالّةٌ بلا علامةٍ لا تُعدّ مُفتَّحة، ولو نُوديت.
      const blocks = new Map<string, string>([
        ["handler", "async def handler(request):\n    return await handler_body(request)\n"],
        ["handler_body", "async def handler_body(request):\n    return 1\n"],
      ]);
      expect(keyed("handler", blocks)).toBe(false);
      blocks.set("handler_body",
        "async def handler_body(request):\n    guard = await idempotency.begin(request)\n");
      expect(keyed("handler", blocks)).toBe(true);
    });
});
