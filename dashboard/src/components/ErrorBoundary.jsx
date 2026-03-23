import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-detec-ui-page text-detec-ui-text p-8">
          <div className="max-w-md text-center space-y-4">
            <h1 className="text-2xl font-semibold text-red-400">Something went wrong</h1>
            <p className="text-detec-ui-muted">
              An unexpected error occurred. Try refreshing the page.
            </p>
            <pre className="text-xs text-left bg-detec-ui-page rounded p-4 overflow-auto max-h-40 text-detec-ui-muted">
              {this.state.error?.message || 'Unknown error'}
            </pre>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-detec-teal-600 hover:bg-detec-teal-500 rounded text-sm font-medium transition-colors"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
