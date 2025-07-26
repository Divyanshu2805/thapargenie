import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { useAuth } from './auth/AuthContext';
import AppShell from './components/layout/AppShell';
import ChatHome from './features/chat/ChatHome';
import AdminRoute from './layouts/AdminRoute';
import { authRedirectHeld } from './lib/page-slide';
import PrivateRoute from './layouts/PrivateRoute';
import AuthAction from './views/auth/AuthAction';
import AuthLoading from './views/auth/AuthLoading';
import ForgotPassword from './views/auth/ForgotPassword/ForgotPassword';
import Login from './views/auth/Login/Login';
import Logout from './views/auth/Logout/Logout';
import Register from './views/auth/Register/Register';

// Pages past the first screen load on demand, keeping the initial bundle small.
// The admin area is its own chunk, so students never download it.
const ConversationPage = lazy(() => import('./features/chat/ConversationPage'));
const SettingsPage = lazy(() => import('./features/settings/SettingsPage'));
const PrivacyPage = lazy(() => import('./features/privacy/PrivacyPage'));
const AdminLayout = lazy(() => import('./features/admin/AdminLayout'));
const OverviewPage = lazy(() => import('./features/admin/OverviewPage'));
const DocumentsPage = lazy(() => import('./features/admin/DocumentsPage'));
const DocumentDetailPage = lazy(() => import('./features/admin/DocumentDetailPage'));
const FeedbackPage = lazy(() => import('./features/admin/FeedbackPage'));
const GapsPage = lazy(() => import('./features/admin/GapsPage'));
const UsersPage = lazy(() => import('./features/admin/UsersPage'));
const AuditLogPage = lazy(() => import('./features/admin/AuditLogPage'));

function SignedOutRoute({ children }) {
  const { initialized, user } = useAuth();
  if (!initialized) return <AuthLoading />;
  // While a sign-in is sliding the user into the app, the sign-in page stays put.
  return user && !authRedirectHeld() ? <Navigate replace to="/chat/" /> : children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/chat/" replace />} />
        <Route path="/register/" element={<SignedOutRoute><Register /></SignedOutRoute>} />
        <Route path="/login/" element={<SignedOutRoute><Login /></SignedOutRoute>} />
        <Route path="/logout/" element={<Logout />} />
        <Route path="/forgot-password/" element={<ForgotPassword />} />
        <Route path="/auth/action" element={<AuthAction />} />
        <Route path="/create-new-password/" element={<Navigate to="/forgot-password/" replace />} />
        <Route path="/verify-email/" element={<Navigate to="/chat/" replace />} />
        <Route path="/privacy" element={<Suspense fallback={<AuthLoading message="Loading…" />}><PrivacyPage /></Suspense>} />

        <Route element={<PrivateRoute><AppShell /></PrivateRoute>}>
          <Route path="/chat/" element={<ChatHome />} />
          <Route path="/chat/:conversationId" element={<ConversationPage />} />
          <Route path="/settings/" element={<SettingsPage />} />
        </Route>

        <Route
          path="/admin/"
          element={
            <AdminRoute>
              <Suspense fallback={<AuthLoading message="Loading the dashboard…" />}>
                <AdminLayout />
              </Suspense>
            </AdminRoute>
          }
        >
          <Route index element={<OverviewPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="documents/:documentId" element={<DocumentDetailPage />} />
          <Route path="feedback" element={<FeedbackPage />} />
          <Route path="gaps" element={<GapsPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="audit-log" element={<AuditLogPage />} />
          <Route path="*" element={<Navigate to="/admin/" replace />} />
        </Route>

        <Route path="*" element={<Navigate to="/chat/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
