import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

/** Legacy link route — password reset is OTP-based on /forgot-password. */
export default function ResetPassword() {
  const navigate = useNavigate();

  useEffect(() => {
    navigate('/forgot-password', { replace: true });
  }, [navigate]);

  return null;
}
