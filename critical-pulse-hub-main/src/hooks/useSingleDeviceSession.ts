import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { SESSION_INVALIDATED_EVENT, isSessionInvalidError } from '@/lib/sessionEvents';
import { useAuthStore } from '@/store/authStore';

const SESSION_POLL_MS = 5000;

/**
 * Enforces one active student session per account.
 * When the user logs in elsewhere, this device is signed out within ~5 seconds.
 */
export function useSingleDeviceSession() {
  const navigate = useNavigate();
  const { user, logout, isAuthenticated } = useAuthStore();
  const signingOutRef = useRef(false);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'student') return;

    const signOutOtherDevice = async (message?: string) => {
      if (signingOutRef.current) return;
      signingOutRef.current = true;
      toast.error(message || 'You signed in on another device. Signing out…');
      await logout();
      navigate('/login', { replace: true });
    };

    const checkSession = async () => {
      try {
        await apiClient('/auth/session/check');
      } catch (error) {
        if (isSessionInvalidError(error)) {
          await signOutOtherDevice(
            typeof error === 'object' && error instanceof Error
              ? error.message
              : 'You signed in on another device. Signing out…',
          );
        }
      }
    };

    const onInvalidated = () => {
      void signOutOtherDevice('You signed in on another device. Signing out…');
    };

    void checkSession();
    const intervalId = window.setInterval(() => {
      void checkSession();
    }, SESSION_POLL_MS);
    window.addEventListener(SESSION_INVALIDATED_EVENT, onInvalidated);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener(SESSION_INVALIDATED_EVENT, onInvalidated);
      signingOutRef.current = false;
    };
  }, [isAuthenticated, user?.role, logout, navigate]);
}
