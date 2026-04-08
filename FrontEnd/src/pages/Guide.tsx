import { BookOpen, Target, GitBranch, BarChart3, Cpu, Layout, Lightbulb } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';

const Guide = () => {
    return (
        <div className="p-6 lg:p-10 max-w-5xl mx-auto space-y-12">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                    <BookOpen className="w-8 h-8 text-primary" />
                    Справочник PokerTrainer
                </h1>
                <p className="text-muted-foreground mt-2 text-lg">
                    Полное руководство по GTO-стратегиям, покерным концепциям и работе тренажёра.
                </p>
            </div>

            <section className="space-y-6">
                <h2 className="text-2xl font-bold tracking-tight border-b pb-2 flex items-center gap-2">
                    <Lightbulb className="w-6 h-6 text-primary" />
                    Ключевые концепции
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Что такое GTO?</CardTitle>
                        </CardHeader>
                        <CardContent className="text-muted-foreground space-y-2">
                            <p><strong>GTO (Game Theory Optimal)</strong> — стратегия покера, основанная на теории игр, при которой ваша игра не может быть эксплуатирована оппонентом. Это математически оптимальная стратегия, рассчитанная компьютерными солверами.</p>
                            <p>В реальности GTO означает, что для каждой руки в каждой ситуации существует оптимальная <strong>частота</strong> каждого действия (смешанная стратегия).</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>EV Loss (Потеря ценности)</CardTitle>
                        </CardHeader>
                        <CardContent className="text-muted-foreground space-y-2">
                            <p><strong>EV Loss</strong> — разница между EV вашего выбора и EV GTO-оптимального действия (измеряется в больших блайндах <strong>bb</strong>).</p>
                            <ul className="list-disc pl-5 space-y-1">
                                <li><span className="text-green-500 font-medium">0.0bb</span> — идеальное решение</li>
                                <li><span className="text-green-500 font-medium">&lt; 0.5bb</span> — отличное решение</li>
                                <li><span className="text-yellow-500 font-medium">0.5 – 2.0bb</span> — допустимая ошибка</li>
                                <li><span className="text-red-500 font-medium">&gt; 2.0bb</span> — грубая ошибка</li>
                            </ul>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Точность (Accuracy)</CardTitle>
                        </CardHeader>
                        <CardContent className="text-muted-foreground space-y-2">
                            <p>Процентное отношение частоты вашего действия к частоте GTO-оптимального.</p>
                            <p>Если GTO ставит в 70% случаев, а вы выбрали ставку — ваша точность 100%. Если вы выбрали чек (который GTO делает в 30% случаев), ваша точность составит 30/70 = 42%.</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Споты (Spots)</CardTitle>
                        </CardHeader>
                        <CardContent className="text-muted-foreground space-y-2">
                            <p>Конкретная игровая ситуация, например «SRP BTN vs BB Flop». Спот включает в себя формат, позиции игроков, улицу и глубину стека.</p>
                        </CardContent>
                    </Card>
                </div>
            </section>

            <section className="space-y-6">
                <h2 className="text-2xl font-bold tracking-tight border-b pb-2 flex items-center gap-2">
                    <Target className="w-6 h-6 text-primary" />
                    Форматы спотов
                </h2>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-5 bg-card border rounded-2xl">
                        <h3 className="font-bold text-lg text-primary mb-2">SRP (Single Raised Pot)</h3>
                        <p className="text-sm text-muted-foreground">Один игрок сделал рейз, другой заколлировал. Самая частая ситуация. Банк ~6.5bb. Широкие диапазоны, умеренная агрессия.</p>
                    </div>
                    <div className="p-5 bg-card border rounded-2xl">
                        <h3 className="font-bold text-lg text-primary mb-2">3-Bet Pot</h3>
                        <p className="text-sm text-muted-foreground">Банк с тремя ставками (рейз → 3-бет). Узкие диапазоны, много префлоп фолдов, банк ~22bb.</p>
                    </div>
                    <div className="p-5 bg-card border rounded-2xl">
                        <h3 className="font-bold text-lg text-primary mb-2">4-Bet Pot</h3>
                        <p className="text-sm text-muted-foreground">Очень большой банк (рейз → 3-бет → 4-бет). Экстремально узкие и сильные диапазоны. Поляризованная стратегия.</p>
                    </div>
                    <div className="p-5 bg-card border rounded-2xl">
                        <h3 className="font-bold text-lg text-primary mb-2">Squeeze</h3>
                        <p className="text-sm text-muted-foreground">3-бет после рейза и одного или нескольких коллов. Агрессивная линия с высокой частотой фолдов от соперников.</p>
                    </div>
                </div>
            </section>

            <section className="space-y-6">
                <h2 className="text-2xl font-bold tracking-tight border-b pb-2">Позиции за столом</h2>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left border">
                        <thead className="text-xs uppercase bg-secondary text-secondary-foreground">
                            <tr>
                                <th className="px-4 py-3 border-b">Позиция</th>
                                <th className="px-4 py-3 border-b">IP/OOP</th>
                                <th className="px-4 py-3 border-b">Описание</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y text-muted-foreground bg-card">
                            <tr>
                                <td className="px-4 py-3 font-medium text-foreground">BTN (Баттон)</td>
                                <td className="px-4 py-3"><span className="px-2 py-1 rounded bg-green-500/10 text-green-500">IP</span></td>
                                <td className="px-4 py-3">Лучшая позиция. Действует последним на постфлопе. Самый широкий диапазон открытий (~40%).</td>
                            </tr>
                            <tr>
                                <td className="px-4 py-3 font-medium text-foreground">CO (Катофф)</td>
                                <td className="px-4 py-3"><span className="px-2 py-1 rounded bg-green-500/10 text-green-500">IP</span></td>
                                <td className="px-4 py-3">Вторая лучшая позиция. Широкий диапазон (~27%).</td>
                            </tr>
                            <tr>
                                <td className="px-4 py-3 font-medium text-foreground">UTG, HJ, MP</td>
                                <td className="px-4 py-3"><span className="px-2 py-1 rounded bg-yellow-500/10 text-yellow-500">Зависит</span></td>
                                <td className="px-4 py-3">Ранние и средние позиции. Узкие диапазоны префлоп-открытий (15-20%).</td>
                            </tr>
                            <tr>
                                <td className="px-4 py-3 font-medium text-foreground">SB (Малый блайнд)</td>
                                <td className="px-4 py-3"><span className="px-2 py-1 rounded bg-red-500/10 text-red-500">OOP</span></td>
                                <td className="px-4 py-3">Действует первым на постфлопе. Сложная позиция для розыгрыша.</td>
                            </tr>
                            <tr>
                                <td className="px-4 py-3 font-medium text-foreground">BB (Большой блайнд)</td>
                                <td className="px-4 py-3"><span className="px-2 py-1 rounded bg-red-500/10 text-red-500">OOP</span></td>
                                <td className="px-4 py-3">Имеет лучшие пот-оддсы для защиты на префлопе, поэтому играет широким диапазоном, но без позиции (OOP).</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                    <strong>IP (In Position)</strong> — действует последним, видя действия оппонента.<br />
                    <strong>OOP (Out of Position)</strong> — действует первым без информации (GTO часто защищается чеком).
                </p>
            </section>

            <section className="space-y-6">
                <h2 className="text-2xl font-bold tracking-tight border-b pb-2 flex items-center gap-2">
                    <Layout className="w-6 h-6 text-primary" />
                    Цвета матрицы рук
                </h2>
                <p className="text-muted-foreground">Ячейки матрицы окрашены в цвет доминирующего действия, а непрозрачность (opacity) зависит от его частоты.</p>

                <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                    <div className="flex flex-col items-center justify-center p-4 bg-card border rounded-2xl">
                        <div className="w-10 h-10 rounded-full mb-3 shadow-[0_0_15px_rgba(239,68,68,0.5)] bg-[hsl(0,55%,45%)]"></div>
                        <div className="font-bold">Фолд</div>
                    </div>
                    <div className="flex flex-col items-center justify-center p-4 bg-card border rounded-2xl">
                        <div className="w-10 h-10 rounded-full mb-3 shadow-[0_0_15px_rgba(234,179,8,0.5)] bg-[hsl(45,65%,50%)]"></div>
                        <div className="font-bold">Чек</div>
                    </div>
                    <div className="flex flex-col items-center justify-center p-4 bg-card border rounded-2xl">
                        <div className="w-10 h-10 rounded-full mb-3 shadow-[0_0_15px_rgba(34,197,94,0.5)] bg-[hsl(155,55%,40%)]"></div>
                        <div className="font-bold">Колл</div>
                    </div>
                    <div className="flex flex-col items-center justify-center p-4 bg-card border rounded-2xl">
                        <div className="w-10 h-10 rounded-full mb-3 shadow-[0_0_15px_rgba(59,130,246,0.5)] bg-[hsl(210,65%,50%)]"></div>
                        <div className="font-bold">Бет 33-50%</div>
                    </div>
                    <div className="flex flex-col items-center justify-center p-4 bg-card border rounded-2xl">
                        <div className="w-10 h-10 rounded-full mb-3 shadow-[0_0_15px_rgba(168,85,247,0.5)] bg-[hsl(270,55%,50%)]"></div>
                        <div className="font-bold">Бет 75%+ / Рейз</div>
                    </div>
                </div>
            </section>

            <section className="space-y-4 text-center mt-10">
                <p className="text-muted-foreground">Используйте <strong>всплывающие подсказки</strong>, наводя курсор на пунктирные подчёркивания на других страницах, чтобы быстро получать эту информацию без перехода в Справочник.</p>
            </section>

        </div>
    );
};

export default Guide;
