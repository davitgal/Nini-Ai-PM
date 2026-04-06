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
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '24px',
      }}>
        <div>
          <h1 style={{
            fontSize: '22px',
            fontWeight: 700,
            margin: 0,
            letterSpacing: '-0.02em',
            color: '#e8e8f0',
          }}>
            {name}
          </h1>
          {data && (
            <span style={{
              fontSize: '12px',
              color: '#6b6b85',
              marginTop: '4px',
              display: 'block',
            }}>
              {data.total} задач
            </span>
          )}
        </div>
      </div>

      {/* Search */}
      <div style={{ marginBottom: '16px' }}>
        <input
          type="text"
          placeholder="Поиск задач..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0) }}
          style={{
            width: '100%',
            maxWidth: '360px',
            padding: '9px 14px',
            borderRadius: '10px',
            border: '1px solid #2a2a3d',
            background: 'rgba(18, 18, 26, 0.8)',
            fontSize: '13px',
            color: '#e8e8f0',
            outline: 'none',
            transition: 'border-color 0.15s',
            fontFamily: 'inherit',
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = 'rgba(139, 92, 246, 0.4)')}
          onBlur={(e) => (e.currentTarget.style.borderColor = '#2a2a3d')}
        />
      </div>

      {/* Content */}
      {isLoading ? (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 20px',
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
      ) : (
        <>
          <TaskTable tasks={data?.tasks ?? []} />

          {totalPages > 1 && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
              marginTop: '16px',
            }}>
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                style={{
                  padding: '6px 14px',
                  fontSize: '12px',
                  fontWeight: 500,
                  borderRadius: '8px',
                  border: '1px solid #2a2a3d',
                  background: '#1a1a28',
                  color: page === 0 ? '#3a3a50' : '#9898b0',
                  cursor: page === 0 ? 'not-allowed' : 'pointer',
                  fontFamily: 'inherit',
                  transition: 'all 0.1s',
                }}
              >
                ← Назад
              </button>
              <span style={{ fontSize: '12px', color: '#6b6b85' }}>
                {page + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                style={{
                  padding: '6px 14px',
                  fontSize: '12px',
                  fontWeight: 500,
                  borderRadius: '8px',
                  border: '1px solid #2a2a3d',
                  background: '#1a1a28',
                  color: page >= totalPages - 1 ? '#3a3a50' : '#9898b0',
                  cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer',
                  fontFamily: 'inherit',
                  transition: 'all 0.1s',
                }}
              >
                Вперёд →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
