import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
    children?: ReactNode;
}

interface State {
    hasError: boolean;
    error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div className="flex h-full w-full flex-col items-center justify-center p-6 text-center">
                    <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                        <AlertTriangle className="h-8 w-8" />
                    </div>
                    <h2 className="mb-2 text-2xl font-bold tracking-tight text-foreground">
                        Что-то пошло не так
                    </h2>
                    <p className="mb-6 max-w-md text-muted-foreground">
                        Произошла непредвиденная ошибка в приложении. Мы уже в курсе и работаем над этим.
                    </p>
                    <div className="flex gap-4">
                        <button
                            onClick={() => window.location.reload()}
                            className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                        >
                            Перезагрузить страницу
                        </button>
                        <button
                            onClick={() => {
                                this.setState({ hasError: false });
                                window.location.href = '/';
                            }}
                            className="inline-flex h-10 items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
                        >
                            На главную
                        </button>
                    </div>
                    {process.env.NODE_ENV === 'development' && this.state.error && (
                        <div className="mt-8 mx-auto max-w-2xl text-left bg-secondary p-4 rounded-lg overflow-auto">
                            <p className="font-mono text-sm text-destructive font-semibold mb-2">{this.state.error.toString()}</p>
                            <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                                {this.state.error.stack}
                            </pre>
                        </div>
                    )}
                </div>
            );
        }

        return this.props.children;
    }
}
