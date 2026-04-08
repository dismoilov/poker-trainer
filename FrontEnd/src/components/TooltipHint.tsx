import React from 'react';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip';

interface TooltipHintProps {
    children: React.ReactNode;
    content: React.ReactNode;
    delayDuration?: number;
    className?: string;
}

export function TooltipHint({
    children,
    content,
    delayDuration = 200,
    className,
}: TooltipHintProps) {
    return (
        <TooltipProvider delayDuration={delayDuration}>
            <Tooltip>
                <TooltipTrigger asChild>
                    <span className={`cursor-help border-b border-dashed border-primary/50 hover:border-primary transition-colors ${className || ''}`}>
                        {children}
                    </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-[300px] text-sm p-3 bg-popover text-popover-foreground border-border break-words">
                    {content}
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}

// Популярные термины для переиспользования
export const HINTS = {
    SRP: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">SRP (Single Raised Pot)</div>
            <div className="text-muted-foreground">Банк с одним рейзом на префлопе. Самая частая ситуация в покере. Широкий диапазон рук.</div>
        </div>
    ),
    '3-Bet': (
        <div className="space-y-1">
            <div className="font-semibold text-primary">3-Bet Pot</div>
            <div className="text-muted-foreground">Банк с тремя ставками (рейз → 3-бет). Узкие диапазоны, большой банк.</div>
        </div>
    ),
    '4-Bet': (
        <div className="space-y-1">
            <div className="font-semibold text-primary">4-Bet Pot</div>
            <div className="text-muted-foreground">Очень большой банк (рейз → 3-бет → 4-бет). Экстремально узкие и сильные диапазоны.</div>
        </div>
    ),
    Squeeze: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">Squeeze</div>
            <div className="text-muted-foreground">3-бет после первоначального рейза и одного или нескольких коллов. Агрессивная линия.</div>
        </div>
    ),
    EVLoss: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">EV Loss (Expected Value Loss)</div>
            <div className="text-muted-foreground">Насколько действие отклоняется от GTO-оптимума по математическому ожиданию (в bb). 0.0bb = идеальное решение.</div>
        </div>
    ),
    Accuracy: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">Точность (Accuracy)</div>
            <div className="text-muted-foreground">Процент совпадения вашего выбора с GTO. Высчитывается как (частота вашего действия / макс. частота).</div>
        </div>
    ),
    IP: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">IP (In Position)</div>
            <div className="text-muted-foreground">Игра в позиции. Игрок принимает решение последним (после флопа), что дает огромное преимущество.</div>
        </div>
    ),
    OOP: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">OOP (Out of Position)</div>
            <div className="text-muted-foreground">Игра без позиции. Игрок принимает решение первым (после флопа), не зная действий оппонента.</div>
        </div>
    ),
    BTN: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">BTN (Button / Баттон)</div>
            <div className="text-muted-foreground">Самая выгодная позиция за столом. Действует последним на всех постфлоп улицах. Самый широкий диапазон открытия (до 40%).</div>
        </div>
    ),
    BB: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">BB (Big Blind / Большой блайнд)</div>
            <div className="text-muted-foreground">Самая широкая защита на префлопе из-за хороших шансов банка, но всегда играет без позиции (OOP).</div>
        </div>
    ),
    CO: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">CO (Cutoff / Катофф)</div>
            <div className="text-muted-foreground">Позиция перед Баттоном. Вторая по значимости, может открывать широкие диапазоны.</div>
        </div>
    ),
    SB: (
        <div className="space-y-1">
            <div className="font-semibold text-primary">SB (Small Blind / Малый блайнд)</div>
            <div className="text-muted-foreground">Тяжелая позиция. Нужно доставить полставки вслепую, а после флопа всегда играть первым.</div>
        </div>
    )
};
