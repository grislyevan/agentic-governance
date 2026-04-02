/**
 * Full-page Policy Studio at /policies/new (create) and /policies/:id/edit (edit).
 * In edit mode, reads the policy object from router location state.
 */
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import PolicyStudio from '../components/policy-studio/PolicyStudio';

export default function PolicyStudioPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams();

  // Policy object passed via navigate(..., { state: { policy } }) from PoliciesPage
  const initialPolicy = id ? (location.state?.policy ?? null) : null;

  const handleClose = () => navigate('/policies');
  const handleSaved = () => navigate('/policies');

  // If editing but no policy in state (e.g. direct URL access), redirect to list
  if (id && !initialPolicy) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <p className="text-sm text-detec-ink-secondary mb-4">
          Policy data not available. Please navigate from the Policies page.
        </p>
        <button
          type="button"
          onClick={() => navigate('/policies')}
          className="h-10 px-4 rounded-detec bg-detec-brand text-sm font-medium text-white hover:bg-detec-brandHover"
        >
          Go to Policies
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-0">
      <PolicyStudio
        key={id || 'new'}
        asPage
        initialPolicy={initialPolicy}
        onClose={handleClose}
        onSaved={handleSaved}
      />
    </div>
  );
}
