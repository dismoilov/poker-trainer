import { useState } from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import { User, Lock, Check } from 'lucide-react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const Profile = () => {
    const user = useAuthStore((s) => s.user);
    const token = useAuthStore((s) => s.token);

    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChangePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        if (newPassword.length < 4) {
            setError('Минимум 4 символа');
            return;
        }
        if (newPassword !== confirmPassword) {
            setError('Пароли не совпадают');
            return;
        }

        setLoading(true);
        try {
            const res = await fetch(`${BASE_URL}/api/auth/password`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ currentPassword, newPassword }),
            });
            if (!res.ok) {
                const data = await res.json().catch(() => ({ detail: 'Ошибка' }));
                throw new Error(data.detail || 'Ошибка');
            }
            setSuccess('Пароль изменён');
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Ошибка');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-4 lg:p-6 max-w-xl mx-auto space-y-6">
            <h1 className="text-xl font-bold text-foreground">Профиль</h1>

            {/* User info */}
            <div className="bg-card border border-border rounded-2xl p-5 flex items-center gap-4">
                <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center">
                    <User className="w-6 h-6 text-primary" />
                </div>
                <div>
                    <div className="font-medium text-foreground">{user?.username}</div>
                    <div className="text-sm text-muted-foreground">ID: {user?.id}</div>
                </div>
            </div>

            {/* Change password */}
            <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
                <div className="flex items-center gap-2 text-foreground font-medium">
                    <Lock className="w-4 h-4" />
                    Сменить пароль
                </div>

                <form onSubmit={handleChangePassword} className="space-y-3">
                    <div>
                        <label className="block text-sm text-muted-foreground mb-1">Текущий пароль</label>
                        <input
                            type="password"
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            className="w-full px-3 py-2.5 bg-secondary border border-border rounded-xl text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-colors"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-muted-foreground mb-1">Новый пароль</label>
                        <input
                            type="password"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            className="w-full px-3 py-2.5 bg-secondary border border-border rounded-xl text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-colors"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-muted-foreground mb-1">Подтвердить пароль</label>
                        <input
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            className="w-full px-3 py-2.5 bg-secondary border border-border rounded-xl text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary transition-colors"
                            required
                        />
                    </div>

                    {error && (
                        <div className="text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                            {error}
                        </div>
                    )}
                    {success && (
                        <div className="text-sm text-green-500 bg-green-500/10 border border-green-500/20 rounded-lg px-3 py-2 flex items-center gap-2">
                            <Check className="w-4 h-4" />
                            {success}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        className="px-5 py-2.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                    >
                        {loading ? 'Сохраняем...' : 'Сменить пароль'}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default Profile;
