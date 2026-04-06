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
    return <div className="text-gray-500 py-8">Загрузка...</div>
  }

  const overdueFiltered = overdueTasks?.tasks.filter(
    (t) => t.status_type !== 'done' && t.status_type !== 'closed'
  ) ?? []

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Overview</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard title="Всего задач" value={stats?.total ?? 0} color="purple" />
        <StatCard title="Просрочено" value={stats?.overdue ?? 0} color={stats?.overdue ? 'red' : 'green'} />
        <StatCard title="На этой неделе" value={weekTasks?.total ?? 0} />
        <StatCard title="Компании" value={Object.keys(stats?.by_company ?? {}).length} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div>
          <h2 className="text-lg font-semibold mb-3 text-gray-300">По компаниям</h2>
          <div className="space-y-2">
            {Object.entries(stats?.by_company ?? {})
              .sort(([, a], [, b]) => b - a)
              .map(([company, count]) => (
                <div key={company} className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-900 border border-gray-800">
                  <span className="text-sm">{company}</span>
                  <span className="text-sm font-medium text-purple-400">{count}</span>
                </div>
              ))}
          </div>
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-3 text-gray-300">По статусам</h2>
          <div className="space-y-2">
            {Object.entries(stats?.by_status ?? {})
              .sort(([, a], [, b]) => b - a)
              .map(([status, count]) => (
                <div key={status} className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-900 border border-gray-800">
                  <span className="text-sm">{status}</span>
                  <span className="text-sm font-medium text-gray-300">{count}</span>
                </div>
              ))}
          </div>
        </div>
      </div>

      {overdueFiltered.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold mb-3 text-red-400">Просроченные задачи</h2>
          <TaskTable tasks={overdueFiltered} />
        </div>
      )}

      {(weekTasks?.tasks.length ?? 0) > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3 text-gray-300">На этой неделе</h2>
          <TaskTable tasks={weekTasks!.tasks} />
        </div>
      )}
    </div>
  )
}
