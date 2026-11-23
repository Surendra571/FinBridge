import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { HealthPage } from './pages/HealthPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { VerifyEmailPage } from './pages/VerifyEmailPage';
import { ProfilePage } from './pages/ProfilePage';
import { OrganizationSettingsPage } from './pages/OrganizationSettingsPage';
import { StatementsPage } from './pages/StatementsPage';
import { LedgerPage } from './pages/LedgerPage';
import { ReconciliationPage } from './pages/ReconciliationPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { AuditPage } from './pages/AuditPage';
import { FailureSimulatorPage } from './pages/FailureSimulatorPage';
import { ReportsPage } from './pages/ReportsPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        {/* Auth routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />

        {/* Protected workspace routes */}
        <Route path="/" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="statements" element={<StatementsPage />} />
          <Route path="ledger" element={<LedgerPage />} />
          <Route path="settings" element={<OrganizationSettingsPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="health" element={<HealthPage />} />

          {/* Placeholders for subsequent phases */}
          <Route path="reconciliation" element={<ReconciliationPage />} />
          <Route path="reviews" element={<ReviewQueuePage />} />
          <Route path="transactions" element={<StatementsPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="integrations" element={<FailureSimulatorPage />} />
          <Route path="simulator" element={<FailureSimulatorPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
