import { NavLink } from 'react-router-dom'

const nav = [
  { to: '/', label: 'Overview' },
]

const workspaces = [
  { name: 'TrueCodeLab', path: '/workspace/TrueCodeLab' },
  { name: 'Yerevan Mall', path: '/workspace/Yerevan Mall' },
]

function linkClass({ isActive }: { isActive: boolean }) {
  return `block px-3 py-2 rounded-lg text-sm transition-colors ${
    isActive
      ? 'bg-purple-600/20 text-purple-400'
      : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
  }`
}

export default function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r border-gray-800 p-4 flex flex-col gap-1">
      <div className="text-lg font-bold text-purple-400 mb-4 px-3">Nini</div>

      {nav.map((n) => (
        <NavLink key={n.to} to={n.to} className={linkClass} end>
          {n.label}
        </NavLink>
      ))}

      <div className="text-xs text-gray-500 uppercase tracking-wider mt-6 mb-2 px-3">
        Workspaces
      </div>

      {workspaces.map((ws) => (
        <div key={ws.name}>
          <NavLink to={ws.path} className={linkClass}>
            {ws.name}
          </NavLink>
        </div>
      ))}
    </aside>
  )
}
