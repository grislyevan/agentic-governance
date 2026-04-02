import { useState } from 'react';
import SectionTabBar from '../components/ui/SectionTabBar';
import DashboardPage from './DashboardPage';
import EndpointProfilesPage from './EndpointProfilesPage';

export default function EndpointsPageWrapper(props) {
  const [activeTab, setActiveTab] = useState('fleet');

  return (
    <div className="space-y-4 min-w-0">
      <h1 className="text-lg font-bold text-detec-ink-primary tracking-tight">Endpoints</h1>
      <SectionTabBar
        tabs={[
          { key: 'fleet', label: 'Fleet' },
          { key: 'profiles', label: 'Profiles' },
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
      />
      {activeTab === 'fleet' && <DashboardPage {...props} embedded />}
      {activeTab === 'profiles' && <EndpointProfilesPage {...props} embedded />}
    </div>
  );
}
