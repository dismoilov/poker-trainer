/**
 * Russian Terminology Dictionary — Phase 8C
 *
 * Centralized source of truth for all user-facing Russian text.
 * Used across all pages for consistency.
 */

// ── Navigation ──
export const NAV = {
  dashboard: 'Главная',
  play: 'Игра',
  drill: 'Тренировка',
  explore: 'Обзор',
  analytics: 'Аналитика',
  library: 'Библиотека',
  jobs: 'Задачи',
  solver: 'Солвер',
  guide: 'Справочник',
  settings: 'Настройки',
  hotkeys: 'Горячие клавиши',
  logout: 'Выйти',
} as const;

// ── Poker Actions ──
export const ACTIONS: Record<string, string> = {
  fold: 'Фолд',
  check: 'Чек',
  call: 'Колл',
  bet: 'Бет',
  raise: 'Рейз',
  allin: 'Олл-ин',
  bet33: 'Бет 33%',
  bet_33: 'Бет 33%',
  bet50: 'Бет 50%',
  bet_50: 'Бет 50%',
  bet75: 'Бет 75%',
  bet_75: 'Бет 75%',
  bet100: 'Бет 100%',
  bet_100: 'Бет 100%',
  bet150: 'Бет 150%',
  bet_150: 'Бет 150%',
};

export function actionLabel(id: string): string {
  return ACTIONS[id] || id.replace(/_/g, ' ');
}

// ── Streets ──
export const STREETS: Record<string, string> = {
  flop: 'Флоп',
  turn: 'Тёрн',
  river: 'Ривер',
  preflop: 'Префлоп',
};

// ── Quality Labels ──
export const QUALITY: Record<string, { emoji: string; text: string }> = {
  perfect: { emoji: '🎯', text: 'Отлично' },
  close_to_solver: { emoji: '✅', text: 'Близко к солверу' },
  acceptable_deviation: { emoji: '⚠️', text: 'Приемлемое отклонение' },
  clear_deviation: { emoji: '❌', text: 'Значительное отклонение' },
  unknown: { emoji: '❓', text: 'Нет данных' },
};

// ── Trust Grades ──
export const TRUST_GRADES: Record<string, string> = {
  FAILED: 'Не пройдена',
  STRUCTURAL_ONLY: 'Только структура',
  INTERNAL_DEMO: 'Демо-режим',
  INTERNAL_DEMO_WITH_WARNINGS: 'Демо с замечаниями',
  VALIDATED_LIMITED_SCOPE: 'Проверено (ограниченый охват)',
};

// ── Data Sources ──
export const DATA_SOURCES: Record<string, string> = {
  real_cfr_solver: 'Настоящий CFR+ солвер',
  heuristic: 'Эвристика GTO',
  persisted_summary: 'Сохранённые данные',
  in_memory: 'Оперативные данные',
};

// ── Solver Page ──
export const SOLVER = {
  title: 'Солвер (CFR+)',
  subtitle: 'Настоящий итеративный солвер для постфлоп ситуаций',
  introTitle: '🎓 Что такое солвер?',
  introText:
    'Солвер — это программа, которая математически рассчитывает оптимальную стратегию покера. ' +
    'Вы задаёте борд, диапазоны рук и стеки — солвер находит, какие действия лучше и с какой частотой.',
  whenToUse: '💡 Когда использовать?',
  whenToUseItems: [
    'Хотите узнать точную оптимальную стратегию для конкретного борда',
    'Готовы подождать 10-60 секунд пока солвер считает',
    'Уже попробовали Тренировку и Обзор, хотите разобраться глубже',
  ],
  altPages:
    'Для быстрого обучения используйте Тренировку (готовые упражнения) или Обзор (изучение стратегий без ожидания).',
  honestNote:
    'Солвер ограничен флоп-ситуациями с маленькими диапазонами (~50 комбинаций на сторону). ' +
    'Метрика сходимости приблизительная. Это реальный CFR+ солвер, но в ограниченном масштабе.',
  basicMode: 'Простой режим',
  advancedMode: 'Расширенный режим',
  fieldBoard: 'Борд',
  fieldBoardHint: '3 карты флопа, например: Ks 7d 2c',
  fieldIpRange: 'Диапазон IP',
  fieldIpRangeHint: 'Игрок в позиции, например: AA,KK,AKs',
  fieldOopRange: 'Диапазон OOP',
  fieldOopRangeHint: 'Игрок без позиции, например: QQ,JJ,AQs',
  fieldPot: 'Банк (bb)',
  fieldPotHint: 'Размер банка в больших блайндах',
  fieldStack: 'Стек (bb)',
  fieldStackHint: 'Эффективный стек в больших блайндах',
  fieldBetSizes: 'Размеры бетов',
  fieldBetSizesHint: 'Доли от банка через запятую: 0.5, 1.0',
  fieldRaiseSizes: 'Размеры рейзов',
  fieldRaiseSizesHint: 'Множитель рейза через запятую: 2.5',
  fieldMaxIter: 'Макс. итераций',
  fieldMaxIterHint: 'Больше итераций = точнее, но дольше',
  fieldMaxRaises: 'Макс. рейзов',
  fieldIncludeTurn: 'Включить тёрн',
  fieldIncludeTurnHint: 'Добавит расчёт тёрна (увеличит время)',
  fieldMaxTurnCards: 'Макс. карт тёрна',
  btnSolve: 'Запустить солвер',
  btnRunning: 'Солвер считает...',
  historyTitle: 'История расчётов',
  historyNote: 'Сохранённые результаты с данными по комбинациям',
  loadingDetail: 'Загрузка...',
  resultTitle: 'Результат расчёта',
  iterations: 'Итерации',
  convergence: 'Сходимость',
  treeNodes: 'Узлов дерева',
  matchups: 'Сопоставлений',
  elapsed: 'Время расчёта',
  exploitability: 'Эксплоитабельность',
  exploitabilityHint:
    'Показывает, насколько стратегия может быть «обыграна». Чем меньше — тем ближе к оптимуму.',
  trustGrade: 'Оценка надёжности',
  trustGradeHint:
    'Общая оценка качества расчёта: учитывает сходимость, валидацию и эксплоитабельность.',
  rootStrategy: 'Стратегия в корне дерева',
  comboData: 'Данные по комбинациям',
  inspectNode: 'Просмотр узла',
  btnInspect: 'Показать',
  compareTitle: 'Сравнение с эвристикой',
  btnCompare: 'Сравнить',
  benchmarkTitle: 'Тесты корректности',
  btnBenchmark: 'Запустить тесты',
  persistedNote: 'Сохранённые результаты включают подмножество комбинаций для интеграции в продукт.',
  exactWithinAbstraction: '✓ Точно в рамках абстракции',
  studyValue: 'Ценность для изучения',
  studyValueHigh: '⭐ Высокая — сошёлся, низкая эксплоитабельность',
  studyValueMedium: '📊 Средняя — есть замечания',
  studyValueLow: '⚠️ Низкая — не сошёлся или высокая эксплоитабельность',
} as const;

// ── Play Page ──
export const PLAY = {
  title: 'Покерный стол',
  subtitle: 'Хедс-ап постфлоп — Герой (IP) против Оппонента (OOP)',
  villainNote: 'Оппонент использует эвристику — не GTO',
  startingStack: 'Стартовый стек (bb)',
  sitDown: 'Сесть за стол',
  newHand: 'Новая раздача',
  leaveTable: 'Встать из-за стола',
  pot: 'Банк',
  stack: 'Стек',
  hero: 'Герой',
  villain: 'Оппонент',
  yourHand: 'Ваша рука',
  actionHistory: 'История действий',
  compareToSolver: 'Сравнение с солвером',
  compareBtn: 'Сравнить с солвером',
  checkingSolver: 'Проверяем базу данных солвера...',
  solverRecommendation: 'Рекомендация солвера',
  accuracy: 'Точность',
  avgFrequencies: 'Средние частоты солвера',
  yourCombo: 'Ваша точная комбинация',
  solverDepth: 'Глубина расчёта',
  flopOnly: 'Только флоп',
  flopPlusTurn: 'Флоп + тёрн',
  clear: 'Очистить',
  showdown: 'Вскрытие',
  even: 'Ничья',
  noSolveFound: 'Для этого борда нет сохранённых расчётов. Запустите солвер на странице Солвер.',
  honestNote:
    'Сравнение использует сохранённый результат солвера для совпадающего борда. ' +
    'Показаны только данные корневого уровня, это НЕ расчёт в реальном времени.',
} as const;

// ── Drill Page ──
export const DRILL = {
  question: 'Вопрос',
  chooseAction: 'Выберите действие:',
  result: 'Результат',
  evLoss: 'Потери EV',
  accuracy: 'Точность',
  correctFreqs: 'Правильные частоты:',
  analysis: 'Объяснение:',
  next: 'Следующий',
  dataSource: 'Эвристика GTO • на основе предрассчитанных таблиц',
  solverDataSource: 'Настоящий CFR+ солвер • данные по комбинациям',
  mixedStrategy: 'Смешанная стратегия: солвер рекомендует несколько действий с разной частотой.',
  pureStrategy: 'Чистая стратегия: солвер предпочитает одно конкретное действие.',
  bestAction: 'Лучшее действие',
  yourAction: 'Ваше действие',
} as const;

// ── Explore Page ──
export const EXPLORE = {
  gtoFrequencies: 'GTO частоты',
  analysis: 'Анализ',
  solverRecommendation: '💡 Рекомендация солвера',
  situation: '📍 Ситуация',
  boardConnection: 'Связь с бордом',
  dataSource: 'Источник данных',
  heuristicGTO: 'Эвристика GTO',
  realSolver: 'Настоящий CFR+ солвер',
  handMatrix: 'Матрица рук',
  notes: 'Заметки',
  spotSelector: 'Выбор спота',
  nodeTree: 'Дерево решений',
} as const;

// ── Common ──
export const COMMON = {
  loading: 'Загрузка...',
  error: 'Ошибка',
  noData: 'Нет данных',
  save: 'Сохранить',
  cancel: 'Отмена',
  close: 'Закрыть',
  board: 'Борд',
  position: 'Позиция',
  pot: 'Банк',
  stack: 'Стек',
  scope: 'Охват',
  ip: 'В позиции',
  oop: 'Без позиции',
} as const;
