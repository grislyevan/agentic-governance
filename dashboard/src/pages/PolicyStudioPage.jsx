/**
 * Full-page Policy Studio at /policies/new. Layout: header, stepper, main + right rail, sticky footer.
 */
import { useNavigate } from 'react-router-dom';
import PolicyStudio from '../components/policy-studio/PolicyStudio';

export default function PolicyStudioPage() {
  const navigate = useNavigate();

  const handleClose = () => navigate('/policies');
  const handleSaved = () => navigate('/policies');

  return (
    <div className="flex flex-col min-h-0">
      <PolicyStudio
        asPage
        onClose={handleClose}
        onSaved={handleSaved}
      />
    </div>
  );
}
