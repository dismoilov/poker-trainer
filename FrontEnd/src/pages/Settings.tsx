import { useSettingsStore } from '@/store/useSettingsStore';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const SettingsPage = () => {
  const settings = useSettingsStore();

  return (
    <div className="p-6 lg:p-10 max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold tracking-tight text-foreground">
        Настройки
      </h1>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList className="bg-secondary">
          <TabsTrigger value="profile">Профиль</TabsTrigger>
          <TabsTrigger value="hotkeys">Горячие клавиши</TabsTrigger>
          <TabsTrigger value="display">Внешний вид</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="space-y-6">
          <div className="bg-card border border-border rounded-2xl p-5 space-y-5">
            <h2 className="font-medium text-foreground">Профиль игры</h2>

            {/* Stack */}
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">
                Стек (bb): {settings.stack}bb
              </Label>
              <Slider
                value={[settings.stack]}
                onValueChange={([v]) => settings.setStack(v)}
                min={20}
                max={200}
                step={5}
                className="w-full"
              />
            </div>

            {/* Rake profile */}
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">
                Рейк профиль
              </Label>
              <Select
                value={settings.rakeProfile}
                onValueChange={(v) =>
                  settings.setRakeProfile(v as 'low' | 'high')
                }
              >
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low rake</SelectItem>
                  <SelectItem value="high">High rake</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Sizings */}
            <div className="space-y-3">
              <Label className="text-sm text-muted-foreground">
                Сайзинги (% pot)
              </Label>
              {(['flop', 'turn', 'river'] as const).map((street) => (
                <div
                  key={street}
                  className="flex items-center gap-3"
                >
                  <span className="text-xs text-muted-foreground w-12 capitalize">
                    {street}
                  </span>
                  <div className="flex gap-2 flex-wrap">
                    {settings.sizings[street].map((size, i) => (
                      <span
                        key={i}
                        className="text-xs bg-secondary px-2.5 py-1 rounded-lg text-secondary-foreground font-mono"
                      >
                        {size}%
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="hotkeys" className="space-y-6">
          <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
            <h2 className="font-medium text-foreground">
              Горячие клавиши
            </h2>
            {Object.entries(settings.hotkeys).map(([action, key]) => (
              <div
                key={action}
                className="flex items-center justify-between"
              >
                <span className="text-sm text-muted-foreground">
                  {action}
                </span>
                <kbd className="px-2.5 py-1 bg-secondary rounded-md text-xs font-mono text-secondary-foreground">
                  {key}
                </kbd>
              </div>
            ))}
            <p className="text-xs text-muted-foreground mt-2">
              Редактирование хоткеев будет доступно в следующем обновлении
            </p>
          </div>
        </TabsContent>

        <TabsContent value="display" className="space-y-6">
          <div className="bg-card border border-border rounded-2xl p-5 space-y-5">
            <h2 className="font-medium text-foreground">Внешний вид</h2>

            {/* Theme */}
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm text-foreground">Тёмная тема</Label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Переключение светлой/тёмной темы
                </p>
              </div>
              <Switch
                checked={settings.theme === 'dark'}
                onCheckedChange={(checked) =>
                  settings.setTheme(checked ? 'dark' : 'light')
                }
              />
            </div>

            {/* Compact */}
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm text-foreground">
                  Компактный режим
                </Label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Уменьшить отступы и размеры элементов
                </p>
              </div>
              <Switch
                checked={settings.compact}
                onCheckedChange={settings.setCompact}
              />
            </div>

            {/* Hints */}
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm text-foreground">Подсказки</Label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Показывать подсказки в режиме тренировки
                </p>
              </div>
              <Switch
                checked={settings.showHints}
                onCheckedChange={settings.setShowHints}
              />
            </div>

            {/* Language */}
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm text-foreground">Язык</Label>
              </div>
              <Select
                value={settings.language}
                onValueChange={(v) =>
                  settings.setLanguage(v as 'ru' | 'en')
                }
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ru">Русский</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default SettingsPage;
