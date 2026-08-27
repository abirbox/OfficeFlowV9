import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import useAuthStore from '@/stores/authStore';
import { useAppSettings } from '@/contexts/AppSettingsContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LogIn, Mail, Lock } from 'lucide-react';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuthStore();
  const { settings, refresh } = useAppSettings();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    const result = await login(email, password);
    setIsLoading(false);

    if (result.success) {
      refresh();
      if (result.user?.role === 'client') {
        navigate('/client', { replace: true });
      } else {
        navigate(from, { replace: true });
      }
    } else {
      setError(result.error);
    }
  };

  const heroTitle = settings?.login_hero_title || settings?.brand_name || 'OfficeFlow';
  const heroSubtitle = settings?.login_hero_subtitle || 'Modern Office Management, HR, Attendance, GPS Tracking & Task Management Platform';
  const welcomeTitle = settings?.login_welcome_title || 'Welcome Back';
  const welcomeSubtitle = settings?.login_welcome_subtitle || `Sign in to your ${settings?.brand_name || 'OfficeFlow'} account`;

  return (
    <div className="min-h-screen flex bg-[#F8FAFC] dark:bg-[#09090B]">
      <div className="flex-1 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          <div className="bg-white dark:bg-[#18181B] rounded-xl border border-[#E2E8F0] dark:border-[#27272A] p-8 shadow-sm">
            <div className="text-center mb-8">
              {settings?.brand_logo_url ? (
                <img
                  src={settings.brand_logo_url}
                  alt="Brand"
                  data-testid="brand-logo"
                  className="w-16 h-16 mx-auto mb-4 object-contain rounded-xl"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                />
              ) : (
                <div className="inline-flex items-center justify-center w-16 h-16 bg-[#4F46E5] rounded-xl mb-4">
                  <LogIn className="w-8 h-8 text-white" />
                </div>
              )}
              <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2" data-testid="login-welcome-title">
                {welcomeTitle}
              </h1>
              <p className="text-[#64748B] dark:text-[#A1A1AA]" data-testid="login-welcome-subtitle">
                {welcomeSubtitle}
              </p>
            </div>

            {error && (
              <div
                data-testid="login-error-message"
                className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm"
              >
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-[#0F172A] dark:text-[#FAFAFA]">
                  Email Address
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#64748B] dark:text-[#A1A1AA]" />
                  <Input
                    id="email"
                    data-testid="login-email-input"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-11"
                    placeholder="you@company.com"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-[#0F172A] dark:text-[#FAFAFA]">
                  Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#64748B] dark:text-[#A1A1AA]" />
                  <Input
                    id="password"
                    data-testid="login-password-input"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-11"
                    placeholder="••••••••"
                    required
                  />
                </div>
              </div>

              <div className="flex items-center justify-end">
                <Link
                  to="/forgot-password"
                  data-testid="forgot-password-link"
                  className="text-sm text-[#4F46E5] hover:text-[#4338CA] dark:text-[#6366F1] dark:hover:text-[#818CF8] transition-colors"
                >
                  Forgot password?
                </Link>
              </div>

              <Button
                type="submit"
                data-testid="login-submit-button"
                disabled={isLoading}
                className="w-full bg-[#4F46E5] hover:bg-[#4338CA] text-white h-11 rounded-lg transition-colors"
              >
                {isLoading ? 'Signing in...' : 'Sign In'}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">
                Contact your administrator to get an account
              </p>
            </div>
          </div>
        </motion.div>
      </div>

      <div className="hidden lg:flex flex-1 bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] items-center justify-center p-12">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6 }}
          className="text-white text-center max-w-lg"
        >
          {settings?.brand_logo_url && (
            <img
              src={settings.brand_logo_url}
              alt={settings?.brand_name || 'Brand'}
              data-testid="login-hero-logo"
              className="w-32 h-32 md:w-40 md:h-40 mx-auto mb-8 object-contain"
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
          )}

          <h2 className="text-5xl font-bold mb-6 tracking-tight" data-testid="login-hero-title">
            {heroTitle}
          </h2>

          <p className="text-xl text-indigo-100 leading-relaxed" data-testid="login-hero-subtitle">
            {heroSubtitle}
          </p>
        </motion.div>
      </div>
    </div>
  );
};

export default Login;
