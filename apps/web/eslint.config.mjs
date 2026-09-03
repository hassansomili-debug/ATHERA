/**
 * إعداد ESLint المسطّح | Flat config (ESLint 9).
 *
 * لماذا وُجد هذا الملف: كان `npm run lint` ينفّذ `next lint`، وقد **أُزيل
 * هذا الأمر في Next.js 16**. ومع `"next": "^16.0.0"` بلا سقف و`npm install`
 * في CI، جُلب 16.3.3 فاختفى الأمر وسقطت خطوة الفحص — ومعها خطوة البناء
 * التي تليها، بلا تغيير سطر واحد في الواجهة.
 *
 * البديل الرسمي: تشغيل ESLint مباشرةً على إعداد مسطّح يستورد ما كان
 * `next/core-web-vitals` و`next/typescript` يقدّمانه.
 */
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

const config = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "**/*.json",
      // اختبارات المتصفح تُثبَّت حزمتها في مهمّتها وحدها.
      "tests/**",
    ],
  },
  ...nextCoreWebVitals,
  ...nextTypeScript,
];

export default config;
