import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

/**
 * حارسُ التغطية | the adoption guard (RC-T1-H2 · Stage 6).
 *
 * **وحارسٌ يفحص الأسماءَ وحدَها لا يحرس شيئًا.** فلهذا يقرأ هذا الملفُّ
 * المصدرَ نفسَه: سياسةَ المسارات، وكلَّ نداءٍ يطفر، وكلَّ رفعٍ متعدّدِ
 * الأجزاء — ويسقط إن التفّ أحدٌ على المنفذ المركزيّ.
 */

const SRC = join(__dirname, "..", "src");

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return walk(full);
    return /\.tsx?$/.test(entry) ? [full] : [];
  });
}

const files = walk(SRC);
const read = (f: string) => readFileSync(f, "utf8");

/** يقصّ نصَّ نداءٍ بأقواسٍ متوازنة، فلا يختلط بنداءٍ مجاور. */
function callAt(src: string, open: number): string {
  let depth = 0;
  for (let i = open; i < src.length; i += 1) {
    const c = src[i];
    if (c === "(" || c === "[" || c === "{") depth += 1;
    else if (c === ")" || c === "]" || c === "}") {
      depth -= 1;
      if (depth === 0) return src.slice(open + 1, i);
    } else if (c === '"' || c === "'" || c === "`") {
      const quote = c;
      i += 1;
      while (i < src.length && src[i] !== quote) {
        if (src[i] === "\\") i += 1;
        i += 1;
      }
    }
  }
  return src.slice(open + 1);
}

interface Callsite {
  file: string;
  line: number;
  fn: string;
  method: string;
  path: string;
  body: string;
}

function callsites(): Callsite[] {
  const out: Callsite[] = [];
  for (const file of files) {
    if (file.endsWith("lib/api.ts") || file.endsWith("lib/upload.ts")) continue;
    const src = read(file);
    const re = /\b(apiFetch|uploadWithProgress)\b(?:<[^>]*>)?\s*\(/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(src))) {
      const inner = callAt(src, m.index + m[0].length - 1);
      const method = /method:\s*["']([A-Za-z]+)["']/.exec(inner)?.[1]?.toUpperCase()
        ?? (m[1] === "uploadWithProgress" ? "POST" : "GET");
      const path = /^\s*(`[^`]*`|"[^"]*"|'[^']*')/.exec(inner)?.[1] ?? "";
      out.push({
        file: file.replace(SRC, "src"),
        line: src.slice(0, m.index).split("\n").length,
        fn: m[1], method, path, body: inner,
      });
    }
  }
  return out;
}

/** أنماطُ المسارات المحميّة — تُقرأ من وحدة السياسة نفسِها، لا تُنسخ. */
function protectedPatterns(): RegExp[] {
  const src = read(join(SRC, "lib", "idempotency.ts"));
  const block = /const PROTECTED_ROUTES[^=]*=\s*\[([\s\S]*?)\n\];/.exec(src);
  expect(block, "لم يُعثر على سياسة المسارات المحميّة").not.toBeNull();
  return [...block![1].matchAll(/\/\^([^\n]+?)\$\/,/g)].map(
    (m) => new RegExp("^" + m[1] + "$"));
}

/** النصُّ الحرفيُّ للمسار إن أمكن — وإلّا شكلٌ تقريبيٌّ للقوالب. */
function literalPath(raw: string): string | null {
  const text = raw.slice(1, -1);
  if (!raw.startsWith("`")) return text;
  return text.replace(/\$\{[^}]*\}/g, "x");
}

test.describe("Stage 6 — web idempotency adoption guard", () => {
  test("the protected-route policy matches the backend families", () => {
    const patterns = protectedPatterns();
    // **والعددُ الدقيقُ لا يُكتب هنا** — كان `20` ثمّ صار الهيكلُ مُمفتَحًا في
    // المرحلة ٨. فالمساواةُ يملكها اشتقاقُ الخادم في `backend-keyed-routes`
    // (في الاتجاهين)، وهذا أرضيّةٌ لا تنخفض دون خطِّ المرحلة ٦ وحدَها.
    expect(patterns.length).toBeGreaterThanOrEqual(20);
    const must = [
      "/api/v1/workspace/projects", "/api/v1/portfolio/projects",
      "/api/v1/analysis/runs", "/api/v1/manuscripts",
      "/api/v1/sources/search", "/api/v1/references/search",
      "/api/v1/sources/import", "/api/v1/sources/abc/verify",
      "/api/v1/files", "/api/v1/files/upload", "/api/v1/files/abc/complete",
      "/api/v1/projects/abc/publication-opportunities/def/outline",
      "/api/v1/ai/ask", "/api/v1/brain/ask",
      "/api/v1/manuscripts/m1/sections/method/draft",
      "/api/v1/projects/p1/publication-opportunities",
      "/api/v1/theses/t1/opportunities/o1/thread", "/api/v1/profile/import",
      "/api/v1/theses/upload", "/api/v1/theses/process-file/f1",
      "/api/v1/theses/t1/reprocess",
    ];
    for (const path of must) {
      expect(patterns.some((r) => r.test(path)), `غير محميّ: ${path}`).toBe(true);
    }
  });

  test("no auth route is inside the protected policy", () => {
    const patterns = protectedPatterns();
    for (const path of [
      "/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh",
      "/api/v1/auth/logout", "/api/v1/auth/forgot-password",
      "/api/v1/auth/reset-password", "/api/v1/auth/change-password",
    ]) {
      expect(patterns.some((r) => r.test(path)), `مسارُ رموزٍ محميّ: ${path}`).toBe(false);
    }
  });

  test("every protected callsite goes through the central client", () => {
    const patterns = protectedPatterns();
    const offenders: string[] = [];
    for (const c of callsites()) {
      const path = literalPath(c.path);
      if (!path) continue;
      const isProtected = patterns.some((r) => r.test(path));
      if (!isProtected) continue;
      // المنفذُ المركزيُّ هو `apiFetch`/`uploadWithProgress` — ولا `fetch` خامّ.
      if (!["apiFetch", "uploadWithProgress"].includes(c.fn)) {
        offenders.push(`${c.file}:${c.line} — ${path} خارج المنفذ المركزيّ`);
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  test("a protected multipart callsite always declares an intent identity", () => {
    const patterns = protectedPatterns();
    const offenders: string[] = [];
    for (const c of callsites()) {
      const path = literalPath(c.path);
      if (!path || !patterns.some((r) => r.test(path))) continue;
      const multipart = /FormData|body:\s*(form|body)\b/.test(c.body)
        || c.fn === "uploadWithProgress";
      if (multipart && !/intentId\s*:/.test(c.body)) {
        offenders.push(
          `${c.file}:${c.line} — ${path} رفعٌ محميٌّ بلا هُويّةِ نيّة`);
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  test("no component mints its own idempotency key", () => {
    const offenders: string[] = [];
    for (const file of files) {
      if (file.endsWith("lib/idempotency.ts")) continue;
      const src = read(file);
      if (/["']Idempotency-Key["']/.test(src) && !file.endsWith("lib/upload.ts")
          && !file.endsWith("lib/api.ts")) {
        offenders.push(`${file.replace(SRC, "src")} — يضع الترويسةَ بنفسه`);
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  test("mutation keys never touch localStorage", () => {
    const src = read(join(SRC, "lib", "idempotency.ts"));
    // **الاستعمالُ لا الذِّكر**: الشرحُ يذكر `localStorage` ليقول لمَ رُفض،
    // والمقصودُ ألّا يُقرأ منه ولا يُكتب فيه.
    const stripped = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
    expect(/localStorage\s*[.?[]/.test(stripped)).toBe(false);
    expect(/sessionStorage\s*[.?[]/.test(stripped)).toBe(true);
  });
});
