const STATUS_COLORS: Record<string, { color: string; bg: string }> = {
  'open': { color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.12)' },
  'to do': { color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.12)' },
  'in progress': { color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.12)' },
  'in review': { color: '#fb923c', bg: 'rgba(251, 146, 60, 0.12)' },
  'review': { color: '#fb923c', bg: 'rgba(251, 146, 60, 0.12)' },
  'done': { color: '#4ade80', bg: 'rgba(74, 222, 128, 0.12)' },
  'complete': { color: '#4ade80', bg: 'rgba(74, 222, 128, 0.12)' },
  'closed': { color: '#6b7280', bg: 'rgba(107, 114, 128, 0.12)' },
  'need to schedule': { color: '#a78bfa', bg: 'rgba(167, 139, 250, 0.12)' },
  'on hold': { color: '#f87171', bg: 'rgba(248, 113, 113, 0.12)' },
  'blocked': { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)' },
}

const DEFAULT_COLOR = { color: '#9ca3af', bg: 'rgba(156, 163, 175, 0.1)' }

export default function StatusBadge({ status }: { status: string }) {
  const s = STATUS_COLORS[status.toLowerCase()] ?? DEFAULT_COLOR
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '4px',
        fontSize: '11px',
        fontWeight: 500,
        color: s.color,
        background: s.bg,
        whiteSpace: 'nowrap',
        letterSpacing: '0.01em',
      }}
    >
      {status}
    </span>
  )
}
