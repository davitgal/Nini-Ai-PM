import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import WorkspaceTasks from './pages/WorkspaceTasks'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="/workspace/:name" element={<WorkspaceTasks />} />
      </Route>
    </Routes>
  )
}
