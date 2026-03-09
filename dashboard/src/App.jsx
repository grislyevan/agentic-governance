import { useState } from 'react';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
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
  const [activePage, setActivePage] = useState('endpoints');

  const PageComponent = PAGES[activePage] || DashboardPage;

  return (
    <div className="flex min-h-screen bg-detec-slate-900">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />

      <div className="flex flex-col flex-1 ml-60">
        <TopBar activePage={activePage} onNavigate={setActivePage} />

        <main className="flex-1 p-6 overflow-y-auto">
          <PageComponent />
        </main>
      </div>
    </div>
  );
}
