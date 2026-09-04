/**
 * الخيط الذهبي كما يُرسم | The golden thread, as it is drawn.
 *
 * **خطٌّ في الرسم دعوى.** والخادم لا يُرسل وصلةً بلا صفٍّ مخزَّن يشهد لها
 * (`services/golden_thread/weave.py`)، وهذا الملف ينقل ما وصل ولا يصل بين
 * عقدتين لأنّهما متجاورتان في المرحلتين. فالفراغ يُرى فيُسأل عنه، والخطُّ
 * المخترَع يُقرأ إثباتًا ويُنقل إلى قسم المنهجية.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";

/** حالات الوصلة الأربع — مفردة المستودع نفسها لا مفردةٌ ثانية للرسم. */
export const CONNECTION_STATES = [
  "known",
  "needs_review",
  "missing",
  "conflicting",
] as const;

export type ConnectionState = (typeof CONNECTION_STATES)[number];

export interface ThreadNode {
  id: string;
  stage: string;
  label: string;
  /** الجدول الذي قُرئت منه العقدة — «نتيجة» في الخيط ليست «نتيجة» تحليل. */
  origin: string;
  detail: string | null;
}

export interface ThreadStage {
  key: string;
  label: string;
  label_ar: string;
  label_en: string;
  nodes: ThreadNode[];
}

export interface ThreadConnection {
  stage_from: string;
  stage_to: string;
  state: ConnectionState;
  detail: string;
  source_id: string | null;
  source_label: string | null;
  target_id: string | null;
  target_label: string | null;
  /** اسم الصفّ المخزَّن الذي يشهد للوصلة — `null` حين لا صفَّ يشهد. */
  basis: string | null;
}

export interface ThreadReadNote {
  key: string;
  detail: string;
}

export interface GoldenThread {
  project_id: string;
  title: string;
  stages: ThreadStage[];
  connections: ThreadConnection[];
  read_notes: ThreadReadNote[];
  /** أعدادٌ بحالاتها — ولا مجموعَ نقاط ولا نسبة. */
  counts: Record<string, number>;
  note: string;
}

export const goldenThread = (locale: Locale, projectId: string) =>
  apiFetch<GoldenThread>(`/api/v1/projects/${projectId}/thread/golden-view`, {
    locale,
  });

/** مفتاحُ زوج المرحلتين — الوصلات تُعرض مجموعةً بما تصل بينه. */
export function pairKey(connection: ThreadConnection): string {
  return `${connection.stage_from}→${connection.stage_to}`;
}

/**
 * الوصلات مرتّبةً بأزواج مراحلها، وبترتيب المراحل نفسه.
 *
 * ولا يُعتمد على ترتيب ورودها من الخادم: `Map` تحفظ ترتيب الإدخال،
 * والترتيب المقصود هو ترتيب المراحل — كل مرحلةٍ تستمد مشروعيتها ممّا قبلها.
 */
export function byStagePair(
  thread: GoldenThread,
): Array<{ key: string; from: string; to: string; connections: ThreadConnection[] }> {
  const order = thread.stages.map((stage) => stage.key);
  const rank = (connection: ThreadConnection) =>
    order.indexOf(connection.stage_to) * 100 + order.indexOf(connection.stage_from);
  const groups = new Map<string, ThreadConnection[]>();
  for (const connection of [...thread.connections].sort((a, b) => rank(a) - rank(b))) {
    const key = pairKey(connection);
    const existing = groups.get(key);
    if (existing) existing.push(connection);
    else groups.set(key, [connection]);
  }
  return [...groups.entries()].map(([key, connections]) => ({
    key,
    from: connections[0]!.stage_from,
    to: connections[0]!.stage_to,
    connections,
  }));
}

/**
 * حالُ زوجٍ من المراحل حين يُلخَّص في وسم واحد — **بأسوأ ما فيه لا بأغلبه**.
 *
 * فوصلةٌ متعارضة بين تسعٍ معلومة لا يجوز أن تختفي خلف «معلوم»: الوسم
 * الملخِّص يُقرأ حكمًا على الزوج كله، وتلخيصُه بالأغلبية يخفي بالضبط ما
 * جاء الباحث ليراه. ولا مجموعَ نقاطٍ هنا ولا متوسّط.
 */
export function worstState(connections: ThreadConnection[]): ConnectionState {
  const rank: Record<ConnectionState, number> = {
    conflicting: 3,
    needs_review: 2,
    missing: 1,
    known: 0,
  };
  return connections.reduce<ConnectionState>(
    (worst, connection) =>
      rank[connection.state] > rank[worst] ? connection.state : worst,
    "known",
  );
}
