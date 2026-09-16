/**
 * تجميعُ الصلاحيات للعرض وحده — **ولا صلاحيةَ تُخترع هنا** (RC-T1C UX-1).
 *
 * تسعُ صلاحياتٍ في قائمةٍ واحدةٍ من مربّعات الاختيار تُقرأ جدولًا لا شاشة:
 * من يريد أن يمنح «إدارة البيانات» يقرأ التسعَ ليجد واحدة. فتُجمَّع
 * بالغرض، فيصير البحثُ في المجموعة لا في القائمة.
 *
 * **والتجميعُ عرضٌ لا سلطة.** المفاتيحُ هي مفاتيحُ الخادم بنصِّها
 * (`athera_api/services/team.py::PROJECT_PERMISSIONS`)، ولا مجموعةَ
 * تُمنح ككتلة: ما يُرسل إلى `PUT …/permissions` هو المفاتيحُ المختارة
 * فردًا فردًا. ولا يقرأ الخادمُ هذا الملفَّ ولا يعرف بوجوده.
 *
 * **ومفتاحٌ لا مجموعةَ له لا يُخفى.** فلو أضاف الخادمُ صلاحيةً عاشرةً
 * غدًا ظهرت في «أخرى» — والبديلُ أن تُمنع من العرض لأنّ ملفَّ واجهةٍ
 * لم يُحدَّث، وذاك صلاحيةٌ تُحجب بسهو. انظر `groupPermissions`.
 */

/** ترتيبُ المجموعات كما تُعرض — ومفاتيحُها مفاتيحُ الترجمة. */
export const PERMISSION_GROUPS: ReadonlyArray<{
  id: string;
  keys: readonly string[];
}> = [
  { id: "research", keys: ["view_project", "edit_research_content"] },
  { id: "sources", keys: ["manage_sources"] },
  { id: "data", keys: ["manage_data"] },
  { id: "review", keys: ["review_scientific_candidates", "approve_scientific_candidates"] },
  { id: "tasks", keys: ["manage_tasks"] },
  { id: "submission", keys: ["manage_submission"] },
  { id: "team", keys: ["manage_team"] },
];

export interface Vocabulary {
  key: string;
  label: string;
}

/**
 * يوزّع مفرداتَ الخادم على المجموعات — **بلا إسقاطِ مفتاحٍ ولا تكراره**.
 *
 * وما لا مجموعةَ له يجتمع في `other`، وهو الفرعُ الذي يمنع أن تصير
 * الواجهةُ مُرشِّحًا صامتًا لما يقبله الخادم.
 */
export function groupPermissions(
  vocabulary: readonly Vocabulary[],
): Array<{ id: string; items: Vocabulary[] }> {
  const byKey = new Map(vocabulary.map((item) => [item.key, item]));
  const groups: Array<{ id: string; items: Vocabulary[] }> = [];
  const placed = new Set<string>();

  for (const group of PERMISSION_GROUPS) {
    const items = group.keys
      .map((key) => byKey.get(key))
      .filter((item): item is Vocabulary => item !== undefined);
    items.forEach((item) => placed.add(item.key));
    if (items.length > 0) groups.push({ id: group.id, items });
  }

  const rest = vocabulary.filter((item) => !placed.has(item.key));
  if (rest.length > 0) groups.push({ id: "other", items: [...rest] });
  return groups;
}
