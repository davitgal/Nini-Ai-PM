interface Props {
  title: string
  value: string | number
  color?: 'default' | 'red' | 'green' | 'purple'
  children?: React.ReactNode
}

const colors = {
  default: 'border-gray-700 bg-gray-900',
  red: 'border-red-800/50 bg-red-950/30',
  green: 'border-green-800/50 bg-green-950/30',
  purple: 'border-purple-800/50 bg-purple-950/30',
}

const valueColors = {
  default: 'text-gray-100',
  red: 'text-red-400',
  green: 'text-green-400',
  purple: 'text-purple-400',
}

export default function StatCard({ title, value, color = 'default', children }: Props) {
  return (
    <div className={`rounded-xl border p-5 ${colors[color]}`}>
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">{title}</div>
      <div className={`text-2xl font-bold ${valueColors[color]}`}>{value}</div>
      {children && <div className="mt-3 text-sm text-gray-400">{children}</div>}
    </div>
  )
}
