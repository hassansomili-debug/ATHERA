# ATHERA | أثيرا

**Research Intelligence & Academic Promotion Operating System**
نظام تشغيل الذكاء البحثي وإدارة الإنتاج العلمي والترقية الأكاديمية.

المرجع الوظيفي: [`athera_claude_v1.2/ATHERA_PRD_SRS_v1.2_CLAUDE.md`](athera_claude_v1.2/ATHERA_PRD_SRS_v1.2_CLAUDE.md) (v1.2) — هو مصدر الحقيقة، والكود يتبعه لا العكس.

> **الحالة: §51 — الذكاء الاستباقي.** السبرنتات التسعة في §42 مكتملة، ومعها القسم الجديد في v1.2 والمصنَّف Must Have: رصد اتجاهات يميّز الإشارة عن الضجيج بأربعة شروط، ودرجتان منفصلتان بنيويًا (قوة الاتجاه ≠ قابلية النشر)، وخط أنابيب P0–P14 ينتهي عند Ready for Submission لا عند النشر.

---

## ما الذي بُني فعلًا

| القدرة | أين | المرجع |
|---|---|---|
| عزل المستأجرين بـRLS إجبارية | [`infra/db/migrations/versions/0003_rls_and_immutability.py`](infra/db/migrations/versions/0003_rls_and_immutability.py) | ADR-0002 |
| سجل تدقيق append-only بسلسلة تجزئة | [`apps/api/athera_api/services/audit.py`](apps/api/athera_api/services/audit.py) | §37، ADR-0004 |
| Provenance بالحقول التسعة الإلزامية | [`apps/api/athera_api/models/audit.py`](apps/api/athera_api/models/audit.py) | §29.2 |
| قاعدة §7.4 مفروضة بقيد قاعدة بيانات | ترحيل `0002` | §7.4 |
| RBAC بتسعة أدوار + منح على مستوى الكائن | [`apps/api/athera_api/services/rbac.py`](apps/api/athera_api/services/rbac.py) | §28 |
| Model Provider Gateway مستقل عن المزود | [`apps/api/athera_api/providers/`](apps/api/athera_api/providers/) | §32، ADR-0003 |
| بوابة اعتماد بشري دائمة في Temporal | [`services/worker/athera_worker/workflows.py`](services/worker/athera_worker/workflows.py) | §9 |
| واجهة عربية/إنجليزية بلا لغة ثانوية | [`apps/web/`](apps/web/) | §26.4، §38.4 |
| تفكيك المستندات بمواضع قابلة للاستشهاد | [`services/parsing.py`](apps/api/athera_api/services/parsing.py) | §33.1، §10.2 |
| حاجز الاختلاق: اقتباس حرفي مؤصَّل | [`services/extraction/base.py`](apps/api/athera_api/services/extraction/base.py) | §4 |
| مستخرِج حتمي يعمل بلا نموذج | [`services/extraction/rules.py`](apps/api/athera_api/services/extraction/rules.py) | §4، §41.2 |
| ترقية الذاكرة عبر مسار واحد فقط | [`services/memory.py`](apps/api/athera_api/services/memory.py) | §7.4، TC-01 |
| شاشة مراجعة الحقائق (بوابة G0) | [`apps/web/src/app/[locale]/facts/`](apps/web/src/app/%5Blocale%5D/facts/) | §10.2، §9 |
| سجل الأجنتات السبعة عشر بقيوده | [`brain/agents.py`](apps/api/athera_api/brain/agents.py) | §8 |
| سجل أدوات بلا أثر جانبي | [`brain/tools.py`](apps/api/athera_api/brain/tools.py) | §7.1 |
| حواجز نزاهة حتمية على المخرجات | [`brain/guardrails.py`](apps/api/athera_api/brain/guardrails.py) | §4، §8، §18.1، §20.4 |
| منسّق العقل البحثي | [`brain/orchestrator.py`](apps/api/athera_api/brain/orchestrator.py) | §7.1، §7.2 |
| عارض الأثر والتكلفة | [`apps/web/src/app/[locale]/traces/`](apps/web/src/app/%5Blocale%5D/traces/) | §38.5 |
| محرك ترقية بلا ثابت جامعي | [`services/promotion/calculator.py`](apps/api/athera_api/services/promotion/calculator.py) | §3، §11 |
| سيناريوهات موسومة كإسقاط | [`services/promotion/scenarios.py`](apps/api/athera_api/services/promotion/scenarios.py) | §11.6 |
| محفظة الأبحاث والخطة المرجعية | [`routers/portfolio.py`](apps/api/athera_api/routers/portfolio.py) | §12 |
| سجلات أدبيات قابلة للتبديل وبلا شبكة في الاختبار | [`services/literature/registry.py`](apps/api/athera_api/services/literature/registry.py) | §14.1، §34.1 |
| حالة الوصول تحكم الاقتطاف | [`models/literature.py`](apps/api/athera_api/models/literature.py) | §14.2، §14.5 |
| سجل الادعاء-الدليل ومنع الاختلاق | [`services/literature/ledger.py`](apps/api/athera_api/services/literature/ledger.py) | §14.4، TC-02 |
| تتبّع السحب والتصحيح بلقطات مؤرَّخة | [`services/literature/verification.py`](apps/api/athera_api/services/literature/verification.py) | §14.3 |
| كشوفات الاتساق التسعة | [`services/golden_thread/checks.py`](apps/api/athera_api/services/golden_thread/checks.py) | §15.2 |
| درجة لا تنفصل عن أسبابها | [`services/golden_thread/score.py`](apps/api/athera_api/services/golden_thread/score.py) | §15.3 |
| متطلبات التصميم تصريحية لكل نوع دراسة | [`services/golden_thread/methodology.py`](apps/api/athera_api/services/golden_thread/methodology.py) | §16 |
| بوابات البروتوكول G2–G5 بلقطة اتساق | [`routers/golden_thread.py`](apps/api/athera_api/routers/golden_thread.py) | §9 |
| مصفوفة تداخل بعتبات من سياسة | [`services/thesis/overlap.py`](apps/api/athera_api/services/thesis/overlap.py) | §23.7، TC-05 |
| درجة جاهزية بمخرجات مصنَّفة | [`services/thesis/readiness.py`](apps/api/athera_api/services/thesis/readiness.py) | §23.6 |
| منقّب فرص حتمي مؤصَّل في الرسالة | [`services/thesis/miner.py`](apps/api/athera_api/services/thesis/miner.py) | §23.4 |
| بوابة الحقوق والتأليف GT1 | [`services/thesis/rights.py`](apps/api/athera_api/services/thesis/rights.py) | §23.9، §24، TC-06 |
| طبقات ثقة المجلات وانتهاء صلاحية الفهرسة | [`services/publishing/journals.py`](apps/api/athera_api/services/publishing/journals.py) | §20، TC-04 |
| بوابة G9: لا ادعاء بلا سند ولا رقم بلا تشغيلة | [`services/publishing/manuscript.py`](apps/api/athera_api/services/publishing/manuscript.py) | §19.2 |
| مجلس محكّمين يقترح رقعًا ولا يعدّل | [`services/publishing/review.py`](apps/api/athera_api/services/publishing/review.py) | §21 |
| RAW غير قابل للتعديل وسلسلة إصدارات | [`services/analysis/lineage.py`](apps/api/athera_api/services/analysis/lineage.py) | §17.2، TC-07 |
| قفل خطة التحليل وإعلان الاستكشاف | [`services/analysis/plan.py`](apps/api/athera_api/services/analysis/plan.py) | §9 G7، §51.8 |
| بيان إعادة الإنتاج وبصمته | [`services/analysis/reproducibility.py`](apps/api/athera_api/services/analysis/reproducibility.py) | §18.1، §31.6 |
| طبقات التفسير الأربع بلا دمج | [`services/analysis/interpretation.py`](apps/api/athera_api/services/analysis/interpretation.py) | §18.3 |
| تمييز الاتجاه عن الضجيج بأربعة شروط | [`services/trends/signals.py`](apps/api/athera_api/services/trends/signals.py) | §51.1 |
| درجة فرصة منفصلة عن قوة الاتجاه | [`services/trends/scoring.py`](apps/api/athera_api/services/trends/scoring.py) | §51.3 |
| خط أنابيب P0–P14 وبوابة التقديم | [`services/trends/pipeline.py`](apps/api/athera_api/services/trends/pipeline.py) | §51.5، §51.6 |
| مصنع المخطوطات وبوابة G9 | [`routers/publishing.py`](apps/api/athera_api/routers/publishing.py) · [`app/[locale]/manuscripts/`](apps/web/src/app/%5Blocale%5D/manuscripts/) | §19، §20، §21 |
| محرك التحليل من الخام إلى التفسير | [`routers/analysis.py`](apps/api/athera_api/routers/analysis.py) · [`app/[locale]/analysis/`](apps/web/src/app/%5Blocale%5D/analysis/) | §17، §18 |
| الذكاء الاستباقي وبوابة P14 | [`routers/trends.py`](apps/api/athera_api/routers/trends.py) · [`app/[locale]/trends/`](apps/web/src/app/%5Blocale%5D/trends/) | §51 |
| مظروف أخطاء موحّد باللغتين حتى في رفض العقد | [`main.py`](apps/api/athera_api/main.py) | §26.4 |
| صندوق القرارات: اعتمادات وتنبيهات وإشعارات | [`routers/inbox.py`](apps/api/athera_api/routers/inbox.py) · [`app/[locale]/approvals/`](apps/web/src/app/%5Blocale%5D/approvals/) | §9، §25 |
| فريق المشروع وأدوار CRediT وسجل القرارات | [`routers/team.py`](apps/api/athera_api/routers/team.py) · [`app/[locale]/team/`](apps/web/src/app/%5Blocale%5D/team/) | §12، §24 |
| سجل التدقيق للقراءة مع تحقق السلسلة | [`app/[locale]/audit/`](apps/web/src/app/%5Blocale%5D/audit/) | §37 |
| إفصاح وضع التشغيل بلا كشف مفاتيح | [`routers/settings.py`](apps/api/athera_api/routers/settings.py) · [`app/[locale]/settings/`](apps/web/src/app/%5Blocale%5D/settings/) | §26.4، §36.2 |
| قاموس البيانات ووسم PII | [`routers/analysis.py`](apps/api/athera_api/routers/analysis.py) | §17.4 |
| تصدير إلى الأدوات بحدوده المعلنة | [`routers/analysis.py`](apps/api/athera_api/routers/analysis.py) | §18.5 |
| النشرة الاستخباراتية وفحص الجدة التنافسية | [`services/trends/brief.py`](apps/api/athera_api/services/trends/brief.py) · [`app/[locale]/briefs/`](apps/web/src/app/%5Blocale%5D/briefs/) | §51.9، §51.10 |
| رصد مجدول في Temporal لا حلقة داخلية | [`athera_worker/schedules.py`](services/worker/athera_worker/schedules.py) | §51.11 |
| محوّل Anthropic خلف البوابة | [`providers/anthropic_adapter.py`](apps/api/athera_api/providers/anthropic_adapter.py) | §32، ADR-0003 |

## ثنائية اللغة — ليست ترجمة لاحقة

- **الواجهة:** المسار يحمل اللغة (`/ar/...` و`/en/...`)، والاتجاه يُحسم على `<html dir>` لا بـCSS مرآة، والتبديل يحفظ الموضع في الصفحة.
- **الـAPI:** كل خطأ يحمل `code` آليًا + رسالة حسب `Accept-Language` + **النصين معًا** في `messages`، فيعرض أي عميل اللغة التي يريدها بلا رحلة إضافية.
- **البيانات:** كل كائن يُعرض للمستخدم يحمل `name_ar` و`name_en` (المستأجرون، الأدوار، التنبيهات، الإشعارات).
- **الاختبار:** `test_at_s0_11_bilingual.py` يفشل عند نقص ترجمة واحدة، أو عند نص إنجليزي في خانة عربية.

## التشغيل

**المتطلبات:** Docker · Node 22+ · Python 3.12+

```bash
cp .env.example .env      # املأ JWT_SECRET؛ لا تضع أسرارًا حقيقية في المستودع
make dev                  # postgres + minio + redis + temporal + api + worker + web
make migrate              # RLS + سجل append-only + بذر الأدوار
make test                 # اختبارات القبول AT-S0-*
```

| الخدمة | العنوان |
|---|---|
| الواجهة | http://localhost:3000 → تعيد التوجيه إلى `/ar` |
| الـAPI | http://localhost:8000/docs |
| Temporal UI | http://localhost:8233 |
| MinIO | http://localhost:9001 |

### تجهيز البيئة على macOS

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install --cask docker
brew install node@22 python@3.12
```

## اختبارات القبول

ثلاثة عشر اختبارًا، كل منها يفشل السبرنت صراحةً — التفاصيل في [خطة Sprint 0 §5](docs/SPRINT0_ARCHITECTURE_PLAN.md).

```bash
make test-offline      # اختبارات لا تحتاج قاعدة بيانات — تعمل اليوم
make test-api          # كل الاختبارات (تحتاج PostgreSQL)
make test-arch         # حدود المزود (§38.6.8)
make verify-constraints # يحاول كل ممنوع ويفشل إن نجح أيٌّ منها
make verify-audit      # سلامة سلسلة التدقيق
```

### مستويا التحقق

| المستوى | ما يغطيه | الحالة |
|---|---|---|
| **منطق خالص** | التفكيك، الحواجز، محرك الترقية، الخيط الذهبي، التداخل، المجلات، التحليل، الاتجاهات | **مُشغَّل** |
| **قيود قاعدة البيانات** | العزل، مناعة التدقيق، §7.4، §14.5، GT1، §21، §31.6، §51 | **مُشغَّل: 14 ترحيلًا صعودًا ونزولًا، و12 فعلًا ممنوعًا مُنعت كلها** |
| **الـAPI من طرف إلى طرف** | رفض G9، رفض التحليل غير المجمَّد، رفض التقديم قبل الجاهزية — عبر HTTP برمز موقّع وRLS مفعّلة | **مُشغَّل** |

**الحصيلة: 437 اختبارًا مُجمَّعًا — 436 ناجحًا، 1 متخطى، 0 فاشل** (مُشغَّلة في CI على PostgreSQL بـpgvector) — و111 مسار API، و19 شاشة تجتاز `tsc` و`next build`.

`scripts/verify_db_constraints.py` يحاول **اثنتي عشرة عملية ممنوعة** ويفشل إن نجحت أيٌّ منها.

لا يلزم Docker للتحقق: [`docs/runbooks/local-postgres-without-docker.md`](docs/runbooks/local-postgres-without-docker.md) يشرح تشغيل PostgreSQL 16 وpgvector عبر pip في مجلد المستخدم، بلا صلاحيات إدارية.

## الوثائق

- [خطة Sprint 0 المعمارية](docs/SPRINT0_ARCHITECTURE_PLAN.md) · [خطة Sprint 1](docs/SPRINT1_PLAN.md) · [خطة Sprint 2](docs/SPRINT2_PLAN.md) · [خطة Sprint 3](docs/SPRINT3_PLAN.md) · [خطة Sprint 4](docs/SPRINT4_PLAN.md) · [خطة Sprint 5](docs/SPRINT5_PLAN.md) · [خطة Sprint 6](docs/SPRINT6_PLAN.md) · [خطة Sprint 7](docs/SPRINT7_PLAN.md) · [خطة Sprint 8](docs/SPRINT8_PLAN.md) · [خطة §51](docs/SPRINT9_TREND_INTELLIGENCE_PLAN.md) · [خطة Sprint 10](docs/SPRINT10_COMPLETION_PLAN.md)
- [ADR-0001 المكدس المعتمد](docs/adr/ADR-0001-approved-stack.md) · [ADR-0002 العزل](docs/adr/ADR-0002-multi-tenancy-isolation.md) · [ADR-0003 بوابة المزود](docs/adr/ADR-0003-model-provider-gateway.md) · [ADR-0004 التدقيق](docs/adr/ADR-0004-audit-provenance.md)
- [نموذج التهديد](docs/threat-model.md) · [تصنيف البيانات](docs/data-classification.md) · [تمرين الاستعادة](docs/runbooks/backup-restore.md)

## ما لا يفعله هذا الكود عمدًا

لا يستدعي نموذجًا في الإنتاج (`MODEL_PROVIDER=null`) · لا يحوّل مخرجات نموذج إلى ذاكرة موثقة · لا يقبل حقيقة باقتباس غير موجود في مصدرها · لا يعتمد حقيقة بلا قرار إنسان · لا يعرض مخرَجًا خالف حاجز نزاهة · لا يملك أداة تعدّل بيانات خامًا أو تبتّ في اعتماد · لا يحتسب قاعدة ترقية لم يعتمدها إنسان · لا يعرض نسبة جاهزية تخفي شرطًا حاجبًا · لا يخلط الإسقاط بالإنجاز · لا يولّد مرجعًا لادعاء بلا دليل · لا يقتطف نصًا من مصدر لم يُتَح نصه · لا يستشهد بمصدر مسحوب بلا إقرار وسياق · لا يفتح بوابة بروتوكول بعيب اتساق حاجب · لا يعيد درجة اتساق مجردة من أسبابها · لا يتقدم بفرصة نشر بلا اعتماد الحقوق والتأليف · لا يسند تأليفًا لغير إنسان أو جهة · لا يحوّل فرصتين متداخلتين بلا حسم بشري · لا يقدّر احتمال قبول ولا يملك حقلًا له · لا يعتمد مجلة بفهرسة لم يُعَد التحقق منها · لا يعدّل نسخة مخطوطة معتمدة بمراجعة آلية · لا يعدّل بيانات خامًا · لا يحلّل بيانات غير مجمَّدة · لا ينتج نتيجة بلا تشغيلة · لا يدمج التفسير الإحصائي بالنظري بالإداري · لا يحتسب مخرَج نموذج دليلًا على اتجاه · لا يخلط قوة الاتجاه بقابلية النشر · لا يقدّم ورقة خارجيًا بلا فعل بشري أو تفويض قابل للسحب · لا يسمح لواجهة المتصفح بالوصول إلى مزود · لا يغلق بوابة اعتماد بمهلة زمنية · لا يعدّل سجل تدقيق.
