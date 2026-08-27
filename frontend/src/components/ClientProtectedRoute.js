import { Navigate, useLocation } from 'react-router-dom';
import useAuthStore from '@/stores/authStore';
import { useEffect } from 'react';

const ClientProtectedRoute = ({ children }) => {
  const { isAuthenticated, isLoading, user, checkAuth } = useAuthStore();
  const location = useLocation();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC] dark:bg-[#09090B]">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-[#64748B] dark:text-[#A1A1AA] font-medium">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Only clients may access the Client Portal. Everyone else goes to admin.
  if (user?.role !== 'client') {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

export default ClientProtectedRoute;
