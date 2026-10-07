import { Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { AuthGuard } from './components/AuthGuard'
import { UploadPage } from './pages/UploadPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { QueryPage } from './pages/QueryPage'
import { GraphPage } from './pages/GraphPage'
import { HealthPage } from './pages/HealthPage'
import { CatalogPage } from './pages/CatalogPage'
import { QualityDashboard } from './pages/QualityDashboard'
import AuthCallbackPage from './pages/AuthCallbackPage'
import LoginPage from './pages/LoginPage'
import WebhookSettingsPage from './pages/WebhookSettingsPage'
import ApiKeySettingsPage from './pages/ApiKeySettingsPage'
import AuditLogPage from './pages/AuditLogPage'
import OrgSettingsPage from './pages/OrgSettingsPage'
import { NotFoundPage } from './pages/NotFoundPage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/upload" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/callback" element={<AuthCallbackPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/quality" element={<QualityDashboard />} />
        <Route path="/query/:docId?" element={<QueryPage />} />
        <Route path="/graph/:docId?" element={<GraphPage />} />
        <Route path="/webhooks" element={<AuthGuard><WebhookSettingsPage /></AuthGuard>} />
        <Route path="/api-keys" element={<AuthGuard><ApiKeySettingsPage /></AuthGuard>} />
        <Route path="/audit" element={<AuthGuard><AuditLogPage /></AuthGuard>} />
        <Route path="/settings/org" element={<AuthGuard><OrgSettingsPage /></AuthGuard>} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}
