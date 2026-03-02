import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthUser {
    id: number;
    username: string;
}

interface AuthState {
    token: string | null;
    user: AuthUser | null;
    login: (token: string, user: AuthUser) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            token: null,
            user: null,
            login: (token, user) => set({ token, user }),
            logout: () => set({ token: null, user: null }),
        }),
        { name: 'pt-auth' }
    )
);
