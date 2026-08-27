import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import useAuthStore from '@/stores/authStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Mail, ArrowLeft } from 'lucide-react';

const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const { forgotPassword } = useAuthStore();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    const result = await forgotPassword(email);
    setIsLoading(false);

    if (result.success) {
      setSuccess(true);
    } else {
      setError(result.error);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC] dark:bg-[#09090B] p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full max-w-md"
        >
          <div className="bg-white dark:bg-[#18181B] rounded-xl border border-[#E2E8F0] dark:border-[#27272A] p-8 shadow-sm text-center">
            <div className="w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
              <Mail className="w-8 h-8 text-green-600 dark:text-green-400" />
            </div>
            <h2 className="text-2xl font-bold text-[#0F172A] dark:text-[#FAFAFA] mb-2">Check Your Email</h2>
            <p className="text-[#64748B] dark:text-[#A1A1AA] mb-6">
              If an account exists with {email}, you will receive a password reset link.
            </p>
            <Link to="/login">
              <Button className="w-full" data-testid="back-to-login-button">
                Back to Login
              </Button>
            </Link>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F8FAFC] dark:bg-[#09090B] p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="bg-white dark:bg-[#18181B] rounded-xl border border-[#E2E8F0] dark:border-[#27272A] p-8 shadow-sm">
          <div className="mb-8">
            <Link
              to="/login"
              className="inline-flex items-center text-sm text-[#4F46E5] hover:text-[#4338CA] dark:text-[#6366F1] dark:hover:text-[#818CF8] mb-6"
              data-testid="back-link"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to login
            </Link>
            <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
              Forgot Password?
            </h1>
            <p className="text-[#64748B] dark:text-[#A1A1AA]">
              Enter your email and we'll send you a reset link
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400 text-sm">
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
                  data-testid="forgot-password-email-input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-11"
                  placeholder="you@company.com"
                  required
                />
              </div>
            </div>

            <Button
              type="submit"
              data-testid="forgot-password-submit-button"
              disabled={isLoading}
              className="w-full bg-[#4F46E5] hover:bg-[#4338CA] text-white h-11 rounded-lg transition-colors"
            >
              {isLoading ? 'Sending...' : 'Send Reset Link'}
            </Button>
          </form>
        </div>
      </motion.div>
    </div>
  );
};

export default ForgotPassword;