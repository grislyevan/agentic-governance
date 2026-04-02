import { useState } from 'react';
import SectionTabBar from '../components/ui/SectionTabBar';
import EventsPage from './EventsPage';
import SessionsPage from './SessionsPage';

export default function DetectionsPage(props) {
  const [activeTab, setActiveTab] = useState('events');

  const tabs = [
    { key: 'events', label: 'Events' },
    { key: 'sessions', label: 'Sessions' },
  ];

  return (
    <div className="space-y-4 min-w-0">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-detec-ink-primary tracking-tight">Detections</h1>
      </div>
      <SectionTabBar tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      {activeTab === 'events' && <EventsPage {...props} embedded />}
      {activeTab === 'sessions' && <SessionsPage {...props} embedded />}
    </div>
  );
}
