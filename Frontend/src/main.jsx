import { QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App.jsx';
import { AuthProvider } from './auth/AuthContext.jsx';
import { ErrorBoundary } from './components/error-boundary.jsx';
import { RecentAuthProvider } from './components/recent-auth.jsx';
import { ThemeProvider } from './components/theme-provider.jsx';
import { Toaster } from './components/ui/sonner.jsx';
import { TooltipProvider } from './components/ui/tooltip.jsx';
import { installGlobalErrorHandlers } from './lib/error-reporting.js';
import { listenForInstallPrompt } from './lib/install-prompt.js';
import { preloadLanding } from './features/landing/load.js';
import { slideOnHistoryMoves } from './lib/page-slide.js';
import { queryClient } from './lib/query-client.js';
import './index.css';

installGlobalErrorHandlers();
listenForInstallPrompt();
slideOnHistoryMoves();

// Arriving on the landing page: fetch its code and hero photo while the rest of the app boots.
if (window.location.pathname === '/') preloadLanding().catch(() => {});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <TooltipProvider>
              <RecentAuthProvider>
                <App />
              </RecentAuthProvider>
              <Toaster />
            </TooltipProvider>
          </AuthProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </ErrorBoundary>
  </StrictMode>,
);
