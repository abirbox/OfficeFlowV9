import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import useAuthStore from '@/stores/authStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { UserPlus, Mail, Lock, User } from 'lucide-react';

const Register = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { register } = useAuthStore();
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setIsLoading(true);
    const result = await register({
      name: formData.name,
      email: formData.email,
      password: formData.password,
      role: 'employee',
    });
    setIsLoading(false);

    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.error);
    }
  };

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
              <div className="inline-flex items-center justify-center w-16 h-16 bg-[#4F46E5] rounded-xl mb-4">
                <UserPlus className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
                Create Account
              </h1>
              <p className="text-[#64748B] dark:text-[#A1A1AA]">
                Join OfficeFlow today
              </p>
            </div>

            {error && (
              <div
                data-testid="register-error-message"
                className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm"
              >
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="name" className="text-[#0F172A] dark:text-[#FAFAFA]">
                  Full Name
                </Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#64748B] dark:text-[#A1A1AA]" />
                  <Input
                    id="name"
                    name="name"
                    data-testid="register-name-input"
                    type="text"
                    value={formData.name}
                    onChange={handleChange}
                    className="pl-11"
                    placeholder="John Doe"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email" className="text-[#0F172A] dark:text-[#FAFAFA]">
                  Email Address
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#64748B] dark:text-[#A1A1AA]" />
                  <Input
                    id="email"
                    name="email"
                    data-testid="register-email-input"
                    type="email"
                    value={formData.email}
                    onChange={handleChange}
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
                    name="password"
                    data-testid="register-password-input"
                    type="password"
                    value={formData.password}
                    onChange={handleChange}
                    className="pl-11"
                    placeholder="••••••••"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="text-[#0F172A] dark:text-[#FAFAFA]">
                  Confirm Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#64748B] dark:text-[#A1A1AA]" />
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    data-testid="register-confirm-password-input"
                    type="password"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    className="pl-11"
                    placeholder="••••••••"
                    required
                  />
                </div>
              </div>

              <Button
                type="submit"
                data-testid="register-submit-button"
                disabled={isLoading}
                className="w-full bg-[#4F46E5] hover:bg-[#4338CA] text-white h-11 rounded-lg transition-colors"
              >
                {isLoading ? 'Creating account...' : 'Create Account'}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">
                Already have an account?{' '}
                <Link
                  to="/login"
                  data-testid="login-link"
                  className="text-[#4F46E5] hover:text-[#4338CA] dark:text-[#6366F1] dark:hover:text-[#818CF8] font-medium transition-colors"
                >
                  Sign in
                </Link>
              </p>
            </div>
          </div>
        </motion.div>
      </div>

      <div className="hidden lg:flex flex-1 bg-gradient-to-br from-[#7C3AED] to-[#4F46E5] items-center justify-center p-12">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6 }}
          className="text-white text-center max-w-lg"
        >
          <h2 className="text-5xl font-bold mb-6 tracking-tight">Join OfficeFlow</h2>
          <p className="text-xl text-purple-100 leading-relaxed">
            Streamline your office operations with our comprehensive management platform
          </p>
        </motion.div>
      </div>
    </div>
  );
};

export default Register;