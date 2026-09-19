import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  intentFingerprint, isProtectedRequest, newIdempotencyKey, shouldRetainIntent,
} from "../src/lib/idempotency";

/**
 * جدولُ السياسة، بلا متصفّح | Stage 6 — the policy table itself.
 *
 * **وفرعٌ لا يُبلَغ من الرحلةِ يبقى بلا لدغة.** رحلةُ المتصفّح تثبت المسلكَ
 * الحيّ، ولا تصل إلى كلِّ فرعٍ في الدالّة: مسلكُ الرفع لا يستشير
 * `shouldRetainIntent` عند انقطاعِ النقل أصلًا (لا يحسم النيّة البتّة)،
 * و`apiFetch` يحسمها عند النجاح بلا سؤالٍ. فالفرعان دفاعيّان — **ويُقالان
 * كذلك** — ويُفحصان هنا مباشرةً، فلا يُعدَّل أحدُهما يومًا بلا أن يحمرّ شيء.
 */

const KEY = /^[A-Za-z0-9_-]{16,128}$/;

test.describe("Stage 6 — the policy answers exactly as specified", () => {
  test("only mutating, non-auth, listed routes are protected", () => {
    expect(isProtectedRequest("POST", "/api/v1/ai/ask")).toBe(true);
    expect(isProtectedRequest("post", "/api/v1/ai/ask")).toBe(true);
    expect(isProtectedRequest("POST", "/api/v1/theses/upload")).toBe(true);

    // **القراءةُ ليست طفرة** — ولو كانت على مسارٍ محميّ.
    for (const verb of ["GET", "HEAD", "OPTIONS"]) {
      expect(isProtectedRequest(verb, "/api/v1/ai/ask"), verb).toBe(false);
    }
    // **ومسالكُ الجلسةِ مستثناةٌ نصًّا** — ولا يُبصَم فيها شيء.
    for (const path of ["/api/v1/auth/login", "/api/v1/auth/register",
                        "/api/v1/auth/refresh", "/api/v1/auth/logout",
                        "/api/v1/auth/change-password"]) {
      expect(isProtectedRequest("POST", path), path).toBe(false);
    }
    expect(isProtectedRequest("POST", "/api/v1/workspace/projects/x/archive"))
      .toBe(false);
    // والاستعلامُ لا يُغيّر الحكم.
    expect(isProtectedRequest("POST", "/api/v1/ai/ask?x=1")).toBe(true);
  });

  test("a computed path is judged after it resolves", () => {
    // `/theses/${id}/${action}` في المكتبة — و«إعادةُ القراءة» منها محميّة.
    const id = "b7f0c1d2-0000-4000-8000-000000000000";
    expect(isProtectedRequest("POST", `/api/v1/theses/${id}/reprocess`)).toBe(true);
    expect(isProtectedRequest("POST", `/api/v1/theses/${id}/restore`)).toBe(false);
    expect(isProtectedRequest("POST", `/api/v1/theses/${id}/mine-opportunities`))
      .toBe(false);
  });

  test("minted keys are well-formed and never repeat", () => {
    const keys = new Set<string>();
    for (let i = 0; i < 500; i += 1) {
      const key = newIdempotencyKey();
      expect(key).toMatch(KEY);
      keys.add(key);
    }
    expect(keys.size, "مفتاحٌ تكرّر في خمسِ مئة سَكَّة").toBe(500);
  });

  test("the fingerprint separates method, path, body and intent", async () => {
    const base = { method: "POST", path: "/api/v1/workspace/projects",
                   body: { title_ar: "أ" } };
    const same = await intentFingerprint(base);
    expect(await intentFingerprint(base)).toBe(same);
    expect(await intentFingerprint({ ...base, method: "PUT" })).not.toBe(same);
    expect(await intentFingerprint({ ...base, path: "/api/v1/manuscripts" }))
      .not.toBe(same);
    expect(await intentFingerprint({ ...base, body: { title_ar: "ب" } }))
      .not.toBe(same);
    // **وترتيبُ المفاتيحِ ليس اختلافَ نيّة.**
    expect(await intentFingerprint({ ...base, body: { title_ar: "أ" } })).toBe(same);

    // وحين تُعلَن الهُويّةُ صراحةً، هي وحدها تفصل — والجسمُ لا يُبصَم.
    const withId = { ...base, body: "__form_data__", intentId: "one" };
    expect(await intentFingerprint(withId))
      .toBe(await intentFingerprint({ ...withId, body: "__other_body__" }));
    expect(await intentFingerprint({ ...withId, intentId: "two" }))
      .not.toBe(await intentFingerprint(withId));
  });

  test("the retention table: what is kept, and what is settled", () => {
    // غموضٌ ⇒ تُحفَظ النيّة.
    expect(shouldRetainIntent(0), "انقطاعُ نقلٍ حُكِم به").toBe(true);
    for (const status of [408, 425, 429, 500, 502, 503, 504]) {
      expect(shouldRetainIntent(status), String(status)).toBe(true);
    }
    for (const code of ["idempotency.in_progress",
                        "idempotency.external_result_unknown"]) {
      expect(shouldRetainIntent(409, code), code).toBe(true);
    }
    // حكمٌ قاطع ⇒ تُحسَم.
    for (const status of [200, 201, 202, 204, 299]) {
      expect(shouldRetainIntent(status), String(status)).toBe(false);
    }
    for (const status of [400, 401, 403, 404, 409, 422]) {
      expect(shouldRetainIntent(status), String(status)).toBe(false);
    }
    expect(shouldRetainIntent(409, "idempotency.key_reused")).toBe(false);
    // ورمزٌ يُبقي النيّةَ لا يُنقذ حالةً قاطعة إن لم يُرسَل.
    expect(shouldRetainIntent(422, "ingestion.unsupported_document")).toBe(false);
  });

  test("the upload transport never settles an intent it cannot judge", () => {
    // **حارسٌ بنيويّ**: `onerror`/`onabort` لا جوابَ لهما، فلا يحسمان.
    const src = readFileSync(join(process.cwd(), "src", "lib", "upload.ts"), "utf-8");
    for (const hook of ["onerror", "onabort"]) {
      const at = src.indexOf(`request.${hook} =`);
      expect(at, `${hook} غير موجود`).toBeGreaterThan(-1);
      const line = src.slice(at, src.indexOf("\n", at));
      expect(line, `${hook} يحسم نيّةً لا جوابَ لها`).not.toContain("resolveIntent");
    }
  });
});
