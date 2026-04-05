import { useState, useCallback, useRef, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import useAuth from './hooks/useAuth';
import IconRail from './components/layout/IconRail';
import TopBar from './components/layout/TopBar';
import AdminLayout from './components/layout/AdminLayout';
import ApertureSpinner from './components/branding/ApertureSpinner';
import LoginPage from './pages/LoginPage';
import SetPasswordPage from './pages/SetPasswordPage';
import SsoCallbackPage from './pages/SsoCallbackPage';
import DashboardPage from './pages/DashboardPage';
import DetectionsPage from './pages/DetectionsPage';
import EventsPage from './pages/EventsPage';
import SessionsPage from './pages/SessionsPage';
import SessionDetailPage from './pages/SessionDetailPage';
import PoliciesPage from './pages/PoliciesPage';
import PolicyStudioPage from './pages/PolicyStudioPage';
import EndpointsPageWrapper from './pages/EndpointsPageWrapper';
import AuditLogPage from './pages/AuditLogPage';
import ApprovalsPage from './pages/ApprovalsPage';
import AdminPage from './pages/AdminPage';
import AdminSsoPage from './pages/AdminSsoPage';
import AdminServerPage from './pages/AdminServerPage';
import SettingsPage from './pages/SettingsPage';
import ExceptionsPage from './pages/ExceptionsPage';
import BehaviorsPage from './pages/BehaviorsPage';

/**
 * Map pathname prefixes → icon rail active section.
 * Order matters: more specific prefixes first.
 */
function resolveActivePage(pathname) {
  if (pathname === '/') return 'overview';
  if (pathname.startsWith('/detections') || pathname.startsWith('/events') || pathname.startsWith('/sessions')) return 'detections';
  if (pathname.startsWith('/policies')) return 'policies';
  if (pathname.startsWith('/approvals') || pathname.startsWith('/exceptions')) return 'approvals';
  if (pathname.startsWith('/endpoints')) return 'endpoints';
  if (pathname.startsWith('/behaviors')) return 'behaviors';
  if (pathname.startsWith('/audit')) return 'audit';
  if (pathname.startsWith('/admin') || pathname.startsWith('/settings')) return 'admin';
  return 'overview';
}

export default function App() {
  const { isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');
  const [alertCount, setAlertCount] = useState(0);
  const [railOpen, setRailOpen] = useState(false);
  const refreshRef = useRef(null);

  const activePage = resolveActivePage(location.pathname);

  const handleNavigate = useCallback((page) => {
    navigate(`/${page}`);
  }, [navigate]);

  const handleRefresh = useCallback(() => {
    refreshRef.current?.();
  }, []);

  useEffect(() => {
    setRailOpen(false);
  }, [location.pathname]);

  /* ── Keyboard shortcuts: 1-8 → section navigation ── */
  useEffect(() => {
    const SECTION_KEYS = { '1': '', '2': 'detections', '3': 'policies', '4': 'approvals', '5': 'endpoints', '6': 'behaviors', '7': 'audit', '8': 'admin' };
    function handleKeyDown(e) {
      // Skip when typing in inputs/textareas or when modifier keys are held (except for standalone digits)
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const path = SECTION_KEYS[e.key];
      if (path != null) {
        e.preventDefault();
        navigate(`/${path}`);
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [navigate]);

  if (location.pathname === '/auth/sso/callback') {
    return <SsoCallbackPage />;
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-detec-void flex flex-col items-center justify-center gap-3">
        <ApertureSpinner size="xl" label="Starting Detec" />
        <span className="text-sm text-detec-ink-secondary">Connecting...</span>
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
    <div className="flex min-h-screen bg-detec-void">
      <IconRail
        activePage={activePage}
        onNavigate={handleNavigate}
        alertCount={alertCount}
        isOpen={railOpen}
        onClose={() => setRailOpen(false)}
      />

      {/* Main content — 56px left margin for icon rail on desktop */}
      <div className="flex flex-col flex-1 min-w-0 lg:ml-14">
        <TopBar
          onNavigate={handleNavigate}
          onSearch={setSearchQuery}
          onRefresh={handleRefresh}
          alertCount={alertCount}
          onMenuClick={() => setRailOpen(true)}
        />

        <main className="flex-1 py-6 px-4 sm:px-5 lg:px-6 2xl:px-8 overflow-y-auto overflow-x-hidden max-w-[1800px] mx-auto w-full">
          <Routes>
            {/* Overview (default landing) */}
            <Route path="/" element={<DashboardPage {...pageProps} />} />

            {/* Detections — events + sessions grouped */}
            <Route path="/detections" element={<DetectionsPage {...pageProps} />} />
            <Route path="/events" element={<EventsPage {...pageProps} />} />
            <Route path="/sessions" element={<SessionsPage {...pageProps} />} />
            <Route path="/sessions/:id" element={<SessionDetailPage {...pageProps} />} />

            {/* Policies */}
            <Route path="/policies" element={<PoliciesPage {...pageProps} />} />
            <Route path="/policies/new" element={<PolicyStudioPage />} />
            <Route path="/policies/:id/edit" element={<PolicyStudioPage />} />

            {/* Approvals + Exceptions grouped */}
            <Route path="/approvals" element={<ApprovalsPage {...pageProps} />} />
            <Route path="/exceptions" element={<ExceptionsPage {...pageProps} />} />

            {/* Endpoints */}
            <Route path="/endpoints" element={<EndpointsPageWrapper {...pageProps} />} />

            {/* Behaviors */}
            <Route path="/behaviors" element={<BehaviorsPage {...pageProps} />} />

            {/* Audit */}
            <Route path="/audit" element={<AuditLogPage {...pageProps} />} />

            {/* Admin — consolidated */}
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminPage {...pageProps} />} />
              <Route path="sso" element={<AdminSsoPage />} />
              <Route path="server" element={<AdminServerPage />} />
            </Route>
            <Route path="/settings" element={<SettingsPage {...pageProps} />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
