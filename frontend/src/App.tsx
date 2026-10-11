import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { ToastProvider } from './lib/toast'
import Overview from './pages/Overview'
import FeedbackExplorer from './pages/FeedbackExplorer'
import Insights from './pages/Insights'
import Recommendations from './pages/Recommendations'
import IssueTracker from './pages/IssueTracker'
import Reports from './pages/Reports'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <ToastProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/feedback" element={<FeedbackExplorer />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/issues" element={<IssueTracker />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Layout>
    </ToastProvider>
  )
}
