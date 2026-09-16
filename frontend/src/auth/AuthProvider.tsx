import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { loginRequest, registerRequest } from '../api/client';
import { clearToken, getToken, setToken } from '../api/auth';
import { AuthContext } from './context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());

  const login = useCallback(async (email: string, password: string) => {
    const response = await loginRequest({ email, password });
    setToken(response.access_token);
    setTokenState(response.access_token);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const response = await registerRequest({ email, password });
    setToken(response.access_token);
    setTokenState(response.access_token);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
  }, []);

  const value = useMemo(
    () => ({ token, isAuthenticated: token !== null, login, register, logout }),
    [token, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
