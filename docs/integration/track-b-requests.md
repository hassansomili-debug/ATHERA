# طلباتُ التكامل — المسار B | Track B integration requests

**إدارة المشروع البحثي (Wave1-B).** ما يلي هو كل ما يحتاجه هذا المسار من
ملفّاتٍ لا يملكها، وكل عقدٍ يُتوقَّع أن تستهلكه مساراتٌ أخرى. ولا يُعدَّل
شيءٌ منها هنا — تُكتب وتُترك للمُكامِل.

---

## ١) تركيبُ الموجّه في `main.py` — **أُضيف في هذا الـPR، ويُطلب مراجعتُه**

الملفّ: `apps/api/athera_api/main.py`

> **إفصاح**: القاعدة أن يُطلب هذا التعديل لا أن يُؤخذ، وقد كُتب الطلب أوّلًا
> وتُرك الملفّ كما هو. ثمّ نُقل الفرعُ على قاعدة السبرنت الجديدة (`d1ddecd`)
> وفيها عقدٌ معماريّ جديد:
> `tests/test_at_arch_wave1_contracts.py::test_every_router_module_is_actually_mounted`
> — يُسقط **أيّ** موجّهٍ مكتوبٍ غير مركَّب، ومقياسه `app.openapi()["paths"]`.
>
> فبقاءُ الموجّه بلا تركيب يجعل فرع السبرنت أحمر. والمخرجُ الآخر — إضافةُ
> `project_management` إلى `UNMOUNTED_BY_DESIGN` — كذبٌ على الحارس: هو ليس
> موجّهًا «لا يُركَّب عمدًا»، بل موجّهًا يُراد تركيبه. وهو بالضبط العطب الذي
> كُتب الحارس لأجله.
>
> فأُضيف السطران، **وهما كلّ ما مُسّ في `main.py`**، ويُذكران هنا بنصّهما
> وبموضعهما ليراجعهما المُكامِل ويحسم بقاءهما.

**ما أُضيف** — سطرا استيرادٍ وتركيب، بلا شيءٍ آخر:

```python
from .routers import project_management as project_management_router
```

```python
app.include_router(project_management_router.router)
```

**لماذا**: تركيبُ الموجّهات صريحٌ في هذا المستودع ولا اكتشاف تلقائيّ فيه.

**ما الذي يسقط بدونهما**: كلّ شيء. الموجّه
`apps/api/athera_api/routers/project_management.py` مكتوبٌ ومُختبَر، ولا يبلغه
طلبُ HTTP واحد بدونهما — فلا لوحةَ مشروع، ولا مهامّ، ولا مَعالم، ولا معاينةَ
إتلاف، ولا سلّة. والشاشات الأربع في `apps/web` تُصيَّر وتعرض «تعذّر تحميل هذه
الشاشة» في الإنتاج. وفوق ذلك يسقط العقدُ المعماريّ نفسه فيصير الفرع أحمر.

**النقاط التي يفتحها** (١٦ مسارًا تحت `/api/v1/project-management`):

| الطريقة | المسار |
|---|---|
| GET | `/vocabulary` |
| GET | `/projects/{project_id}/dashboard` |
| GET · PATCH | `/projects/{project_id}/plan` · `/projects/{project_id}/timeline` |
| GET · POST | `/projects/{project_id}/stage` · `/stage/confirm` · `/stage/history` |
| GET · POST · PATCH | `/projects/{project_id}/tasks` · `/tasks/{task_id}` |
| GET | `/projects/{project_id}/task-suggestions` |
| GET · PUT | `/projects/{project_id}/milestones` · `/milestones/{milestone_key}` |
| GET | `/trash` · `/trash/{project_id}/deletion-preview` |
| POST | `/trash/{project_id}/permanent-delete` (يردّ ٤٠٩ عمدًا — انظر ٤) |

**حارسٌ قائم**: `tests/test_at_project_management.py::test_the_router_is_either_mounted_or_its_mount_is_formally_requested`
يمرّ اليوم لأن هذا الطلب مكتوب، ويتحوّل إلى فحصٍ للتركيب نفسه فور إضافته.

---

## ٢) خطوةُ المتصفّح في CI — **مطلوبة**

الملفّ: `.github/workflows/ci.yml`، مهمّة `browser`.

**المطلوب** — خطوةٌ واحدة بعد `Product surface`:

```yaml
      - name: Project management surface (real browser)
        run: cd apps/web && npm run test:project-management
        env:
          NEXT_PUBLIC_API_BASE_URL: https://athera-api.fly.dev
```

والسكربت `test:project-management` مضافٌ بالفعل في `apps/web/package.json`.

**لماذا**: `apps/web/tests/project-management.spec.ts` بلا اعتمادٍ وبلا خادمٍ
خلفي — الجلسة مزروعة والشبكة معترَضة — فيعمل في كل PR كما تعمل
`product-surface`.

**ما الذي يسقط بدونه**: يبقى الفحص في المستودع ولا يُشغَّل، فلا يحرس شيئًا.
وهو الذي يحرس: ألّا تعود نسبةٌ إلى الشاشة، وألّا يعود العنوان المُلفَّق،
وأن تسبق المعاينةُ زرَّ الإتلاف.

---

## ٣) العقدُ المشترك لعرض عنوان المشروع — **تستهلكه المسارات الأخرى**

الملفّان (مكتوبان، ولا يحتاجان تغييرًا من المُكامِل):

- `apps/api/athera_api/services/project_management/titles.py` → `project_title(...)`
- `apps/web/src/lib/projectTitle.ts` → `projectTitle(...)` و`displayTitle(...)`

### العطبُ الذي يعالجه

عُرضت للباحث في قائمة بحوثه عناوينُ من هذا النوع:

```
قبول 2026-09-09T17:12:41.883012+00:00
```

وهذه ليست عنوانًا: هي نصُّ حدثٍ في سجلّ التدقيق ووقتُه لُصقا معًا وعُرضا في
موضع العنوان.

### القاعدة

> **لا يُصنَع عنوانٌ من شيء** — لا من نصِّ تدقيق، ولا من طابعٍ زمني، ولا من
> أول جملةٍ في وصف، ولا من اسم ملفٍّ مرفوع.

فإن لم يكن للبحث عنوانُ عملٍ ذو معنًى:

1. يُعرض **`مشروع بدون عنوان`** (`Untitled project`)،
2. ويُعرض تاريخ الإنشاء **في حقلٍ منفصل** لا مضمومًا إلى العنوان،
3. وتبقى **إعادة التسمية** متاحة (`can_rename`).

### ثلاث حالاتٍ ترفض، ولا رابعة

| السبب | المثال |
|---|---|
| `blank` | `""` · `"   "` |
| `audit_timestamp` | `قبول 2026-09-09T17:12:41…` |
| `no_letters` | `2026-09-09` · `17:12` |

**والتضييق مقصود**: رفضُ عنوانٍ صحيح أسوأ من قبول عنوانٍ رديء. فـ«دراسة 2024
عن التدريب» يُعرض كما كتبه صاحبه.

### كيف تستهلكه وحدةٌ أخرى

**API** — لا تُرجع `working_title_ar` خامًا في أيّ عقد:

```python
from ..services.project_management import project_title
from ..schemas.project_management import ProjectTitleView

title = project_title(row.working_title_ar, created_at=row.created_at)
view = ProjectTitleView(
    display_ar=title.display_ar, display_en=title.display_en,
    is_placeholder=title.is_placeholder, placeholder_reason=title.reason,
    created_at=title.created_at, can_rename=title.can_rename)
```

**الويب** — لا تقرأ الحقل الخام في الشاشة:

```ts
import { displayTitle } from "@/lib/projectTitle";
<strong>{displayTitle(row.title, locale)}</strong>
```

**الشاشات التي ما زالت تقرأ العمود خامًا** (خارج نطاق هذا المسار، وتحتاج
تحويلًا إلى العقد): `portfolio/page.tsx` · `team/page.tsx` ·
`thread/page.tsx` · `references/page.tsx` · `components/ProjectPicker.tsx`.
وقراءةُ العمود خامًا في شاشةٍ واحدة كافيةٌ لعودة العيب بعد أن أُصلح في أربع.

### ثلاثةُ مواضع تُوحَّد عند التكامل — **وهذا هو الطلب**

أفاد المُكامِل أنّ المسار F بنى السلوك نفسه محليًّا لئلّا يتوقّف، وأنّ
موضعًا ثالثًا يستعمل بديلًا مختلفًا. فالمواضع الثلاثة:

| الموضع | البديل اليوم | ما يصير إليه |
|---|---|---|
| `services/project_management/titles.py` (هذا المسار) | `مشروع بدون عنوان` | **المرجع** — يبقى كما هو |
| نسخةُ المسار F المحلّية (الخيط الذهبي) | السلوك نفسه، منسوخًا | تُحذف، ويُستورد المرجع |
| `services/golden_thread/snapshot.py` | `"بحث"` | يُستبدل بالمرجع |

و`"بحث"` ليست خطأً إملائيًّا بل عقدًا ثانيًا: بحثٌ بلا عنوان يُعرض في
الخيط الذهبي «بحث» وفي السلّة «مشروع بدون عنوان» — فيظنّ الباحث أنهما
شيئان، أو يظنّ «بحث» عنوانًا اختاره أحد. **وبديلٌ لا يُعرَف أنه بديل هو
نصفُ العيب الأصلي**: لا `is_placeholder` مع `"بحث"`، فلا تستطيع شاشةٌ أن
تعرض «أعِد التسمية» ولا أن تفصل تاريخ الإنشاء.

**والاستيراد جاهز ولا يحتاج تغييرًا:**

```python
from athera_api.services.project_management import project_title
```

ودالّةٌ خالصة بلا جلسةٍ ولا مستأجر: `project_title(working_title_ar,
created_at=...)` → `ProjectTitle(display_ar, display_en, is_placeholder,
reason, created_at, can_rename)`. ونظيرتها في الويب:

```ts
import { projectTitle, displayTitle } from "@/lib/projectTitle";
```

---

## ٤) قرارُ سياسة الاحتفاظ — **قرارُ مالكٍ، لا قرارُ مسار**

**الحال اليوم**: الإتلاف الدائم من السلّة **موقوف**. والمعاينة تعمل كاملةً
(عشرة أعدادٍ باسمها)، ثمّ يردّ `POST /trash/{id}/permanent-delete` بـ**٤٠٩**
ومعه سببُ الوقف وشرطُ رفعه.

**لماذا وُقف** — سياسةُ الاحتفاظ في هذا المستودع ليست معرَّفةً تعريفًا صالحًا
للتنفيذ. و`docs/data-classification.md` تقول:

| المستوى | الاحتفاظ |
|---|---|
| C2 بحثيّ حسّاس | «مدة المشروع + ٥ سنوات» |
| C3 بيانات بحثية | «حسب Data Management Plan» |
| C4 بيانات مشاركين | «حسب الموافقة الأخلاقية فقط» |

فالأولى تعني أنّ إتلافَ بحثٍ اليوم قد يخالف احتفاظًا واجبًا لخمس سنوات؛
والثانيتان تُحيلان إلى خطّة إدارة بياناتٍ وموافقةٍ أخلاقية **لا يمثّلهما
جدولٌ في هذه القاعدة أصلًا**. فالمنصّة لا تملك ما تقرأ منه أنّ الإتلاف
مسموح، وتنفيذُه على تخمينٍ إتلافُ نسبٍ علميّ لا يُعاد كتابته.

**ما يلزم لرفع الوقف** — قرارُ معمارية مكتوب (ADR) يحدّد لكل مستوى تصنيف:

1. مدّة الاحتفاظ الواجبة،
2. مَن يملك إذن الإتلاف،
3. ما الذي يبقى في شاهد التدقيق بعده — و**بياناتٌ وصفية فقط**: معرّفٌ ووقتٌ
   وفاعل، ولا سطرَ محتوًى بحثيّ. (سجلُّ التدقيق يُلحَق ولا يُحذف — ترحيل
   0003 ينزع `UPDATE`/`DELETE` عن `athera_app` — فأثرُ البحث فيه باقٍ بعد
   إتلافه لا محالة.)

**وحين يُكتب**: الموضع الوحيد الذي يتغيّر هو
`apps/api/athera_api/services/project_management/retention.py::verdict()`،
ويقابله اختبارٌ في `test_at_project_management.py`. ولا `if` مبعثرةٌ في موجّه.

---

## ٥) ملفّاتٌ مشتركةٌ مُسَّت — **إفصاحٌ لا طلب**

ثلاثةُ ملفّاتٍ عامّة عُدِّلت إضافةً فقط. ويُذكر موضعُ كلٍّ منها لأن ستّة
مساراتٍ تُعدّلها معًا تُنتج تعارضًا يحلّه من لا يعرف نيّة أصحابه:

| الملفّ | التعديل |
|---|---|
| `apps/api/athera_api/models/__init__.py` | استيرادُ نماذج `project_management` وإضافتها إلى `__all__` |
| `apps/api/athera_api/i18n/catalog.py` | ستّة مفاتيح `project_management.*` بلغتيها، كتلةٌ واحدة قبل `validation.failed` |
| `apps/web/messages/{ar,en}.json` | قسمٌ جديد `projectManagement` في آخر الملفّ |
| `apps/web/package.json` | سكربت `test:project-management` |
| `apps/api/athera_api/main.py` | سطرُ استيرادٍ وسطرُ `include_router` — وحدهما، بسببهما في البند ١ |

ولم يُمسّ `.github/workflows/ci.yml` — وهو موضوع الطلب ٢ أعلاه، والفحص
موجودٌ في الشجرة ولا يُشغَّل حتى تُضاف خطوته.

---

## ٦) ما يملكه هذا المسار ولا يشاركه أحد

- **الترحيل `0026_project_management`** (`revision="0026"`, `down_revision="0025"`).
  إضافيٌّ بالكامل: أربعةُ جداول جديدة، وقيدٌ فريدٌ واحد يُضاف إلى
  `project_members` ليكون مرجعًا لمفتاحٍ أجنبيٍّ مركّب.
- `models/project_management.py` · `schemas/project_management.py` ·
  `services/project_management/` · `routers/project_management.py`
- الشاشات: `portfolio/[projectId]/{plan,tasks,timeline}` و`portfolio/trash`
- `apps/web/src/lib/{projectManagement,projectTitle}.ts`
