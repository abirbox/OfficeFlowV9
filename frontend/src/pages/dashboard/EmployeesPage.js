import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Plus, Users, Search, Filter, Pencil, Trash2 } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/components/ui/sonner';
import AddEmployeeDialog from '@/components/AddEmployeeDialog';
import EditEmployeeDialog from '@/components/EditEmployeeDialog';
import { usePresence } from '@/contexts/PresenceContext';

const EmployeesPage = () => {
  const navigate = useNavigate();
  const { isOnline } = usePresence();
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const [editEmp, setEditEmp] = useState(null);

  useEffect(() => {
    fetchEmployees();
  }, []);

  const fetchEmployees = async () => {
    try {
      const { data } = await api.get('/employees');
      setEmployees(data);
    } catch (error) {
      toast.error('Failed to load employees');
    } finally {
      setLoading(false);
    }
  };

  const filteredEmployees = employees.filter(
    (emp) =>
      emp.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      emp.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const deleteEmployee = async (emp) => {
    if (!window.confirm(`Permanently delete "${emp.name}"? Attendance, shifts, leaves and overtime for this employee will also be removed. This cannot be undone.`)) return;
    try {
      await api.delete(`/employees/${emp.id}`);
      toast.success('Employee deleted');
      fetchEmployees();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete employee');
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
    <div data-testid="employees-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
            Employees
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
            Manage your workforce
          </p>
        </div>
        <Button
          data-testid="add-employee-button"
          onClick={() => setAddOpen(true)}
          className="bg-[#4F46E5] hover:bg-[#4338CA]"
        >
          <Plus className="w-5 h-5 mr-2" />
          Add Employee
        </Button>
      </div>

      <div className="flex gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#64748B] dark:text-[#A1A1AA]" />
          <Input
            data-testid="employee-search-input"
            placeholder="Search employees..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-11"
          />
        </div>
        <Button variant="outline" data-testid="filter-button">
          <Filter className="w-5 h-5 mr-2" />
          Filter
        </Button>
      </div>

      {filteredEmployees.length === 0 ? (
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardContent className="p-12 text-center">
            <Users className="w-16 h-16 text-[#64748B] dark:text-[#A1A1AA] mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-[#0F172A] dark:text-[#FAFAFA] mb-2">
              {searchQuery ? 'No employees found' : 'No employees yet'}
            </h3>
            <p className="text-[#64748B] dark:text-[#A1A1AA] mb-6">
              {searchQuery ? 'Try a different search' : 'Add your first employee to get started'}
            </p>
            {!searchQuery && (
              <Button onClick={() => setAddOpen(true)} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="add-employee-empty-button">
                <Plus className="w-5 h-5 mr-2" />
                Add Employee
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-[#F8FAFC] dark:bg-[#18181B] border-b border-[#E2E8F0] dark:border-[#27272A]">
                  <tr>
                    <th className="text-left p-4 text-sm font-medium text-[#64748B] dark:text-[#A1A1AA]">
                      Employee
                    </th>
                    <th className="text-left p-4 text-sm font-medium text-[#64748B] dark:text-[#A1A1AA]">
                      Department
                    </th>
                    <th className="text-left p-4 text-sm font-medium text-[#64748B] dark:text-[#A1A1AA]">
                      Role
                    </th>
                    <th className="text-left p-4 text-sm font-medium text-[#64748B] dark:text-[#A1A1AA]">
                      Status
                    </th>
                    <th className="text-right p-4 text-sm font-medium text-[#64748B] dark:text-[#A1A1AA]">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEmployees.map((employee, index) => (
                    <motion.tr
                      key={employee.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: index * 0.05 }}
                      className="border-b border-[#E2E8F0] dark:border-[#27272A] hover:bg-[#F8FAFC] dark:hover:bg-[#27272A] transition-colors"
                      data-testid={`employee-row-${index}`}
                    >
                      <td className="p-4 cursor-pointer" onClick={() => navigate(`/dashboard/employees/${employee.id}`)}>
                        <div className="flex items-center gap-3">
                          <div className="relative">
                            <Avatar>
                              <AvatarImage src={employee.avatar_path} />
                              <AvatarFallback className="bg-[#4F46E5] text-white">
                                {employee.name.charAt(0).toUpperCase()}
                              </AvatarFallback>
                            </Avatar>
                            <span
                              data-testid={`presence-dot-${employee.id}`}
                              title={isOnline(employee.id) ? 'Online' : 'Offline'}
                              className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white dark:border-[#18181B] ${isOnline(employee.id) ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'}`}
                            />
                          </div>
                          <div>
                            <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA] flex items-center gap-2">
                              {employee.name}
                              {isOnline(employee.id) && <span className="text-[10px] font-medium text-green-600">● Online</span>}
                            </p>
                            <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">
                              {employee.email}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className="text-sm text-[#0F172A] dark:text-[#FAFAFA]">
                          {employee.department_name || '-'}
                        </span>
                      </td>
                      <td className="p-4">
                        <Badge
                          variant="secondary"
                          className="bg-[#F1F5F9] dark:bg-[#27272A] text-[#0F172A] dark:text-[#FAFAFA]"
                        >
                          {employee.role}
                        </Badge>
                      </td>
                      <td className="p-4">
                        <Badge
                          variant={employee.status === 'active' ? 'success' : 'secondary'}
                          className={`${
                            employee.status === 'active'
                              ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                              : employee.status === 'suspended'
                              ? 'bg-orange-100 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400'
                              : 'bg-gray-100 dark:bg-gray-900/20 text-gray-700 dark:text-gray-400'
                          }`}
                        >
                          {employee.status}
                        </Badge>
                      </td>
                      <td className="p-4 text-right space-x-2">
                        <Button size="sm" variant="outline" onClick={() => setEditEmp(employee)} data-testid={`edit-employee-${employee.id}`}>
                          <Pencil className="w-4 h-4 mr-1" /> Edit
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => deleteEmployee(employee)} data-testid={`delete-employee-${employee.id}`} className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/20">
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      <AddEmployeeDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onCreated={() => fetchEmployees()}
      />
      <EditEmployeeDialog
        open={!!editEmp}
        onOpenChange={(o) => !o && setEditEmp(null)}
        employee={editEmp}
        onChanged={() => fetchEmployees()}
      />
    </div>
  );
};

export default EmployeesPage;