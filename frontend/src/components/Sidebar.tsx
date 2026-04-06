import { useState, useEffect, useRef } from 'react'
import { NavLink } from 'react-router-dom'
import { fetchWorkspaces, syncWorkspace, syncAll } from '../api/client'
import type { WorkspaceInfo, SyncResultResponse } from '../types'

const nav = [
  { to: '/', label: 'Overview' },
]

const workspaceRoutes = [
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
  const [workspaces, setWorkspaces] = useState<WorkspaceInfo[]>([])
  const [menuOpen, setMenuOpen] = useState(false)
  const [loadingWs, setLoadingWs] = useState(false)
  const [wsError, setWsError] = useState(false)
  const [syncing, setSyncing] = useState<string | null>(null) // workspace id or 'all'
  const [lastResult, setLastResult] = useState<SyncResultResponse | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // Load workspaces when menu opens
  async function openMenu() {
    setMenuOpen(true)
    setLoadingWs(true)
    setWsError(false)
    try {
      const ws = await fetchWorkspaces()
      setWorkspaces(ws)
    } catch {
      setWsError(true)
    } finally {
      setLoadingWs(false)
    }
  }

  // Close menu on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [menuOpen])

  async function handleSync(workspaceId?: string) {
    setMenuOpen(false)
    setLastResult(null)
    setSyncing(workspaceId ?? 'all')
    try {
      if (workspaceId) {
        const result = await syncWorkspace(workspaceId)
        setLastResult(result)
      } else {
        const results = await syncAll()
        // Combine results
        const combined: SyncResultResponse = {
          workspace: 'All',
          created: results.reduce((s, r) => s + r.created, 0),
          updated: results.reduce((s, r) => s + r.updated, 0),
          skipped: results.reduce((s, r) => s + r.skipped, 0),
          archived: results.reduce((s, r) => s + r.archived, 0),
          errors: results.reduce((s, r) => s + r.errors, 0),
        }
        setLastResult(combined)
      }
    } catch {
      setLastResult({ workspace: '', created: 0, updated: 0, skipped: 0, archived: 0, errors: -1 })
    } finally {
      setSyncing(null)
    }
  }

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

      {workspaceRoutes.map((ws) => (
        <div key={ws.name}>
          <NavLink to={ws.path} className={linkClass}>
            {ws.name}
          </NavLink>
        </div>
      ))}

      {/* Sync section */}
      <div className="mt-auto pt-4 border-t border-gray-800 relative" ref={menuRef}>
        <button
          onClick={() => menuOpen ? setMenuOpen(false) : openMenu()}
          disabled={syncing !== null}
          className="w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors
            bg-purple-600/20 text-purple-400 hover:bg-purple-600/30
            disabled:opacity-50 disabled:cursor-wait
            flex items-center justify-center gap-2"
        >
          {syncing ? (
            <>
              <span className="inline-block w-3.5 h-3.5 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
              Syncing...
            </>
          ) : (
            'Sync ClickUp'
          )}
        </button>

        {menuOpen && (
          <div className="absolute bottom-full left-0 right-0 mb-1 bg-gray-900 border border-gray-700 rounded-lg shadow-xl overflow-hidden z-50">
            {loadingWs ? (
              <div className="px-3 py-3 text-sm text-gray-500 text-center">Loading...</div>
            ) : wsError ? (
              <div className="px-3 py-3 text-sm text-red-400 text-center">
                Backend unavailable
              </div>
            ) : (
              <>
                <button
                  onClick={() => handleSync()}
                  className="w-full px-3 py-2 text-sm text-left text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
                >
                  Sync all workspaces
                </button>
                {workspaces.length > 0 && <div className="border-t border-gray-800" />}
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => handleSync(ws.id)}
                    className="w-full px-3 py-2 text-sm text-left text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
                  >
                    {ws.name}
                  </button>
                ))}
              </>
            )}
          </div>
        )}

        {lastResult && (
          <div className={`mt-2 px-3 py-2 rounded-lg text-xs ${
            lastResult.errors === -1
              ? 'bg-red-900/30 text-red-400'
              : lastResult.errors > 0
                ? 'bg-yellow-900/30 text-yellow-400'
                : 'bg-green-900/30 text-green-400'
          }`}>
            {lastResult.errors === -1 ? (
              'Sync failed'
            ) : (
              <>
                +{lastResult.created} new, {lastResult.updated} updated
                {lastResult.archived > 0 && `, ${lastResult.archived} archived`}
                {lastResult.errors > 0 && `, ${lastResult.errors} errors`}
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  )
}
