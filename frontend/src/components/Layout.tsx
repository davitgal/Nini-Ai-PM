import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      background: '#0a0a0f',
      color: '#e8e8f0',
      fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
    }}>
      <Sidebar />
      <main style={{
        flex: 1,
        overflow: 'auto',
        padding: '28px 32px',
      }}>
        <Outlet />
      </main>
    </div>
  )
}
