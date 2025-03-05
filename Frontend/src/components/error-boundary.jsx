import { AlertTriangle, RotateCcw } from 'lucide-react';
import { Component } from 'react';

import { Button } from '@/components/ui/button';
import { isChunkLoadError, reloadForNewVersion, reportError } from '@/lib/error-reporting';

/**
 * Catches rendering errors so one broken screen never leaves a blank page.
 * A failed chunk load (the app was updated while open) reloads once instead.
 */
export class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    if (isChunkLoadError(error) && reloadForNewVersion(error)) return;
    reportError(error, 'render');
  }

  reset = () => this.setState({ error: null });

  render() {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback) return this.props.fallback({ error: this.state.error, reset: this.reset });
    const updated = isChunkLoadError(this.state.error);
    return (
      <div role="alert" className="flex min-h-[60dvh] flex-col items-center justify-center px-6 py-16 text-center">
        <span className="flex size-12 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
          <AlertTriangle className="size-5" aria-hidden="true" />
        </span>
        <h1 className="mt-4 text-lg font-semibold">{updated ? 'ThaparGenie was updated' : 'Something went wrong'}</h1>
        <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">
          {updated
            ? 'Reload to get the latest version.'
            : 'This screen hit an unexpected error. It has been reported. Reloading usually fixes it.'}
        </p>
        <div className="mt-6 flex gap-2">
          <Button onClick={() => window.location.reload()}>
            <RotateCcw /> Reload
          </Button>
          {!updated ? (
            <Button variant="outline" onClick={() => window.location.assign('/chat/')}>
              Go to chat
            </Button>
          ) : null}
        </div>
      </div>
    );
  }
}
