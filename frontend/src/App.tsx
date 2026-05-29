import { Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { UploadPage } from './pages/UploadPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { QueryPage } from './pages/QueryPage'
import { GraphPage } from './pages/GraphPage'
import { HealthPage } from './pages/HealthPage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/upload" replace />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/query/:docId?" element={<QueryPage />} />
        <Route path="/graph/:docId?" element={<GraphPage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </AppShell>
  )
}
