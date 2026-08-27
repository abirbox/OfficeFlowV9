import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Bell, Lock, User, Palette, Shield, Building2, MapPin, Droplet, Mail } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { useTheme } from '@/contexts/ThemeContext';
import { toast } from '@/components/ui/sonner';
import BrandingTab from '@/components/settings/BrandingTab';
import OfficeLocationsTab from '@/components/settings/OfficeLocationsTab';
import ColorsTab from '@/components/settings/ColorsTab';
import EmailSettingsTab from '@/components/settings/EmailSettingsTab';

const SettingsPage = () => {
  const { user } = useAuthStore();
  const { theme, toggleTheme } = useTheme();
  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin';
  const [notifications, setNotifications] = useState({
    email: true,
    push: true,
    sms: false,
  });

  return (
    <div data-testid="settings-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
          Settings
        </h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
          Manage your account preferences
        </p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <div className="overflow-x-auto -mx-3 md:mx-0 px-3 md:px-0 scrollbar-thin" data-testid="settings-tabs-scroll">
          <TabsList className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] w-max min-w-full flex-nowrap justify-start">
            <TabsTrigger value="profile" data-testid="tab-profile" className="shrink-0">
            <User className="w-4 h-4 mr-2" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="security" data-testid="tab-security" className="shrink-0">
            <Shield className="w-4 h-4 mr-2" />
            Security
          </TabsTrigger>
          <TabsTrigger value="notifications" data-testid="tab-notifications" className="shrink-0">
            <Bell className="w-4 h-4 mr-2" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="appearance" data-testid="tab-appearance" className="shrink-0">
            <Palette className="w-4 h-4 mr-2" />
            Appearance
          </TabsTrigger>
          {isAdmin && (
            <TabsTrigger value="branding" data-testid="tab-branding" className="shrink-0">
              <Building2 className="w-4 h-4 mr-2" />
              Branding
            </TabsTrigger>
          )}
          {isAdmin && (
            <TabsTrigger value="colors" data-testid="tab-colors" className="shrink-0">
              <Droplet className="w-4 h-4 mr-2" />
              Colours
            </TabsTrigger>
          )}
          {isAdmin && (
            <TabsTrigger value="offices" data-testid="tab-offices" className="shrink-0">
              <MapPin className="w-4 h-4 mr-2" />
              Offices
            </TabsTrigger>
          )}
          {isAdmin && (
            <TabsTrigger value="email" data-testid="tab-email" className="shrink-0">
              <Mail className="w-4 h-4 mr-2" />
              Email
            </TabsTrigger>
          )}
          </TabsList>
        </div>

        <TabsContent value="profile">
          <Card className="border-[#E2E8F0] dark:border-[#27272A]">
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-6">
                <Avatar className="w-24 h-24">
                  <AvatarImage src={user?.avatar_path} />
                  <AvatarFallback className="bg-[#4F46E5] text-white text-3xl">
                    {user?.name?.charAt(0).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <h3 className="text-xl font-semibold text-[#0F172A] dark:text-[#FAFAFA]">{user?.name}</h3>
                  <p className="text-[#64748B] dark:text-[#A1A1AA]">{user?.email}</p>
                  <p className="text-sm text-[#4F46E5] mt-1 capitalize">{user?.role?.replace('_', ' ')}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Full Name</Label>
                  <Input defaultValue={user?.name} data-testid="settings-name-input" />
                </div>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input defaultValue={user?.email} disabled />
                </div>
                <div className="space-y-2">
                  <Label>Phone</Label>
                  <Input defaultValue={user?.phone || ''} placeholder="+1 234 567 8900" data-testid="settings-phone-input" />
                </div>
                <div className="space-y-2">
                  <Label>Role</Label>
                  <Input defaultValue={user?.role} disabled />
                </div>
              </div>

              <Button onClick={() => toast.success('Profile updated')} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-profile-button">
                Save Changes
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security">
          <Card className="border-[#E2E8F0] dark:border-[#27272A]">
            <CardHeader>
              <CardTitle>Security Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label>Current Password</Label>
                <Input type="password" data-testid="current-password-input" />
              </div>
              <div className="space-y-2">
                <Label>New Password</Label>
                <Input type="password" data-testid="new-password-input" />
              </div>
              <div className="space-y-2">
                <Label>Confirm New Password</Label>
                <Input type="password" data-testid="confirm-password-input" />
              </div>
              <Button onClick={() => toast.success('Password changed')} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="change-password-button">
                Change Password
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications">
          <Card className="border-[#E2E8F0] dark:border-[#27272A]">
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">Email Notifications</p>
                  <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">Receive updates via email</p>
                </div>
                <Switch
                  checked={notifications.email}
                  onCheckedChange={(v) => setNotifications({ ...notifications, email: v })}
                  data-testid="email-notifications-switch"
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">Push Notifications</p>
                  <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">Receive in-app notifications</p>
                </div>
                <Switch
                  checked={notifications.push}
                  onCheckedChange={(v) => setNotifications({ ...notifications, push: v })}
                  data-testid="push-notifications-switch"
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">SMS Notifications</p>
                  <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">Receive updates via SMS</p>
                </div>
                <Switch
                  checked={notifications.sms}
                  onCheckedChange={(v) => setNotifications({ ...notifications, sms: v })}
                  data-testid="sms-notifications-switch"
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appearance">
          <Card className="border-[#E2E8F0] dark:border-[#27272A]">
            <CardHeader>
              <CardTitle>Appearance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">Dark Mode</p>
                  <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">Toggle between light and dark themes</p>
                </div>
                <Switch
                  checked={theme === 'dark'}
                  onCheckedChange={toggleTheme}
                  data-testid="dark-mode-switch"
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {isAdmin && (
          <TabsContent value="branding">
            <BrandingTab />
          </TabsContent>
        )}

        {isAdmin && (
          <TabsContent value="colors">
            <ColorsTab />
          </TabsContent>
        )}

        {isAdmin && (
          <TabsContent value="offices">
            <OfficeLocationsTab />
          </TabsContent>
        )}

        {isAdmin && (
          <TabsContent value="email">
            <EmailSettingsTab />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
};

export default SettingsPage;
