import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { dhakaParts, formatMonth } from '@/lib/datetime';

const CalendarPage = () => {
  const [currentDate, setCurrentDate] = useState(new Date());

  const cursor = dhakaParts(currentDate);          // {y, m, d} in Asia/Dhaka
  const daysInMonth = new Date(Date.UTC(cursor.y, cursor.m, 0)).getUTCDate();
  const firstDay = new Date(Date.UTC(cursor.y, cursor.m - 1, 1)).getUTCDay();
  const monthName = formatMonth(currentDate);

  const days = [];
  for (let i = 0; i < firstDay; i++) days.push(null);
  for (let i = 1; i <= daysInMonth; i++) days.push(i);

  const todayParts = dhakaParts(new Date());
  const isToday = (day) =>
    day === todayParts.d &&
    cursor.m === todayParts.m &&
    cursor.y === todayParts.y;

  const changeMonth = (delta) => {
    setCurrentDate(new Date(Date.UTC(cursor.y, cursor.m - 1 + delta, 1)));
  };

  return (
    <div data-testid="calendar-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
            Calendar
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
            View events, deadlines, and meetings
          </p>
        </div>
        <Button data-testid="add-event-button" className="bg-[#4F46E5] hover:bg-[#4338CA]">
          <Plus className="w-5 h-5 mr-2" />
          Add Event
        </Button>
      </div>

      <Card className="border-[#E2E8F0] dark:border-[#27272A]">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-2xl">{monthName}</CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="icon" onClick={() => changeMonth(-1)} data-testid="prev-month">
                <ChevronLeft className="w-5 h-5" />
              </Button>
              <Button variant="outline" size="icon" onClick={() => changeMonth(1)} data-testid="next-month">
                <ChevronRight className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-2 mb-2">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
              <div key={day} className="text-center text-sm font-medium text-[#64748B] dark:text-[#A1A1AA] py-2">
                {day}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-2">
            {days.map((day, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: index * 0.01 }}
                className={`aspect-square p-2 rounded-lg border ${
                  day
                    ? isToday(day)
                      ? 'bg-[#4F46E5] text-white border-[#4F46E5]'
                      : 'bg-white dark:bg-[#18181B] border-[#E2E8F0] dark:border-[#27272A] hover:bg-[#F8FAFC] dark:hover:bg-[#27272A]'
                    : 'border-transparent'
                } transition-colors cursor-pointer`}
              >
                {day && (
                  <div className="text-sm font-medium">
                    {day}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default CalendarPage;
