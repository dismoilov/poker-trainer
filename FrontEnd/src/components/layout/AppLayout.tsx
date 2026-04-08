import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Home,
  Target,
  GitBranch,
  BarChart3,
  BookOpen,
  Cpu,
  Settings,
  HelpCircle,
  User,
  LogOut,
  Spade,
  Zap,
} from 'lucide-react';
import { useAppStore } from '@/store/useAppStore';
import { useAuthStore } from '@/store/useAuthStore';
import { HotkeyModal } from '@/components/HotkeyModal';
import { useHotkey } from '@/lib/useHotkeys';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';

const navItems = [
  { to: '/', icon: Home, label: 'Главная' },
  { to: '/play', icon: Spade, label: 'Игра' },
  { to: '/drill', icon: Target, label: 'Тренировка' },
  { to: '/explore', icon: GitBranch, label: 'Обзор' },
  { to: '/analytics', icon: BarChart3, label: 'Аналитика' },
  { to: '/library', icon: BookOpen, label: 'Библиотека' },
  { to: '/jobs', icon: Cpu, label: 'Задачи' },
  { to: '/solver', icon: Zap, label: 'Солвер' },
  { to: '/guide', icon: HelpCircle, label: 'Справочник' },
  { to: '/settings', icon: Settings, label: 'Настройки' },
];

export function AppLayout() {
  const navigate = useNavigate();
  const toggleHotkeyModal = useAppStore((s) => s.toggleHotkeyModal);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const queryClient = useQueryClient();

  useHotkey('?', toggleHotkeyModal);

  const handleLogout = () => {
    logout();
    queryClient.clear();
    navigate('/login', { replace: true });
  };

  const prefetchData = (path: string) => {
    switch (path) {
      case '/analytics':
        queryClient.prefetchQuery({ queryKey: ['analytics-summary'], queryFn: api.getAnalyticsSummary });
        queryClient.prefetchQuery({ queryKey: ['analytics-history'], queryFn: api.getAnalyticsHistory });
        queryClient.prefetchQuery({ queryKey: ['analytics-recent'], queryFn: api.getRecentQuestions });
        break;
      case '/jobs':
        queryClient.prefetchQuery({ queryKey: ['jobs'], queryFn: api.getJobs });
        break;
      case '/library':
      case '/drill':
      case '/explore':
        queryClient.prefetchQuery({ queryKey: ['spots'], queryFn: api.getSpots });
        break;
    }
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <aside className="w-16 lg:w-56 border-r border-border flex flex-col py-4 shrink-0 bg-card/50">
        <div className="px-4 mb-8">
          <h1 className="text-primary font-bold text-lg hidden lg:block tracking-tight">
            PokerTrainer
          </h1>
          <div className="lg:hidden text-primary font-bold text-xl text-center">
            PT
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-2" aria-label="Основная навигация">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onMouseEnter={() => prefetchData(item.to)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors ${isActive
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                }`
              }
            >
              <item.icon className="w-5 h-5 shrink-0" />
              <span className="hidden lg:inline">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Bottom: profile + help */}
        <div className="px-2 mt-auto space-y-1">
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors ${isActive
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
              }`
            }
          >
            <User className="w-5 h-5 shrink-0" />
            <span className="hidden lg:inline">{user?.username || 'Профиль'}</span>
          </NavLink>
          <button
            onClick={toggleHotkeyModal}
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-secondary w-full transition-colors"
            aria-label="Горячие клавиши"
          >
            <HelpCircle className="w-5 h-5 shrink-0" />
            <span className="hidden lg:inline">Горячие клавиши</span>
          </button>
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 w-full transition-colors"
            aria-label="Выйти"
          >
            <LogOut className="w-5 h-5 shrink-0" />
            <span className="hidden lg:inline">Выйти</span>
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto scrollbar-thin">
        <Outlet />
      </main>
      <HotkeyModal />
    </div>
  );
}
