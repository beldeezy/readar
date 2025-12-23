import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import AuthCallbackPage from './pages/AuthCallbackPage';
import OnboardingPage from './pages/OnboardingPage';
import RecommendationsPage from './pages/RecommendationsPage';
import RecommendationsLoadingPage from './pages/RecommendationsLoadingPage';
import BookDetailPage from './pages/BookDetailPage';
import UpgradePage from './pages/UpgradePage';
import ProfilePage from './pages/ProfilePage';
import AdminLayout from './pages/admin/AdminLayout';
import Books from './pages/admin/Books';
import Users from './pages/admin/Users';
import Engine from './pages/admin/Engine';
import InsightReview from './pages/admin/InsightReview';
import RecommendationsDebug from './pages/admin/RecommendationsDebug';
import EnvCheckPage from './pages/EnvCheckPage';
import Header from './components/Header';
import ScrollToTop from './components/ScrollToTop';
import BackendHealthGate from './components/BackendHealthGate';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading, onboardingComplete, onboardingChecked } = useAuth();
  const location = useLocation();
  
  // Debug log
  console.log("[route] authed=", isAuthenticated, "onboarded=", onboardingComplete, "checked=", onboardingChecked, "path=", location.pathname);
  
  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        minHeight: '50vh' 
      }}>
        Loading...
      </div>
    );
  }
  
  // Public routes that don't require authentication
  const publicRoutes = ['/', '/onboarding', '/recommendations/loading', '/login', '/auth/callback'];
  const isPublicRoute = publicRoutes.includes(location.pathname);
  
  // If it's a public route, allow access
  if (isPublicRoute) {
    // But if user is already onboarded and trying to access onboarding, redirect away
    if (isAuthenticated && onboardingComplete === true && location.pathname.startsWith('/onboarding')) {
      return <Navigate to="/recommendations" replace />;
    }
    return <>{children}</>;
  }
  
  // For protected routes:
  // 1. If not logged in → /login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // 2. If logged in and onboarding not complete → force /onboarding
  // (except if already on /onboarding to avoid redirect loop)
  // Only force onboarding if we definitively checked and found it missing
  if (onboardingChecked && onboardingComplete === false && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }
  
  // 3. If logged in and onboarding complete → allow access
  // (onboardingComplete === true or null while checking)
  
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route path="/env" element={<EnvCheckPage />} />
      <Route
        path="/onboarding"
        element={<OnboardingPage />}
      />
      <Route
        path="/recommendations/loading"
        element={<RecommendationsLoadingPage />}
      />
      <Route
        path="/recommendations"
        element={
          <ProtectedRoute>
            <RecommendationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/book/:id"
        element={
          <ProtectedRoute>
            <BookDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/upgrade"
        element={
          <ProtectedRoute>
            <UpgradePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route path="/admin" element={<AdminLayout />}>
        <Route path="books" element={<Books />} />
        <Route path="users" element={<Users />} />
        <Route path="engine" element={<Engine />}>
          <Route path="insight-review" element={<InsightReview />} />
        </Route>
        <Route path="recommendations-debug" element={<RecommendationsDebug />} />
        <Route index element={<Navigate to="/admin/books" replace />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <ScrollToTop />
        <BackendHealthGate />
        <div className="readar-app">
          <Header />
          <main className="readar-main">
            <AppRoutes />
          </main>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;

