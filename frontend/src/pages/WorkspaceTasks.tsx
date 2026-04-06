import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchTasks } from '../api/client'
import TaskTable from '../components/TaskTable'

export default function WorkspaceTasks() {
  const { name } = useParams<{ name: string }>()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const limit = 50

  const params: Record<string, string> = {
    limit: String(limit),
    page: String(page),
    sort_by: 'date_updated',
    sort_order: 'desc',
  }

  // For TrueCodeLab, show all tasks (it's the main workspace)
  // For other workspaces, filter by company_tag
  if (name && name !== 'TrueCodeLab') {
    params.company = name
  }

  if (search) {
    params.search = search
  }

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', name, page, search],
    queryFn: () => fetchTasks(params),
  })

  const totalPages = data ? Math.ceil(data.total / limit) : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{name}</h1>
        <span className="text-sm text-gray-500">
          {data ? `${data.total} задач` : ''}
        </span>
      </div>

      <div className="mb-4">
        <input
          type="text"
          placeholder="Поиск задач..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0) }}
          className="w-full max-w-sm px-3 py-2 rounded-lg bg-gray-900 border border-gray-700 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-purple-500"
        />
      </div>

      {isLoading ? (
        <div className="text-gray-500 py-8">Загрузка...</div>
      ) : (
        <>
          <TaskTable tasks={data?.tasks ?? []} />

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1 text-sm rounded bg-gray-800 text-gray-300 disabled:opacity-30 hover:bg-gray-700"
              >
                Назад
              </button>
              <span className="text-sm text-gray-500">
                {page + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1 text-sm rounded bg-gray-800 text-gray-300 disabled:opacity-30 hover:bg-gray-700"
              >
                Вперёд
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
