import { useState, useEffect, useRef } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { fetchWorkspaces, syncWorkspace, syncAll, cleanupAndSync } from '../api/client'
import type { WorkspaceInfo, SyncResultResponse } from '../types'

export default function Sidebar() {
  const location = useLocation()
  const [workspaces, setWorkspaces] = useState<WorkspaceInfo[]>([])
  const [wsLoaded, setWsLoaded] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [loadingWs, setLoadingWs] = useState(false)
  const [wsError, setWsError] = useState(false)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<SyncResultResponse | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // Load workspaces on mount for sidebar nav
  useEffect(() => {
    async function load() {
      try {
        const ws = await fetchWorkspaces()
        setWorkspaces(ws)
        setWsLoaded(true)
      } catch {
        // Workspaces will load when sync menu opens
      }
    }
    load()
  }, [])

  // Load workspaces when menu opens (refresh)
  async function openMenu() {
    setMenuOpen(true)
    setLoadingWs(true)
    setWsError(false)
    try {
      const ws = await fetchWorkspaces()
      setWorkspaces(ws)
      setWsLoaded(true)
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

  async function handleCleanup() {
    setMenuOpen(false)
    setLastResult(null)
    setSyncing('cleanup')
    try {
      const result = await cleanupAndSync()
      setLastResult(result)
    } catch {
      setLastResult({ workspace: '', created: 0, updated: 0, skipped: 0, archived: 0, errors: -1 })
    } finally {
      setSyncing(null)
    }
  }

  function isActive(path: string) {
    return location.pathname === path
  }

  const linkStyle = (active: boolean): React.CSSProperties => ({
    display: 'block',
    padding: '8px 14px',
    borderRadius: '8px',
    fontSize: '13px',
    fontWeight: active ? 500 : 400,
    color: active ? '#a78bfa' : '#9898b0',
    background: active ? 'rgba(139, 92, 246, 0.1)' : 'transparent',
    textDecoration: 'none',
    transition: 'all 0.15s ease',
    cursor: 'pointer',
  })

  const formatLastSync = (iso: string | null) => {
    if (!iso) return 'never'
    const d = new Date(iso)
    const now = new Date()
    const diffMin = Math.round((now.getTime() - d.getTime()) / 60000)
    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    const diffH = Math.round(diffMin / 60)
    if (diffH < 24) return `${diffH}h ago`
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  }

  return (
    <aside style={{
      width: '220px',
      flexShrink: 0,
      borderRight: '1px solid #1e1e30',
      padding: '20px 12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '2px',
      background: 'rgba(12, 12, 18, 0.8)',
    }}>
      {/* Logo */}
      <div style={{
        fontSize: '20px',
        fontWeight: 700,
        background: 'linear-gradient(135deg, #a78bfa 0%, #818cf8 100%)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        padding: '4px 14px 16px',
        letterSpacing: '-0.02em',
      }}>
        Nini
      </div>

      {/* Nav */}
      <NavLink to="/" style={() => linkStyle(isActive('/'))}>
        <span style={{ marginRight: '8px', opacity: 0.7 }}>📊</span>
        Overview
      </NavLink>

      {/* Workspaces section */}
      <div style={{
        fontSize: '10px',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        color: '#4a4a65',
        marginTop: '20px',
        marginBottom: '6px',
        padding: '0 14px',
      }}>
        Workspaces
      </div>

      {wsLoaded && workspaces.map((ws) => (
        <NavLink
          key={ws.id}
          to={`/workspace/${encodeURIComponent(ws.name)}`}
          style={() => linkStyle(isActive(`/workspace/${encodeURIComponent(ws.name)}`))}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>
              <span style={{ marginRight: '8px', opacity: 0.7 }}>🏢</span>
              {ws.name}
            </span>
            {ws.sync_enabled && (
              <span style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: ws.webhook_active ? '#4ade80' : '#6b7280',
                display: 'inline-block',
                flexShrink: 0,
              }} />
            )}
          </div>
          {ws.last_full_sync && (
            <div style={{ fontSize: '10px', color: '#4a4a65', marginTop: '2px', paddingLeft: '24px' }}>
              synced {formatLastSync(ws.last_full_sync)}
            </div>
          )}
        </NavLink>
      ))}

      {!wsLoaded && (
        <div style={{ padding: '8px 14px', fontSize: '12px', color: '#4a4a65' }}>
          Loading workspaces...
        </div>
      )}

      {/* Sync section */}
      <div style={{
        marginTop: 'auto',
        paddingTop: '16px',
        borderTop: '1px solid #1e1e30',
        position: 'relative',
      }} ref={menuRef}>
        <button
          onClick={() => menuOpen ? setMenuOpen(false) : openMenu()}
          disabled={syncing !== null}
          style={{
            width: '100%',
            padding: '10px 14px',
            borderRadius: '10px',
            fontSize: '13px',
            fontWeight: 500,
            border: '1px solid rgba(139, 92, 246, 0.2)',
            background: syncing
              ? 'rgba(139, 92, 246, 0.08)'
              : 'rgba(139, 92, 246, 0.1)',
            color: '#a78bfa',
            cursor: syncing ? 'wait' : 'pointer',
            opacity: syncing ? 0.7 : 1,
            transition: 'all 0.15s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            fontFamily: 'inherit',
          }}
        >
          {syncing ? (
            <>
              <span style={{
                display: 'inline-block',
                width: '14px',
                height: '14px',
                border: '2px solid rgba(167, 139, 250, 0.3)',
                borderTopColor: '#a78bfa',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
              }} />
              Synchronizing...
            </>
          ) : (
            <>
              <span style={{ fontSize: '14px' }}>⟳</span>
              Sync ClickUp
            </>
          )}
        </button>

        {menuOpen && (
          <div style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            right: 0,
            marginBottom: '4px',
            background: '#1a1a28',
            border: '1px solid #2a2a3d',
            borderRadius: '10px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
            overflow: 'hidden',
            zIndex: 50,
          }}>
            {loadingWs ? (
              <div style={{ padding: '12px 14px', fontSize: '13px', color: '#6868880', textAlign: 'center' }}>
                Loading...
              </div>
            ) : wsError ? (
              <div style={{ padding: '12px 14px', fontSize: '13px', color: '#f87171', textAlign: 'center' }}>
                Backend unavailable
              </div>
            ) : (
              <>
                <button
                  onClick={() => handleSync()}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    fontSize: '13px',
                    textAlign: 'left',
                    color: '#e8e8f0',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#222235')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  ⟳ Sync all workspaces
                </button>
                <div style={{ borderTop: '1px solid #2a2a3d' }} />
                <button
                  onClick={handleCleanup}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    fontSize: '13px',
                    textAlign: 'left',
                    color: '#f87171',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#222235')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  🧹 Cleanup + full import
                </button>
                {workspaces.length > 0 && <div style={{ borderTop: '1px solid #2a2a3d' }} />}
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => handleSync(ws.id)}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      fontSize: '13px',
                      textAlign: 'left',
                      color: '#9898b0',
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#222235'
                      e.currentTarget.style.color = '#e8e8f0'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent'
                      e.currentTarget.style.color = '#9898b0'
                    }}
                  >
                    🏢 {ws.name}
                  </button>
                ))}
              </>
            )}
          </div>
        )}

        {lastResult && (
          <div style={{
            marginTop: '8px',
            padding: '8px 12px',
            borderRadius: '8px',
            fontSize: '11px',
            fontWeight: 500,
            ...(lastResult.errors === -1
              ? { background: 'rgba(239, 68, 68, 0.1)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.15)' }
              : lastResult.errors > 0
                ? { background: 'rgba(234, 179, 8, 0.1)', color: '#fbbf24', border: '1px solid rgba(234, 179, 8, 0.15)' }
                : { background: 'rgba(34, 197, 94, 0.1)', color: '#4ade80', border: '1px solid rgba(34, 197, 94, 0.15)' }),
          }}>
            {lastResult.errors === -1 ? (
              'Sync failed — check backend logs'
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

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </aside>
  )
}
