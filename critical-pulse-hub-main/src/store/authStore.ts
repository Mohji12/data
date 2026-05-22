import { create } from 'zustand';
import { apiClient } from '@/lib/apiClient';

const STUDENT_TOKEN_KEY = 'access_token';
const ADMIN_TOKEN_KEY = 'admin_access_token';

export interface User {
  id: string;
  name: string;
  email: string;
  role: 'student' | 'admin';
  /** From `admin` table when role is admin (e.g. `techadmin`). */
  userType?: string | null;
  initials: string;
  course?: string;
  expiresAt?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  initialized: boolean;
  login: (email: string, password?: string) => Promise<boolean>;
  /** Admin table login only (stores admin bearer token). */
  loginAsAdmin: (username: string, password: string) => Promise<boolean>;
  register: (data: Record<string, string>) => Promise<boolean>;
  logout: () => Promise<void>;
  initialize: () => Promise<void>;
}

function mapAdminMe(res: {
  admin_id: number;
  name?: string | null;
  username: string;
  user_type?: string | null;
}): User {
  return {
    id: String(res.admin_id),
    name: res.name || 'Admin',
    email: res.username,
    role: 'admin',
    userType: res.user_type ?? null,
    initials: (res.name || res.username || 'AD').slice(0, 2).toUpperCase(),
  };
}

async function tryHydrateAdmin(): Promise<User | null> {
  try {
    const me = await apiClient('/admin/auth/me');
    if (me?.access_token) {
      sessionStorage.setItem(ADMIN_TOKEN_KEY, me.access_token);
    }
    return mapAdminMe(me);
  } catch {
    return null;
  }
}

async function tryHydrateStudent(): Promise<User | null> {
  try {
    const response = await apiClient('/dashboard/summary');
    return {
      id: String(response.user_id),
      name: response.name || 'User',
      email: response.email,
      role: 'student',
      userType: null,
      initials: (response.name || 'U').substring(0, 2).toUpperCase(),
      course: response.subscription,
    };
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!(sessionStorage.getItem(ADMIN_TOKEN_KEY) || localStorage.getItem(STUDENT_TOKEN_KEY)),
  initialized: false,

  loginAsAdmin: async (username: string, password: string) => {
    const adminRes = await apiClient('/admin/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username: username.trim(), password }),
    });
    if (adminRes.access_token) {
      sessionStorage.setItem(ADMIN_TOKEN_KEY, adminRes.access_token);
    }
    set({
      isAuthenticated: true,
      initialized: true,
      user: mapAdminMe(adminRes),
    });
    return true;
  },

  login: async (email: string, password?: string) => {
    try {
      const response = await apiClient('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });

      if (response.access_token) {
        localStorage.setItem(STUDENT_TOKEN_KEY, response.access_token);
      }

      set({
        isAuthenticated: true,
        initialized: true,
        user: {
          id: String(response.id),
          name: response.name || 'User',
          email: response.email,
          role: 'student',
          userType: null,
          initials: (response.name || email).substring(0, 2).toUpperCase(),
          course: response.subscription,
        },
      });
      return true;
    } catch {
      // Student failed: try admin with same identifier (username often has no @)
      try {
        await useAuthStore.getState().loginAsAdmin(email.trim(), password || '');
        return true;
      } catch (adminErr) {
        console.error('Login failed:', adminErr);
        throw adminErr instanceof Error ? adminErr : new Error('Login failed');
      }
    }
  },

  register: async (data: Record<string, any>) => {
    try {
      const response = await apiClient('/registration/init', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      return response;
    } catch (error) {
      console.error('Registration failed:', error);
      throw error;
    }
  },

  logout: async () => {
    const adminToken = sessionStorage.getItem(ADMIN_TOKEN_KEY);
    const studentToken = localStorage.getItem(STUDENT_TOKEN_KEY);
    const token = adminToken || studentToken;
    if (token) {
      try {
        const adminUser = useAuthStore.getState().user?.role === 'admin';
        if (adminUser) {
          await apiClient('/admin/auth/logout', { method: 'POST' });
        }
      } catch {
        /* ignore */
      }
    }
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.removeItem(STUDENT_TOKEN_KEY);
    set({ user: null, isAuthenticated: false, initialized: true });
  },

  initialize: async () => {
    const adminToken = sessionStorage.getItem(ADMIN_TOKEN_KEY);
    const studentToken = localStorage.getItem(STUDENT_TOKEN_KEY);
    if (!adminToken && !studentToken) {
      set({ user: null, isAuthenticated: false, initialized: true });
      return;
    }
    try {
      // If this tab has an admin token, keep the tab in admin context only.
      if (adminToken) {
        const adminUser = await tryHydrateAdmin();
        if (adminUser) {
          set({ isAuthenticated: true, user: adminUser, initialized: true });
          return;
        }
        sessionStorage.removeItem(ADMIN_TOKEN_KEY);
        set({ user: null, isAuthenticated: false, initialized: true });
        return;
      }

      if (studentToken) {
        const studentUser = await tryHydrateStudent();
        if (studentUser) {
          set({ isAuthenticated: true, user: studentUser, initialized: true });
          return;
        }
      }
      localStorage.removeItem(STUDENT_TOKEN_KEY);
      set({ user: null, isAuthenticated: false, initialized: true });
    } catch (e) {
      console.error('Session invalid', e);
      sessionStorage.removeItem(ADMIN_TOKEN_KEY);
      localStorage.removeItem(STUDENT_TOKEN_KEY);
      set({ user: null, isAuthenticated: false, initialized: true });
    }
  },
}));

export function useIsTechAdmin(): boolean {
  const u = useAuthStore((s) => s.user);
  return u?.role === 'admin' && (u.userType || '').toLowerCase() === 'techadmin';
}
