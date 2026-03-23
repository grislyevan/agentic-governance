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
import SessionsPage from './pages/SessionsPage';
import SessionDetailPage from './pages/SessionDetailPage';
import PoliciesPage from './pages/PoliciesPage';
import PolicyStudioPage from './pages/PolicyStudioPage';
import PlaybooksPage from './pages/PlaybooksPage';
import EndpointProfilesPage from './pages/EndpointProfilesPage';
import AuditLogPage from './pages/AuditLogPage';
import AdminPage from './pages/AdminPage';
import AdminSsoPage from './pages/AdminSsoPage';
import AdminServerPage from './pages/AdminServerPage';
import SettingsPage from './pages/SettingsPage';
import BillingPage from './pages/BillingPage';
import OrgPage from './pages/OrgPage';
import DemoBanner from './components/layout/DemoBanner';

const PATH_TO_PAGE = {
  '/endpoints': 'endpoints',
  '/sessions': 'sessions',
  '/events': 'events',
  '/policies': 'policies',
  '/playbooks': 'admin',
  '/endpoint-profiles': 'admin',
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('detec_sidebar_collapsed') === '1';
    } catch {
      return false;
    }
  });
  const refreshRef = useRef(null);

  const toggleSidebarCollapsed = useCallback(() => {
    setSidebarCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem('detec_sidebar_collapsed', next ? '1' : '0');
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const activePage = location.pathname.startsWith('/sessions')
    ? 'sessions'
    : location.pathname.startsWith('/policies')
      ? 'policies'
      : location.pathname.startsWith('/admin') ||
          location.pathname === '/playbooks' ||
          location.pathname === '/endpoint-profiles'
        ? 'admin'
        : PATH_TO_PAGE[location.pathname] || 'endpoints';

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
      <div className="min-h-screen bg-detec-ui-page flex flex-col items-center justify-center gap-3">
        <ApertureSpinner size="xl" label="Starting Detec" />
        <span className="text-sm text-detec-ui-muted">Connecting...</span>
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
    <div className="flex min-h-screen bg-detec-ui-page">
      <Sidebar
        activePage={activePage}
        onNavigate={handleNavigate}
        alertCount={alertCount}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        collapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebarCollapsed}
      />

      <div
        className={`flex flex-col flex-1 min-w-0 transition-[margin] duration-200 ease-out ${
          sidebarCollapsed ? 'lg:ml-16' : 'lg:ml-60'
        }`}
      >
        <DemoBanner />
        <TopBar
          activePage={activePage}
          onNavigate={handleNavigate}
          onSearch={setSearchQuery}
          onRefresh={handleRefresh}
          alertCount={alertCount}
          onMenuClick={() => setSidebarOpen(true)}
        />

        <main className="flex-1 py-8 px-4 sm:px-6 lg:px-8 2xl:px-10 overflow-y-auto overflow-x-hidden max-w-[1600px] mx-auto w-full">
          <Routes>
            <Route path="/endpoints" element={<DashboardPage {...pageProps} />} />
            <Route path="/sessions" element={<SessionsPage {...pageProps} />} />
            <Route path="/sessions/:id" element={<SessionDetailPage {...pageProps} />} />
            <Route path="/events" element={<EventsPage {...pageProps} />} />
            <Route path="/policies" element={<PoliciesPage {...pageProps} />} />
            <Route path="/policies/new" element={<PolicyStudioPage />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminPage {...pageProps} />} />
              <Route path="sso" element={<AdminSsoPage />} />
              <Route path="server" element={<AdminServerPage />} />
            </Route>
            <Route path="/playbooks" element={<AdminLayout />}>
              <Route index element={<PlaybooksPage {...pageProps} />} />
            </Route>
            <Route path="/endpoint-profiles" element={<AdminLayout />}>
              <Route index element={<EndpointProfilesPage {...pageProps} />} />
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
