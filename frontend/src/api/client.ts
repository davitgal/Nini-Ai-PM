import type { TaskListResponse, TaskStats } from '../types'

const BASE = ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export function fetchTasks(params: Record<string, string> = {}): Promise<TaskListResponse> {
  const qs = new URLSearchParams(params).toString()
  return get(`/api/v1/tasks${qs ? `?${qs}` : ''}`)
}

export function fetchStats(): Promise<TaskStats> {
  return get('/api/v1/tasks/stats')
}
