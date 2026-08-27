import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { api } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Building2, Users, MapPin, Briefcase } from 'lucide-react';
import { toast } from '@/components/ui/sonner';

const CompaniesPage = () => {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCompanies();
  }, []);

  const fetchCompanies = async () => {
    try {
      const { data } = await api.get('/companies');
      setCompanies(data);
    } catch (error) {
      toast.error('Failed to load companies');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div data-testid="companies-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
            Companies
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
            Manage your organization structure
          </p>
        </div>
        <Button
          data-testid="add-company-button"
          className="bg-[#4F46E5] hover:bg-[#4338CA]"
        >
          <Plus className="w-5 h-5 mr-2" />
          Add Company
        </Button>
      </div>

      {companies.length === 0 ? (
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardContent className="p-12 text-center">
            <Building2 className="w-16 h-16 text-[#64748B] dark:text-[#A1A1AA] mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-[#0F172A] dark:text-[#FAFAFA] mb-2">
              No companies yet
            </h3>
            <p className="text-[#64748B] dark:text-[#A1A1AA] mb-6">
              Create your first company to get started
            </p>
            <Button className="bg-[#4F46E5] hover:bg-[#4338CA]">
              <Plus className="w-5 h-5 mr-2" />
              Add Company
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {companies.map((company, index) => (
            <motion.div
              key={company.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card
                className="border-[#E2E8F0] dark:border-[#27272A] hover:shadow-lg transition-shadow cursor-pointer"
                data-testid={`company-card-${index}`}
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="w-12 h-12 bg-[#4F46E5] rounded-xl flex items-center justify-center">
                      <Building2 className="w-6 h-6 text-white" />
                    </div>
                  </div>
                  <CardTitle className="text-xl mt-4">{company.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {company.address && (
                      <div className="flex items-center gap-2 text-sm text-[#64748B] dark:text-[#A1A1AA]">
                        <MapPin className="w-4 h-4" />
                        {company.address}
                      </div>
                    )}
                    {company.industry && (
                      <div className="flex items-center gap-2 text-sm text-[#64748B] dark:text-[#A1A1AA]">
                        <Briefcase className="w-4 h-4" />
                        {company.industry}
                      </div>
                    )}
                    <div className="flex items-center gap-2 text-sm">
                      <Users className="w-4 h-4 text-[#4F46E5]" />
                      <span className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">
                        {company.employee_count || 0} Employees
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CompaniesPage;