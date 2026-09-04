/**
 * إدارة المشروع البحثي | Project-management client (PUBRIVA).
 *
 * **لا حقل في هذه الأنواع يحمل نسبة.** ولا `number` منها كسرٌ: الأعداد
 * صحيحةٌ لأنها أعداد — ثلاث مهامّ متأخرة، مَعْلَمان معتمَدان. و«٧٣٪
 * مكتمل» لا عقد علميّ خلفه، والباحث يصدّقه لأنه رقم.
 *
 * **والمرحلة أربعة حقول لا حقل**: حاليّة، وهل أكّدها إنسان، وما المقترَح،
 * وبأيّ سند. وطيُّها في نصٍّ واحد يجعل القارئ يظنّ أن المنصّة تعرف.
 */
import { apiFetch } from "./api";
import type { Locale } from "./i18n";
import type { ProjectTitleFields } from "./projectTitle";

export type Load = "loading" | "ready" | "failed";

export type TaskStatus =
  | "not_started"
  | "in_progress"
  | "awaiting_review"
  | "needs_decision"
  | "blocked"
  | "completed";

export type TaskPriority = "low" | "normal" | "high";

/** السندان اللذان لا ثالث لهما — و`none` امتناعٌ يحمل سببه. */
export type SuggestionBasis = "milestone_completed" | "conventional_order" | "none";

export interface StageSuggestion {
  is_offered: boolean;
  stage: string | null;
  stage_label: string | null;
  basis_kind: SuggestionBasis;
  basis: string;
}

export interface ProjectStage {
  current_stage: string;
  current_stage_label: string;
  /** **مشروعٌ لم يؤكِّد صاحبُه مرحلته ليس في «الفكرة» يقينًا.** */
  is_researcher_confirmed: boolean;
  confirmed_by: string | null;
  confirmed_at: string | null;
  confirmation_note_ar: string | null;
  suggestion: StageSuggestion;
  disclaimer: string;
}

export interface StageEvent {
  id: string;
  from_stage: string | null;
  from_stage_label: string | null;
  to_stage: string;
  to_stage_label: string;
  occurred_at: string;
  confirmed_by: string;
  note_ar: string | null;
  system_suggested_stage: string | null;
  followed_the_suggestion: boolean | null;
  /** حقيقةٌ تُعرض ولا تُوصف تراجعًا: التحليل قد يكشف عيبًا في التصميم. */
  is_return_to_earlier_stage: boolean;
}

export interface StageHistory {
  project_id: string;
  events: StageEvent[];
  note: string;
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  stage: string;
  stage_label: string;
  status: TaskStatus;
  status_label: string;
  priority: TaskPriority;
  priority_label: string;
  assignee_member_id: string | null;
  assignee_name: string | null;
  created_by: string;
  source: string;
  source_label: string;
  suggested_by_system: boolean;
  accepted_by: string | null;
  accepted_at: string | null;
  due_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  /** يُحسَب في الخادم عند القراءة — ولا يُخزَّن، فلا يكذب عند منتصف الليل. */
  is_overdue: boolean;
  requires_decision: boolean;
  decision_gate: string | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
  created_at: string;
  updated_at: string;
}

/** **أعدادٌ فقط.** ولا حقل هنا كسر. */
export interface TaskCounts {
  open: number;
  overdue: number;
  awaiting_your_decision: number;
  awaiting_review: number;
  blocked: number;
  completed: number;
  total: number;
}

export interface TasksView {
  project_id: string;
  tasks: Task[];
  counts: TaskCounts;
  note: string;
}

export interface TaskSuggestion {
  key: string;
  title_ar: string;
  why_ar: string;
  stage: string;
  stage_label: string;
  priority: TaskPriority;
  source: string;
}

export interface TaskSuggestionsView {
  project_id: string;
  suggestions: TaskSuggestion[];
  note: string;
}

export interface Milestone {
  key: string;
  label: string;
  target_date: string | null;
  completed_at: string | null;
  /** **الإتمام له صاحب** — ولا يُستنتج من زيارةِ صفحة. */
  completed_by: string | null;
  evidence_note_ar: string | null;
  is_completed: boolean;
}

export interface MilestonesView {
  project_id: string;
  milestones: Milestone[];
  note: string;
}

export interface AttentionItem {
  key: string;
  label: string;
  detail: string;
  count: number | null;
  destination: string;
}

export interface MissingItem {
  key: string;
  label: string;
  expected_since_stage: string;
  expected_since_stage_label: string;
}

export interface Activity {
  kind: string;
  occurred_at: string;
  subject: string;
  actor_user_id: string | null;
}

export interface Dashboard {
  project_id: string;
  title: ProjectTitleFields;
  stage: ProjectStage;
  start_date: string | null;
  target_completion_date: string | null;
  counts: TaskCounts;
  team_members: number;
  missing_scientific_items: MissingItem[];
  recent_activity: Activity[];
  needs_your_attention: AttentionItem[];
  nothing_urgent_note: string;
}

export interface Timeline {
  start_date: string | null;
  target_completion_date: string | null;
  milestones: Milestone[];
  stage_events: StageEvent[];
}

export interface DependencyCount {
  kind: string;
  count: number;
  label: string;
}

export interface DeletionPreview {
  project_id: string;
  title: ProjectTitleFields;
  is_in_trash: boolean;
  dependencies: DependencyCount[];
  total_dependent_rows: number;
  /** **الوقف حكمُ امتناعٍ مدروس، لا عطب** — والسبب في الاستجابة نفسها. */
  is_blocked: boolean;
  blocked_reason: string;
  message: string;
  unblock_requirement: string;
  policy_sources: string[];
}

export interface TrashedProject {
  project_id: string;
  title: ProjectTitleFields;
  created_at: string;
  deleted_at: string | null;
  deleted_by: string | null;
}

export interface TrashView {
  projects: TrashedProject[];
  note: string;
}

export interface VocabularyEntry {
  key: string;
  label: string;
}

export interface Vocabulary {
  stages: VocabularyEntry[];
  milestones: VocabularyEntry[];
  task_statuses: VocabularyEntry[];
  task_priorities: VocabularyEntry[];
  task_sources: VocabularyEntry[];
}

const base = "/api/v1/project-management";

export const loadVocabulary = (locale: Locale) =>
  apiFetch<Vocabulary>(`${base}/vocabulary`, { locale });

export const loadDashboard = (locale: Locale, projectId: string) =>
  apiFetch<Dashboard>(`${base}/projects/${projectId}/dashboard`, { locale });

export const loadStage = (locale: Locale, projectId: string) =>
  apiFetch<ProjectStage>(`${base}/projects/${projectId}/stage`, { locale });

/** اعتمادُ المرحلة — **فعلُ الباحث، وهو المسار الوحيد الذي يغيّرها**. */
export const confirmStage = (
  locale: Locale,
  projectId: string,
  stage: string,
  noteAr?: string,
) =>
  apiFetch<ProjectStage>(`${base}/projects/${projectId}/stage/confirm`, {
    locale,
    method: "POST",
    body: JSON.stringify({ stage, note_ar: noteAr ?? null }),
  });

export const loadStageHistory = (locale: Locale, projectId: string) =>
  apiFetch<StageHistory>(`${base}/projects/${projectId}/stage/history`, { locale });

export const loadTasks = (locale: Locale, projectId: string, status?: string) =>
  apiFetch<TasksView>(
    `${base}/projects/${projectId}/tasks${status ? `?status=${status}` : ""}`,
    { locale },
  );

export interface NewTask {
  title: string;
  stage: string;
  description?: string | null;
  priority?: TaskPriority;
  assignee_member_id?: string | null;
  due_at?: string | null;
  requires_decision?: boolean;
  source?: string;
  /**
   * **بوابة القبول.** ومهمّةٌ مصدرها اقتراحٌ آليّ لا تُنشأ إلا بها — والخادم
   * يردّ ٤٢٢ بدونها، والقاعدة ترفض الصفّ أصلًا.
   */
  accept_suggestion?: boolean;
}

export const createTask = (locale: Locale, projectId: string, task: NewTask) =>
  apiFetch<Task>(`${base}/projects/${projectId}/tasks`, {
    locale,
    method: "POST",
    body: JSON.stringify(task),
  });

export const updateTask = (
  locale: Locale,
  projectId: string,
  taskId: string,
  patch: Record<string, unknown>,
) =>
  apiFetch<Task>(`${base}/projects/${projectId}/tasks/${taskId}`, {
    locale,
    method: "PATCH",
    body: JSON.stringify(patch),
  });

/** معاينة — **لا تكتب في القاعدة شيئًا**. */
export const loadTaskSuggestions = (locale: Locale, projectId: string) =>
  apiFetch<TaskSuggestionsView>(`${base}/projects/${projectId}/task-suggestions`, {
    locale,
  });

export const loadMilestones = (locale: Locale, projectId: string) =>
  apiFetch<MilestonesView>(`${base}/projects/${projectId}/milestones`, { locale });

export const setMilestone = (
  locale: Locale,
  projectId: string,
  key: string,
  patch: Record<string, unknown>,
) =>
  apiFetch<Milestone>(`${base}/projects/${projectId}/milestones/${key}`, {
    locale,
    method: "PUT",
    body: JSON.stringify(patch),
  });

export const loadTimeline = (locale: Locale, projectId: string) =>
  apiFetch<Timeline>(`${base}/projects/${projectId}/timeline`, { locale });

export const updatePlan = (
  locale: Locale,
  projectId: string,
  patch: Record<string, unknown>,
) =>
  apiFetch<Timeline>(`${base}/projects/${projectId}/plan`, {
    locale,
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const loadTrash = (locale: Locale) =>
  apiFetch<TrashView>(`${base}/trash`, { locale });

export const loadDeletionPreview = (locale: Locale, projectId: string) =>
  apiFetch<DeletionPreview>(`${base}/trash/${projectId}/deletion-preview`, {
    locale,
  });

/**
 * الإتلاف الدائم — **موقوف، ويردّ الخادم ٤٠٩ برسالةٍ تقول لماذا**.
 *
 * والدالّة قائمةٌ لأن الشاشة تعرض الزرّ وتُظهر الجواب: زرٌّ يختفي يجعل
 * الباحث يظنّ الميزة غير موجودة، وزرٌّ يعمل بصمت يُتلف ما لا يُعاد.
 */
export const requestPermanentDelete = (locale: Locale, projectId: string) =>
  apiFetch<DeletionPreview>(`${base}/trash/${projectId}/permanent-delete`, {
    locale,
    method: "POST",
  });
