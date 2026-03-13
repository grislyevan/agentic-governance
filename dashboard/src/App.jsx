import { useState, useCallback, useRef, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import useAuth from './hooks/useAuth';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import AdminLayout from './components/layout/AdminLayout';
import ApertureSpinner from './components/branding/ApertureSpinner';
import LoginPage from './pages/LoginPage';
import SetPasswordPage from './pages/SetPasswordPage';
import SsoCallbackPage from './pages/SsoCallbackPage';
import DashboardPage from './pages/DashboardPage';
import EventsPage from './pages/EventsPage';
import PoliciesPage from './pages/PoliciesPage';
import PlaybooksPage from './pages/PlaybooksPage';
import AuditLogPage from './pages/AuditLogPage';
import AdminPage from './pages/AdminPage';
import SettingsPage from './pages/SettingsPage';
import BillingPage from './pages/BillingPage';
import OrgPage from './pages/OrgPage';
import DemoBanner from './components/layout/DemoBanner';

const PATH_TO_PAGE = {
  '/endpoints': 'endpoints',
  '/events': 'events',
  '/policies': 'policies',
  '/playbooks': 'admin',
  '/audit': 'audit',
  '/admin': 'admin',
  '/settings': 'settings',
  '/billing': 'billing',
  '/org': 'org',
};

export default function App() {
  const { isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');
  const [alertCount, setAlertCount] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const refreshRef = useRef(null);

  const activePage = PATH_TO_PAGE[location.pathname] || 'endpoints';

  const handleNavigate = useCallback((page) => {
    navigate(`/${page}`);
  }, [navigate]);

  const handleRefresh = useCallback(() => {
    refreshRef.current?.();
  }, []);

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  if (location.pathname === '/auth/sso/callback') {
    return <SsoCallbackPage />;
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-detec-slate-900 flex flex-col items-center justify-center gap-3">
        <ApertureSpinner size="xl" label="Starting Detec" />
        <span className="text-sm text-detec-slate-500">Connecting...</span>
      </div>
    );
  }

  if (location.pathname === '/set-password' || location.pathname === '/accept-invite') {
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
      <Sidebar
        activePage={activePage}
        onNavigate={handleNavigate}
        alertCount={alertCount}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex flex-col flex-1 lg:ml-60 min-w-0">
        <DemoBanner />
        <TopBar
          activePage={activePage}
          onNavigate={handleNavigate}
          onSearch={setSearchQuery}
          onRefresh={handleRefresh}
          alertCount={alertCount}
          onMenuClick={() => setSidebarOpen(true)}
        />

        <main className="flex-1 p-4 sm:p-6 overflow-y-auto overflow-x-hidden">
          <Routes>
            <Route path="/endpoints" element={<DashboardPage {...pageProps} />} />
            <Route path="/events" element={<EventsPage {...pageProps} />} />
            <Route path="/policies" element={<PoliciesPage {...pageProps} />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminPage {...pageProps} />} />
            </Route>
            <Route path="/playbooks" element={<AdminLayout />}>
              <Route index element={<PlaybooksPage {...pageProps} />} />
            </Route>
            <Route path="/audit" element={<AuditLogPage {...pageProps} />} />
            <Route path="/settings" element={<SettingsPage {...pageProps} />} />
            <Route path="/billing" element={<BillingPage {...pageProps} />} />
            <Route path="/org" element={<OrgPage {...pageProps} />} />
            <Route path="*" element={<Navigate to="/endpoints" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
