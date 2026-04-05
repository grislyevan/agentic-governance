import DashboardPage from './DashboardPage';

export default function EndpointsPageWrapper(props) {
  return (
    <div className="space-y-4 min-w-0">
      <h1 className="text-lg font-bold text-detec-ink-primary tracking-tight">Endpoints</h1>
      <DashboardPage {...props} embedded />
    </div>
  );
}
