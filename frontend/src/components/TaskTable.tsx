import type { Task } from '../types'
import StatusBadge from './StatusBadge'

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function isOverdue(task: Task) {
  if (!task.due_date) return false
  if (task.status_type === 'done' || task.status_type === 'closed') return false
  return new Date(task.due_date) < new Date()
}

export default function TaskTable({ tasks }: { tasks: Task[] }) {
  if (tasks.length === 0) {
    return <div className="text-gray-500 py-8 text-center">Нет задач</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
            <th className="text-left py-3 px-3">Название</th>
            <th className="text-left py-3 px-3">Статус</th>
            <th className="text-left py-3 px-3">Компания</th>
            <th className="text-left py-3 px-3">Исполнитель</th>
            <th className="text-left py-3 px-3">Дедлайн</th>
            <th className="text-center py-3 px-3">Ссылка</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr
              key={task.id}
              className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
            >
              <td className="py-3 px-3 max-w-md">
                <div className="truncate">{task.title}</div>
              </td>
              <td className="py-3 px-3">
                <StatusBadge status={task.status} />
              </td>
              <td className="py-3 px-3 text-gray-400">{task.company_tag ?? '—'}</td>
              <td className="py-3 px-3 text-gray-400">
                {task.assignees.length > 0
                  ? task.assignees.map((a) => a.username ?? `#${a.id}`).join(', ')
                  : '—'}
              </td>
              <td className={`py-3 px-3 ${isOverdue(task) ? 'text-red-400 font-medium' : 'text-gray-400'}`}>
                {formatDate(task.due_date)}
              </td>
              <td className="py-3 px-3 text-center">
                {task.clickup_url ? (
                  <a
                    href={task.clickup_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-purple-400 hover:text-purple-300"
                    title="Открыть в ClickUp"
                  >
                    ↗
                  </a>
                ) : (
                  '—'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
