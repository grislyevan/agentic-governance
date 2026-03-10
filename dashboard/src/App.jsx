import { useState, useCallback, useRef } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import useAuth from './hooks/useAuth';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import ApertureSpinner from './components/branding/ApertureSpinner';
import LoginPage from './pages/LoginPage';
import SetPasswordPage from './pages/SetPasswordPage';
import DashboardPage from './pages/DashboardPage';
import EventsPage from './pages/EventsPage';
import PoliciesPage from './pages/PoliciesPage';
import AuditLogPage from './pages/AuditLogPage';
import AdminPage from './pages/AdminPage';
import SettingsPage from './pages/SettingsPage';

const PATH_TO_PAGE = {
  '/endpoints': 'endpoints',
  '/events': 'events',
  '/policies': 'policies',
  '/audit': 'audit',
  '/admin': 'admin',
  '/settings': 'settings',
};

export default function App() {
  const { isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');
  const [alertCount, setAlertCount] = useState(0);
  const refreshRef = useRef(null);

  const activePage = PATH_TO_PAGE[location.pathname] || 'endpoints';

  const handleNavigate = useCallback((page) => {
    navigate(`/${page}`);
  }, [navigate]);

  const handleRefresh = useCallback(() => {
    refreshRef.current?.();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-detec-slate-900 flex flex-col items-center justify-center gap-3">
        <ApertureSpinner size="xl" label="Starting Detec" />
        <span className="text-sm text-detec-slate-500">Connecting...</span>
      </div>
    );
  }

  if (location.pathname === '/set-password') {
    return <SetPasswordPage onComplete={() => navigate('/')} />;
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const pageProps = {
    onNavigate: handleNavigate,
    searchQuery,
    refreshRef,
    onAlertCountChange: setAlertCount,
  };

  return (
    <div className="flex min-h-screen bg-detec-slate-900">
      <Sidebar activePage={activePage} onNavigate={handleNavigate} alertCount={alertCount} />

      <div className="flex flex-col flex-1 ml-60">
        <TopBar
          activePage={activePage}
          onNavigate={handleNavigate}
          onSearch={setSearchQuery}
          onRefresh={handleRefresh}
          alertCount={alertCount}
        />

        <main className="flex-1 p-6 overflow-y-auto">
          <Routes>
            <Route path="/endpoints" element={<DashboardPage {...pageProps} />} />
            <Route path="/events" element={<EventsPage {...pageProps} />} />
            <Route path="/policies" element={<PoliciesPage {...pageProps} />} />
            <Route path="/audit" element={<AuditLogPage {...pageProps} />} />
            <Route path="/admin" element={<AdminPage {...pageProps} />} />
            <Route path="/settings" element={<SettingsPage {...pageProps} />} />
            <Route path="*" element={<Navigate to="/endpoints" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
