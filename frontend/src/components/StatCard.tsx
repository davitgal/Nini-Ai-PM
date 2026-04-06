interface Props {
  title: string
  value: string | number
  color?: 'default' | 'red' | 'green' | 'purple' | 'blue' | 'yellow'
  icon?: string
  children?: React.ReactNode
}

const colorSchemes: Record<string, { border: string; bg: string; value: string; glow: string }> = {
  default: {
    border: '#2a2a3d',
    bg: 'linear-gradient(145deg, rgba(26, 26, 40, 0.8) 0%, rgba(18, 18, 28, 0.6) 100%)',
    value: '#e8e8f0',
    glow: 'none',
  },
  purple: {
    border: 'rgba(139, 92, 246, 0.25)',
    bg: 'linear-gradient(145deg, rgba(139, 92, 246, 0.08) 0%, rgba(99, 102, 241, 0.04) 100%)',
    value: '#a78bfa',
    glow: '0 0 24px rgba(139, 92, 246, 0.08)',
  },
  red: {
    border: 'rgba(239, 68, 68, 0.25)',
    bg: 'linear-gradient(145deg, rgba(239, 68, 68, 0.08) 0%, rgba(220, 38, 38, 0.04) 100%)',
    value: '#f87171',
    glow: '0 0 24px rgba(239, 68, 68, 0.06)',
  },
  green: {
    border: 'rgba(34, 197, 94, 0.25)',
    bg: 'linear-gradient(145deg, rgba(34, 197, 94, 0.08) 0%, rgba(22, 163, 74, 0.04) 100%)',
    value: '#4ade80',
    glow: '0 0 24px rgba(34, 197, 94, 0.06)',
  },
  blue: {
    border: 'rgba(59, 130, 246, 0.25)',
    bg: 'linear-gradient(145deg, rgba(59, 130, 246, 0.08) 0%, rgba(37, 99, 235, 0.04) 100%)',
    value: '#60a5fa',
    glow: '0 0 24px rgba(59, 130, 246, 0.06)',
  },
  yellow: {
    border: 'rgba(234, 179, 8, 0.25)',
    bg: 'linear-gradient(145deg, rgba(234, 179, 8, 0.08) 0%, rgba(202, 138, 4, 0.04) 100%)',
    value: '#fbbf24',
    glow: '0 0 24px rgba(234, 179, 8, 0.06)',
  },
}

export default function StatCard({ title, value, color = 'default', icon, children }: Props) {
  const scheme = colorSchemes[color] || colorSchemes.default
  return (
    <div
      style={{
        borderRadius: '14px',
        border: `1px solid ${scheme.border}`,
        background: scheme.bg,
        padding: '20px 22px',
        boxShadow: scheme.glow,
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
        cursor: 'default',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = scheme.glow.replace('0.08', '0.15').replace('0.06', '0.12')
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = scheme.glow
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '6px',
      }}>
        {icon && <span style={{ fontSize: '13px' }}>{icon}</span>}
        <span style={{
          fontSize: '11px',
          fontWeight: 500,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          color: '#6b6b85',
        }}>
          {title}
        </span>
      </div>
      <div style={{
        fontSize: '28px',
        fontWeight: 700,
        color: scheme.value,
        lineHeight: 1.1,
      }}>
        {value}
      </div>
      {children && (
        <div style={{ marginTop: '10px', fontSize: '13px', color: '#9898b0' }}>
          {children}
        </div>
      )}
    </div>
  )
}
