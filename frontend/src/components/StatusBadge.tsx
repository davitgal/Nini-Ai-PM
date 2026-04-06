const STATUS_COLORS: Record<string, string> = {
  open: 'bg-blue-500/20 text-blue-400',
  'to do': 'bg-blue-500/20 text-blue-400',
  'in progress': 'bg-yellow-500/20 text-yellow-400',
  review: 'bg-orange-500/20 text-orange-400',
  done: 'bg-green-500/20 text-green-400',
  closed: 'bg-gray-500/20 text-gray-400',
  'need to schedule': 'bg-violet-500/20 text-violet-400',
}

export default function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status.toLowerCase()] ?? 'bg-gray-500/20 text-gray-400'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {status}
    </span>
  )
}
