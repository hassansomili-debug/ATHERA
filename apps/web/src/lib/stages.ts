/**
 * مرحلة المشروع — **مشتقّة من حالته الفعلية لا مخترعة**.
 *
 * المصدر الوحيد هو `current_gate` الذي يعيده الخادم: البوابة التي بلغها
 * المشروع في سلسلة الاعتمادات. والخريطة أدناه صريحة ومكتوبة، فلا تُخمَّن
 * مرحلة من رقم ولا تُلفَّق نسبة تقدّم من بيانات غير متاحة.
 *
 * ومشروع بلا بوابة مقطوعة هو مشروع في مرحلة الفكرة — وهذا وصف صادق لا
 * افتراض.
 */
export const STAGE_BY_GATE: Record<string, string> = {
  G0: "idea", G1: "idea",
  G2: "literature", G3: "literature",
  G4: "design", G5: "design",
  G6: "data",
  G7: "analysis", G8: "analysis",
  G9: "writing",
  G10: "journal", G11: "ready", G12: "review",
  GT1: "design",
};

export function stageKeyFor(currentGate: string | null): string {
  if (!currentGate) return "idea";
  return STAGE_BY_GATE[currentGate] ?? "idea";
}
