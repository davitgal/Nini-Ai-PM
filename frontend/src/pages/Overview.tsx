import { useQuery } from '@tanstack/react-query'
import { fetchStats, fetchTasks } from '../api/client'
import StatCard from '../components/StatCard'
import TaskTable from '../components/TaskTable'

export default function Overview() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
  })

  const now = new Date()
  const weekLater = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)

  const { data: overdueTasks } = useQuery({
    queryKey: ['tasks', 'overdue'],
    queryFn: () =>
      fetchTasks({
        due_before: now.toISOString(),
        sort_by: 'due_date',
        sort_order: 'asc',
        limit: '20',
      }),
  })

  const { data: weekTasks } = useQuery({
    queryKey: ['tasks', 'week'],
    queryFn: () =>
      fetchTasks({
        due_after: now.toISOString(),
        due_before: weekLater.toISOString(),
        sort_by: 'due_date',
        sort_order: 'asc',
        limit: '20',
      }),
  })

  if (statsLoading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '80px 20px',
        color: '#6b6b85',
        fontSize: '14px',
      }}>
        <span style={{
          display: 'inline-block',
          width: '16px',
          height: '16px',
          border: '2px solid #2a2a3d',
          borderTopColor: '#8b5cf6',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
          marginRight: '10px',
        }} />
        Загрузка...
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  const overdueFiltered = overdueTasks?.tasks.filter(
    (t) => t.status_type !== 'done' && t.status_type !== 'closed'
  ) ?? []

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
        <StatCard title="На этой неделе" value={weekTasks?.total ?? 0} color="blue" icon="📅" />
        <StatCard
          title="Компании"
          value={Object.keys(stats?.by_company ?? {}).length}
          color="default"
          icon="🏢"
        />
      </div>

      {/* Two-column breakdown */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '20px',
        marginBottom: '32px',
      }}>
        {/* By company */}
        <div>
          <h2 style={{
            fontSize: '14px',
            fontWeight: 600,
            color: '#9898b0',
            margin: '0 0 12px',
            letterSpacing: '0.01em',
          }}>
            По компаниям
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {Object.entries(stats?.by_company ?? {})
              .sort(([, a], [, b]) => b - a)
              .map(([company, count]) => (
                <div
                  key={company}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    background: 'rgba(18, 18, 26, 0.6)',
                    border: '1px solid #1e1e30',
                    transition: 'background 0.1s',
                    cursor: 'default',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(26, 26, 40, 0.8)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(18, 18, 26, 0.6)')}
                >
                  <span style={{ fontSize: '13px', color: '#c8c8d8' }}>{company}</span>
                  <span style={{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#a78bfa',
                    minWidth: '28px',
                    textAlign: 'right',
                  }}>
                    {count}
                  </span>
                </div>
              ))}
          </div>
        </div>

        {/* By status */}
        <div>
          <h2 style={{
            fontSize: '14px',
            fontWeight: 600,
            color: '#9898b0',
            margin: '0 0 12px',
            letterSpacing: '0.01em',
          }}>
            По статусам
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {Object.entries(stats?.by_status ?? {})
              .sort(([, a], [, b]) => b - a)
              .map(([status, count]) => (
                <div
                  key={status}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    background: 'rgba(18, 18, 26, 0.6)',
                    border: '1px solid #1e1e30',
                    transition: 'background 0.1s',
                    cursor: 'default',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(26, 26, 40, 0.8)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(18, 18, 26, 0.6)')}
                >
                  <span style={{ fontSize: '13px', color: '#c8c8d8' }}>{status}</span>
                  <span style={{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: '#9898b0',
                    minWidth: '28px',
                    textAlign: 'right',
                  }}>
                    {count}
                  </span>
                </div>
              ))}
          </div>
        </div>
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
