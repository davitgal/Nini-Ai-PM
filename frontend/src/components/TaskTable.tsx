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

const PRIORITY_MAP: Record<number, { label: string; color: string; bg: string }> = {
  1: { label: 'Urgent', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' },
  2: { label: 'High', color: '#f97316', bg: 'rgba(249, 115, 22, 0.15)' },
  3: { label: 'Normal', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.15)' },
  4: { label: 'Low', color: '#6b7280', bg: 'rgba(107, 114, 128, 0.15)' },
}

function PriorityBadge({ priority }: { priority: number | null }) {
  if (!priority) return <span style={{ color: '#4a4a65', fontSize: '12px' }}>—</span>
  const p = PRIORITY_MAP[priority]
  if (!p) return <span style={{ color: '#4a4a65', fontSize: '12px' }}>P{priority}</span>
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 8px',
        borderRadius: '4px',
        fontSize: '11px',
        fontWeight: 500,
        color: p.color,
        background: p.bg,
        letterSpacing: '0.02em',
      }}
    >
      <span style={{
        width: '6px',
        height: '6px',
        borderRadius: '50%',
        background: p.color,
        display: 'inline-block',
      }} />
      {p.label}
    </span>
  )
}

function HierarchyCell({ value, fallback }: { value: string | null | undefined; fallback?: string }) {
  const text = value || fallback
  if (!text) return <span style={{ color: '#4a4a65' }}>—</span>
  return (
    <span
      style={{
        fontSize: '12px',
        color: '#9898b0',
        maxWidth: '140px',
        display: 'inline-block',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}
      title={text}
    >
      {text}
    </span>
  )
}

interface TaskTableProps {
  tasks: Task[]
  compact?: boolean
}

export default function TaskTable({ tasks, compact = false }: TaskTableProps) {
  if (tasks.length === 0) {
    return (
      <div style={{
        textAlign: 'center',
        padding: '48px 20px',
        color: '#6868880',
        fontSize: '14px',
        background: 'rgba(18, 18, 26, 0.5)',
        borderRadius: '12px',
        border: '1px solid #1e1e30',
      }}>
        Нет задач
      </div>
    )
  }

  const headerStyle: React.CSSProperties = {
    textAlign: 'left',
    padding: '10px 12px',
    fontSize: '10px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: '#6868880',
    borderBottom: '1px solid #2a2a3d',
    whiteSpace: 'nowrap',
  }

  const cellStyle: React.CSSProperties = {
    padding: '10px 12px',
    borderBottom: '1px solid rgba(42, 42, 61, 0.4)',
    verticalAlign: 'middle',
  }

  return (
    <div style={{
      overflowX: 'auto',
      borderRadius: '12px',
      border: '1px solid #2a2a3d',
      background: 'rgba(18, 18, 26, 0.6)',
      backdropFilter: 'blur(8px)',
    }}>
      <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ ...headerStyle, minWidth: '200px' }}>Задача</th>
            <th style={headerStyle}>Статус</th>
            <th style={headerStyle}>Приоритет</th>
            {!compact && <th style={headerStyle}>Workspace</th>}
            {!compact && <th style={headerStyle}>Space</th>}
            {!compact && <th style={headerStyle}>List</th>}
            <th style={headerStyle}>Дедлайн</th>
            <th style={{ ...headerStyle, textAlign: 'center' }}>↗</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr
              key={task.id}
              style={{ transition: 'background 0.15s ease' }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(139, 92, 246, 0.04)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <td style={{ ...cellStyle, maxWidth: '320px' }}>
                <div style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  color: '#e8e8f0',
                  fontWeight: 400,
                }} title={task.title}>
                  {task.title}
                </div>
              </td>
              <td style={cellStyle}>
                <StatusBadge status={task.status} />
              </td>
              <td style={cellStyle}>
                <PriorityBadge priority={task.clickup_priority} />
              </td>
              {!compact && (
                <td style={cellStyle}>
                  <HierarchyCell value={task.workspace_name} />
                </td>
              )}
              {!compact && (
                <td style={cellStyle}>
                  <HierarchyCell value={task.space_name} />
                </td>
              )}
              {!compact && (
                <td style={cellStyle}>
                  <HierarchyCell value={task.list_name} />
                </td>
              )}
              <td style={{
                ...cellStyle,
                color: isOverdue(task) ? '#ef4444' : '#9898b0',
                fontWeight: isOverdue(task) ? 500 : 400,
                fontSize: '12px',
                whiteSpace: 'nowrap',
              }}>
                {formatDate(task.due_date)}
              </td>
              <td style={{ ...cellStyle, textAlign: 'center' }}>
                {task.clickup_url ? (
                  <a
                    href={task.clickup_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      color: '#8b5cf6',
                      textDecoration: 'none',
                      fontSize: '14px',
                      opacity: 0.7,
                      transition: 'opacity 0.15s',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.7')}
                    title="Открыть в ClickUp"
                  >
                    ↗
                  </a>
                ) : (
                  <span style={{ color: '#2a2a3d' }}>—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
