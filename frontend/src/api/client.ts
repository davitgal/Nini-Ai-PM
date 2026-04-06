import type { TaskListResponse, TaskStats, WorkspaceInfo, SyncResultResponse } from '../types'

const BASE = ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

export function fetchTasks(params: Record<string, string> = {}): Promise<TaskListResponse> {
  const qs = new URLSearchParams(params).toString()
  return get(`/api/v1/tasks${qs ? `?${qs}` : ''}`)
}

export function fetchStats(): Promise<TaskStats> {
  return get('/api/v1/tasks/stats')
}

export function fetchWorkspaces(): Promise<WorkspaceInfo[]> {
  return get('/api/v1/sync/workspaces')
}

export function syncWorkspace(workspaceId: string): Promise<SyncResultResponse> {
  return post(`/api/v1/sync/workspace/${workspaceId}`)
}

export function syncAll(): Promise<SyncResultResponse[]> {
  return post('/api/v1/sync/full')
}
