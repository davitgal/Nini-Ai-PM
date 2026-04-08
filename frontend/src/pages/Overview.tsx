import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createNiniIssue, fetchNiniIssues, fetchStats, fetchTasks, updateNiniIssue } from '../api/client'
import StatCard from '../components/StatCard'
import TaskTable from '../components/TaskTable'

export default function Overview() {
  const queryClient = useQueryClient()
  const [issueTitle, setIssueTitle] = useState('')
  const [issueDesc, setIssueDesc] = useState('')
  const [issueSeverity, setIssueSeverity] = useState('medium')

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })

  const now = new Date()
  const weekLater = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)

  const { data: overdueTasks } = useQuery({
    queryKey: ['tasks', 'overdue'],
    queryFn: () =>
      fetchTasks({
        due_before: now.toISOString(),
        unresolved_only: 'true',
        include_total: 'false',
        sort_by: 'due_date',
        sort_order: 'asc',
        limit: '20',
      }),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })

  const { data: weekTasks } = useQuery({
    queryKey: ['tasks', 'week'],
    queryFn: () =>
      fetchTasks({
        due_after: now.toISOString(),
        due_before: weekLater.toISOString(),
        unresolved_only: 'true',
        include_total: 'false',
        sort_by: 'due_date',
        sort_order: 'asc',
        limit: '20',
      }),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })

  const { data: issuesData, isLoading: issuesLoading } = useQuery({
    queryKey: ['nini-issues'],
    queryFn: () => fetchNiniIssues({ limit: '30' }),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })

  const createIssue = useMutation({
    mutationFn: createNiniIssue,
    onSuccess: () => {
      setIssueTitle('')
      setIssueDesc('')
      setIssueSeverity('medium')
      queryClient.invalidateQueries({ queryKey: ['nini-issues'] })
    },
  })

  const patchIssue = useMutation({
    mutationFn: ({ issueId, status }: { issueId: string; status: string }) =>
      updateNiniIssue(issueId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nini-issues'] })
    },
  })

  const overdueFiltered = overdueTasks?.tasks.filter(
    (t) => t.status_type !== 'done' && t.status_type !== 'closed'
  ) ?? []
  const issues = issuesData?.items ?? []
  const openIssues = issues.filter((i) => i.status !== 'fixed' && i.status !== 'ignored')

  function severityColor(severity: string): string {
    if (severity === 'critical') return '#f87171'
    if (severity === 'high') return '#fb923c'
    if (severity === 'medium') return '#facc15'
    return '#60a5fa'
  }

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{
          fontSize: '24px',
          fontWeight: 700,
          margin: 0,
          letterSpacing: '-0.02em',
          color: '#e8e8f0',
        }}>
          Dashboard
        </h1>
        <p style={{
          fontSize: '13px',
          color: '#6b6b85',
          margin: '4px 0 0',
        }}>
          Nini AI Project Manager — overview всех задач
        </p>
      </div>

      {/* Stats grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '14px',
        marginBottom: '32px',
      }}>
        <StatCard title="Всего задач" value={stats?.total ?? 0} color="purple" icon="📋" />
        <StatCard
          title="Просрочено"
          value={stats?.overdue ?? 0}
          color={stats?.overdue ? 'red' : 'green'}
          icon={stats?.overdue ? '🔴' : '✅'}
        />
        <StatCard title="На этой неделе" value={weekTasks?.tasks.length ?? 0} color="blue" icon="📅" />
        <StatCard
          title="Nini issues"
          value={openIssues.length}
          color={openIssues.length > 0 ? 'red' : 'green'}
          icon={openIssues.length > 0 ? '🧩' : '✅'}
        />
      </div>

      {statsLoading && (
        <div style={{ color: '#6b6b85', fontSize: '12px', marginTop: '-20px', marginBottom: '20px' }}>
          Обновляю статистику...
        </div>
      )}

      {/* Nini issues backlog */}
      <div style={{
        marginBottom: '32px',
        padding: '16px',
        borderRadius: '12px',
        background: 'rgba(18, 18, 26, 0.6)',
        border: '1px solid #1e1e30',
      }}>
        <h2 style={{
          fontSize: '14px',
          fontWeight: 600,
          color: '#c4b5fd',
          margin: '0 0 12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <span>🧩</span> Nini Issues Backlog
          <span style={{
            fontSize: '11px',
            fontWeight: 500,
            padding: '2px 8px',
            borderRadius: '10px',
            background: 'rgba(139, 92, 246, 0.12)',
            color: '#c4b5fd',
          }}>
            open: {openIssues.length} / total: {issues.length}
          </span>
        </h2>

        <div style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr auto',
          gap: '8px',
          marginBottom: '10px',
        }}>
          <input
            value={issueTitle}
            onChange={(e) => setIssueTitle(e.target.value)}
            placeholder="Краткий заголовок проблемы"
            style={{
              background: '#11111a',
              border: '1px solid #2a2a3d',
              color: '#e8e8f0',
              borderRadius: '8px',
              fontSize: '12px',
              padding: '8px 10px',
            }}
          />
          <select
            value={issueSeverity}
            onChange={(e) => setIssueSeverity(e.target.value)}
            style={{
              background: '#11111a',
              border: '1px solid #2a2a3d',
              color: '#e8e8f0',
              borderRadius: '8px',
              fontSize: '12px',
              padding: '8px 10px',
            }}
          >
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
            <option value="critical">critical</option>
          </select>
          <button
            onClick={() => {
              if (!issueTitle.trim()) return
              createIssue.mutate({
                title: issueTitle.trim(),
                description: issueDesc.trim(),
                issue_type: 'logic',
                severity: issueSeverity,
                source: 'manual',
              })
            }}
            disabled={createIssue.isPending || !issueTitle.trim()}
            style={{
              border: '1px solid rgba(139, 92, 246, 0.3)',
              background: 'rgba(139, 92, 246, 0.15)',
              color: '#c4b5fd',
              borderRadius: '8px',
              padding: '8px 12px',
              fontSize: '12px',
              cursor: createIssue.isPending ? 'wait' : 'pointer',
              opacity: createIssue.isPending || !issueTitle.trim() ? 0.6 : 1,
            }}
          >
            {createIssue.isPending ? 'Saving...' : 'Add issue'}
          </button>
        </div>

        <textarea
          value={issueDesc}
          onChange={(e) => setIssueDesc(e.target.value)}
          placeholder="Описание: что пошло не так и как проявилось"
          rows={2}
          style={{
            width: '100%',
            resize: 'vertical',
            background: '#11111a',
            border: '1px solid #2a2a3d',
            color: '#c8c8d8',
            borderRadius: '8px',
            fontSize: '12px',
            padding: '8px 10px',
            marginBottom: '12px',
            boxSizing: 'border-box',
          }}
        />

        {issuesLoading ? (
          <div style={{ color: '#6b6b85', fontSize: '12px' }}>Loading issues...</div>
        ) : issues.length === 0 ? (
          <div style={{ color: '#6b6b85', fontSize: '12px' }}>Пока нет записанных проблем.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {issues.map((issue) => (
              <div
                key={issue.id}
                style={{
                  border: '1px solid #26263a',
                  background: '#11111a',
                  borderRadius: '10px',
                  padding: '10px 12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                    <span style={{
                      fontSize: '10px',
                      textTransform: 'uppercase',
                      padding: '2px 6px',
                      borderRadius: '10px',
                      border: `1px solid ${severityColor(issue.severity)}55`,
                      color: severityColor(issue.severity),
                    }}>
                      {issue.severity}
                    </span>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: '#e8e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {issue.title}
                    </span>
                  </div>
                  <span style={{ fontSize: '11px', color: '#8181a6' }}>{issue.status}</span>
                </div>
                {issue.description && (
                  <div style={{ fontSize: '12px', color: '#a8a8bd', marginTop: '6px' }}>
                    {issue.description}
                  </div>
                )}
                <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
                  {['in_progress', 'fixed', 'ignored'].map((s) => (
                    <button
                      key={s}
                      onClick={() => patchIssue.mutate({ issueId: issue.id, status: s })}
                      disabled={patchIssue.isPending}
                      style={{
                        border: '1px solid #2d2d45',
                        background: issue.status === s ? 'rgba(139, 92, 246, 0.2)' : 'transparent',
                        color: issue.status === s ? '#c4b5fd' : '#9898b0',
                        borderRadius: '8px',
                        padding: '4px 8px',
                        fontSize: '11px',
                        cursor: patchIssue.isPending ? 'wait' : 'pointer',
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Overdue tasks */}
      {overdueFiltered.length > 0 && (
        <div style={{ marginBottom: '32px' }}>
          <h2 style={{
            fontSize: '14px',
            fontWeight: 600,
            color: '#f87171',
            margin: '0 0 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}>
            <span>🔴</span> Просроченные задачи
            <span style={{
              fontSize: '11px',
              fontWeight: 500,
              padding: '2px 8px',
              borderRadius: '10px',
              background: 'rgba(239, 68, 68, 0.12)',
              color: '#f87171',
            }}>
              {overdueFiltered.length}
            </span>
          </h2>
          <TaskTable tasks={overdueFiltered} compact />
        </div>
      )}

      {/* This week */}
      {(weekTasks?.tasks.length ?? 0) > 0 && (
        <div>
          <h2 style={{
            fontSize: '14px',
            fontWeight: 600,
            color: '#9898b0',
            margin: '0 0 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}>
            <span>📅</span> На этой неделе
            <span style={{
              fontSize: '11px',
              fontWeight: 500,
              padding: '2px 8px',
              borderRadius: '10px',
              background: 'rgba(59, 130, 246, 0.12)',
              color: '#60a5fa',
            }}>
              {weekTasks!.tasks.length}
            </span>
          </h2>
          <TaskTable tasks={weekTasks!.tasks} compact />
        </div>
      )}
    </div>
  )
}
