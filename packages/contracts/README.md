# عقود API | API Contracts

مصدر واحد للحقيقة بين الخلفية والواجهة (§50).

`openapi.json` **مولَّد لا مكتوب** — لا يُحرَّر يدويًا:

```bash
make openapi   # apps/api → packages/contracts/openapi.json
```

منه تُولَّد أنواع TypeScript لعميل الواجهة. أي انحراف بين الكود والعقد يكسر الـCI.
