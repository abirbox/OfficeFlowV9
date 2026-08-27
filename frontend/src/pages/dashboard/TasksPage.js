import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Plus, FolderKanban, Calendar, MessageSquare, Building, Home } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/components/ui/sonner';
import useAuthStore from '@/stores/authStore';
import { formatDate } from '@/lib/datetime';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const columns = [
  { id: 'todo', title: 'To Do', color: 'bg-slate-500' },
  { id: 'in_progress', title: 'In Progress', color: 'bg-blue-500' },
  { id: 'review', title: 'Review', color: 'bg-yellow-500' },
  { id: 'done', title: 'Done', color: 'bg-green-500' },
];

const priorityColors = {
  low: 'bg-gray-100 dark:bg-gray-900/20 text-gray-700 dark:text-gray-400',
  medium: 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400',
  high: 'bg-orange-100 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400',
  urgent: 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400',
};

const TasksPage = () => {
  const { user } = useAuthStore();
  const [tasks, setTasks] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    priority: 'medium',
    status: 'todo',
    assigned_to: '',
    work_type: 'in_office',
    due_date: '',
  });

  const isAdmin = user && user.role !== 'employee';

  useEffect(() => {
    (async () => {
      try {
        const promises = [api.get('/tasks')];
        if (isAdmin) promises.push(api.get('/employees'));
        const results = await Promise.all(promises);
        setTasks(results[0].data);
        if (results[1]) setEmployees(results[1].data);
      } catch (error) {
        toast.error('Failed to load tasks');
      } finally {
        setLoading(false);
      }
    })();
  }, [isAdmin]);

  const handleCreateTask = async () => {
    if (!newTask.title.trim()) return toast.error('Task title is required');
    if (!newTask.assigned_to) return toast.error('Please assign to an employee');
    try {
      const payload = { ...newTask };
      if (!payload.due_date) delete payload.due_date;
      const { data } = await api.post('/tasks', payload);
      setTasks([data, ...tasks]);
      setNewTask({ title: '', description: '', priority: 'medium', status: 'todo', assigned_to: '', work_type: 'in_office', due_date: '' });
      setDialogOpen(false);
      toast.success(`Task assigned to ${data.assignee_name}!`);
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const handleStatusChange = async (taskId, newStatus) => {
    try {
      await api.put(`/tasks/${taskId}`, { status: newStatus });
      setTasks(tasks.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)));
      toast.success('Task updated');
    } catch (error) {
      toast.error('Failed to update task');
    }
  };

  const getTasksByStatus = (status) => tasks.filter((t) => t.status === status);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div data-testid="tasks-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
            {isAdmin ? 'Tasks' : 'My Tasks'}
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
            {isAdmin ? 'Assign and manage team work' : 'Tasks assigned to you'}
          </p>
        </div>
        {isAdmin && (
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button data-testid="create-task-button" className="bg-[#4F46E5] hover:bg-[#4338CA]">
                <Plus className="w-5 h-5 mr-2" />
                Assign Task
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Assign New Task</DialogTitle>
                <DialogDescription>Create a task and assign it to an employee</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Title</Label>
                  <Input
                    data-testid="task-title-input"
                    value={newTask.title}
                    onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                    placeholder="e.g. Follow up with Q4 client"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Textarea
                    data-testid="task-description-input"
                    value={newTask.description}
                    onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                    placeholder="Details of the task..."
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Assign To</Label>
                  <Select value={newTask.assigned_to} onValueChange={(v) => setNewTask({ ...newTask, assigned_to: v })}>
                    <SelectTrigger data-testid="assignee-select">
                      <SelectValue placeholder="Select an employee" />
                    </SelectTrigger>
                    <SelectContent>
                      {employees.map((emp) => (
                        <SelectItem key={emp.id} value={emp.id}>
                          {emp.name} · {emp.role}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Work Type</Label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setNewTask({ ...newTask, work_type: 'in_office' })}
                      data-testid="work-type-office"
                      className={`p-4 rounded-lg border-2 transition-all ${
                        newTask.work_type === 'in_office'
                          ? 'border-[#4F46E5] bg-[#4F46E5]/5'
                          : 'border-[#E2E8F0] dark:border-[#27272A]'
                      }`}
                    >
                      <Building className={`w-6 h-6 mx-auto mb-2 ${newTask.work_type === 'in_office' ? 'text-[#4F46E5]' : 'text-[#64748B]'}`} />
                      <p className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA]">In Office</p>
                    </button>
                    <button
                      type="button"
                      onClick={() => setNewTask({ ...newTask, work_type: 'work_from_home' })}
                      data-testid="work-type-wfh"
                      className={`p-4 rounded-lg border-2 transition-all ${
                        newTask.work_type === 'work_from_home'
                          ? 'border-[#4F46E5] bg-[#4F46E5]/5'
                          : 'border-[#E2E8F0] dark:border-[#27272A]'
                      }`}
                    >
                      <Home className={`w-6 h-6 mx-auto mb-2 ${newTask.work_type === 'work_from_home' ? 'text-[#4F46E5]' : 'text-[#64748B]'}`} />
                      <p className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA]">Work from Home</p>
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Priority</Label>
                    <Select value={newTask.priority} onValueChange={(v) => setNewTask({ ...newTask, priority: v })}>
                      <SelectTrigger data-testid="task-priority-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="low">Low</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="urgent">Urgent</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Due Date</Label>
                    <Input
                      type="date"
                      value={newTask.due_date}
                      onChange={(e) => setNewTask({ ...newTask, due_date: e.target.value })}
                    />
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleCreateTask} data-testid="submit-task-button" className="bg-[#4F46E5] hover:bg-[#4338CA]">
                  Assign Task
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {columns.map((column) => {
          const columnTasks = getTasksByStatus(column.id);
          return (
            <div key={column.id} data-testid={`kanban-column-${column.id}`}>
              <div className="mb-4 flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${column.color}`}></div>
                <h3 className="font-semibold text-[#0F172A] dark:text-[#FAFAFA]">{column.title}</h3>
                <Badge variant="secondary" className="text-xs">{columnTasks.length}</Badge>
              </div>
              <div className="space-y-3 min-h-[400px] p-3 bg-[#F8FAFC] dark:bg-[#18181B] rounded-xl border border-[#E2E8F0] dark:border-[#27272A]">
                {columnTasks.map((task, index) => (
                  <motion.div key={task.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }}>
                    <Card className="border-[#E2E8F0] dark:border-[#27272A] hover:shadow-md transition-shadow cursor-pointer" data-testid={`task-card-${task.id}`}>
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between mb-2">
                          <h4 className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">{task.title}</h4>
                          <Badge className={`text-xs ${priorityColors[task.priority]}`}>{task.priority}</Badge>
                        </div>
                        {task.description && (
                          <p className="text-sm text-[#64748B] dark:text-[#A1A1AA] mb-3 line-clamp-2">{task.description}</p>
                        )}
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          {task.work_type === 'work_from_home' ? (
                            <Badge variant="outline" className="text-xs border-purple-300 text-purple-700 dark:text-purple-400">
                              <Home className="w-3 h-3 mr-1" />
                              Work from Home
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs border-blue-300 text-blue-700 dark:text-blue-400">
                              <Building className="w-3 h-3 mr-1" />
                              In Office
                            </Badge>
                          )}
                          {task.assignee_name && (
                            <Badge variant="outline" className="text-xs">
                              {task.assignee_name}
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3 text-xs text-[#64748B] dark:text-[#A1A1AA]">
                            {task.comments?.length > 0 && (
                              <div className="flex items-center gap-1">
                                <MessageSquare className="w-3 h-3" />
                                {task.comments.length}
                              </div>
                            )}
                            {task.due_date && (
                              <div className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" />
                                {formatDate(task.due_date)}
                              </div>
                            )}
                          </div>
                          <Select value={task.status} onValueChange={(v) => handleStatusChange(task.id, v)}>
                            <SelectTrigger className="h-7 text-xs w-24">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="todo">To Do</SelectItem>
                              <SelectItem value="in_progress">In Progress</SelectItem>
                              <SelectItem value="review">Review</SelectItem>
                              <SelectItem value="done">Done</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
                {columnTasks.length === 0 && (
                  <div className="text-center py-8">
                    <FolderKanban className="w-8 h-8 text-[#64748B] dark:text-[#A1A1AA] mx-auto mb-2" />
                    <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">No tasks</p>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TasksPage;
