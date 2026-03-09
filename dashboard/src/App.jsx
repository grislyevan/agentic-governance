import { useState, useCallback, useRef } from 'react';
import useAuth from './hooks/useAuth';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import ApertureSpinner from './components/branding/ApertureSpinner';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import EventsPage from './pages/EventsPage';
import PoliciesPage from './pages/PoliciesPage';
import AuditLogPage from './pages/AuditLogPage';
import AdminPage from './pages/AdminPage';
import SettingsPage from './pages/SettingsPage';

const PAGES = {
  endpoints: DashboardPage,
  events: EventsPage,
  policies: PoliciesPage,
  audit: AuditLogPage,
  admin: AdminPage,
  settings: SettingsPage,
};

export default function App() {
  const { isAuthenticated, loading } = useAuth();
  const [activePage, setActivePage] = useState('endpoints');
  const [searchQuery, setSearchQuery] = useState('');
  const [alertCount, setAlertCount] = useState(0);
  const refreshRef = useRef(null);

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

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const PageComponent = PAGES[activePage] || DashboardPage;

  return (
    <div className="flex min-h-screen bg-detec-slate-900">
      <Sidebar activePage={activePage} onNavigate={setActivePage} alertCount={alertCount} />

      <div className="flex flex-col flex-1 ml-60">
        <TopBar
          activePage={activePage}
          onNavigate={setActivePage}
          onSearch={setSearchQuery}
          onRefresh={handleRefresh}
          alertCount={alertCount}
        />

        <main className="flex-1 p-6 overflow-y-auto">
          <PageComponent
            onNavigate={setActivePage}
            searchQuery={searchQuery}
            refreshRef={refreshRef}
            onAlertCountChange={setAlertCount}
          />
        </main>
      </div>
    </div>
  );
}
