export interface Task {
  id: string
  clickup_task_id: string | null
  title: string
  description: string
  status: string
  status_type: string | null
  clickup_priority: number | null
  nini_priority: string
  company_tag: string | null
  task_type_tag: string | null
  assignees: { id?: number; username?: string }[]
  due_date: string | null
  start_date: string | null
  date_created: string | null
  date_updated: string | null
  clickup_url: string | null
  tags: string[]
  archived: boolean
  last_synced_at: string
  created_at: string
  updated_at: string
}

export interface TaskListResponse {
  tasks: Task[]
  total: number
  page: number
  limit: number
}

export interface TaskStats {
  total: number
  by_status: Record<string, number>
  by_company: Record<string, number>
  by_priority: Record<string, number>
  overdue: number
}
