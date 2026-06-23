import {
  daysLeft,
  formatDateTimeRu,
  formatReward,
  progressPercent,
  questTypeLabel,
  unwrapList,
} from './apiData'

export interface ApiQuest {
  id: number
  code: string
  title: string
  description?: string
  quest_type: string
  reward_coins: number
  reward_rating_delta?: number
  end_at?: string | null
  auto_verify?: boolean
  manual_complete_allowed?: boolean
}

export interface ApiQuestProgress {
  id: number
  progress_value: number
  is_completed: boolean
  quest: ApiQuest
}

export interface ApiQuestReward {
  id: number
  quest_title: string
  coins_delta: number
  rating_delta: number
  granted_at: string
}

export interface UiQuest {
  id: number
  code: string
  kind: string
  leftDays: string
  progress: number
  title: string
  desc: string
  reward: string
  note: string
  confirm: boolean
  teamNote: string
  completed: boolean
  autoVerify: boolean
}

export interface UiRewardActivity {
  id: number
  title: string
  reward: string
  time: string
}

export function mapActiveQuest(
  quest: ApiQuest,
  progress?: ApiQuestProgress | null,
): UiQuest {
  const completed = progress?.is_completed ?? false
  const autoVerify = Boolean(quest.auto_verify)
  return {
    id: quest.id,
    code: quest.code,
    kind: questTypeLabel(quest.quest_type),
    leftDays: completed ? '0 дн.' : daysLeft(quest.end_at),
    progress: completed ? 100 : progressPercent(progress?.progress_value ?? 0),
    title: quest.title,
    desc: quest.description || '',
    reward: formatReward(quest.reward_coins, quest.reward_rating_delta),
    note: autoVerify ? 'Проверяется автоматически' : '',
    confirm: !completed && !autoVerify && (quest.manual_complete_allowed !== false),
    teamNote: '',
    completed,
    autoVerify,
  }
}

export function mapCompletedProgress(row: ApiQuestProgress): UiQuest {
  const quest = row.quest
  return {
    id: row.id,
    code: quest.code,
    kind: questTypeLabel(quest.quest_type),
    leftDays: '0 дн.',
    progress: 100,
    title: quest.title,
    desc: quest.description || '',
    reward: formatReward(quest.reward_coins, quest.reward_rating_delta),
    note: '',
    confirm: false,
    teamNote: '',
    completed: true,
    autoVerify: Boolean(quest.auto_verify),
  }
}

export function mapRewardHistory(row: ApiQuestReward): UiRewardActivity {
  return {
    id: row.id,
    title: row.quest_title,
    reward: formatReward(row.coins_delta, row.rating_delta),
    time: formatDateTimeRu(row.granted_at),
  }
}

export function mergeActiveQuests(
  active: unknown,
  progressRows: unknown,
): UiQuest[] {
  const quests = unwrapList<ApiQuest>(active)
  const progress = unwrapList<ApiQuestProgress>(progressRows)
  const byCode = new Map(progress.map((p) => [p.quest.code, p]))
  return quests
    .filter((q) => !byCode.get(q.code)?.is_completed)
    .map((q) => mapActiveQuest(q, byCode.get(q.code)))
}

export function mapCompletedQuests(data: unknown): UiQuest[] {
  return unwrapList<ApiQuestProgress>(data).map(mapCompletedProgress)
}

export function mapRewardActivities(data: unknown): UiRewardActivity[] {
  return unwrapList<ApiQuestReward>(data).map(mapRewardHistory)
}

export function pickSelfReportQuestCode(active: unknown): string | null {
  const quests = unwrapList<ApiQuest>(active)
  const candidate = quests.find((q) => q.quest_type === 'self_report' || q.quest_type === 'mixed')
  return candidate?.code ?? quests[0]?.code ?? null
}
