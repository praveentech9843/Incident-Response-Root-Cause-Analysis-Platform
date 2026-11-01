import React, { useEffect, useState, type ReactNode } from "react";
import {
  type User,
  type LoginPayload,
  type RegisterPayload,
  loginUser,
  registerUser,
  fetchCurrentUser,
  logoutUser,
  getAuthToken,
  setAuthToken,
} from "../services/api";
import { AuthContext } from "./authContextDef";

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(getAuthToken());
  const [loading, setLoading] = useState<boolean>(true);

  const refreshUser = async () => {
    const curToken = getAuthToken();
    if (!curToken) {
      setUser(null);
      setTokenState(null);
      setLoading(false);
      return;
    }
    try {
      const profile = await fetchCurrentUser();
      setUser(profile);
      setTokenState(curToken);
    } catch {
      // Invalidate on expired/invalid token
      setAuthToken(null);
      setUser(null);
      setTokenState(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    const curToken = getAuthToken();
    if (!curToken) {
      Promise.resolve().then(() => {
        if (isMounted) {
          setUser(null);
          setTokenState(null);
          setLoading(false);
        }
      });
      return () => {
        isMounted = false;
      };
    }

    fetchCurrentUser()
      .then((profile) => {
        if (isMounted) {
          setUser(profile);
          setTokenState(curToken);
          setLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setAuthToken(null);
          setUser(null);
          setTokenState(null);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const login = async (payload: LoginPayload) => {
    const tokens = await loginUser(payload);
    setTokenState(tokens.access_token);
    const profile = await fetchCurrentUser();
    setUser(profile);
  };

  const register = async (payload: RegisterPayload): Promise<User> => {
    return registerUser(payload);
  };

  const logout = async () => {
    await logoutUser();
    setUser(null);
    setTokenState(null);
  };

  const role = user?.role || null;
  const isAdmin = role === "ADMIN";
  const isDeveloper = role === "DEVELOPER" || role === "ADMIN";
  const isViewer = role === "VIEWER";
  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        role,
        isAdmin,
        isDeveloper,
        isViewer,
        isAuthenticated,
        loading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
