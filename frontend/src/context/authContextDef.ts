import { createContext } from "react";
import type {
  User,
  UserRole,
  LoginPayload,
  RegisterPayload,
} from "../services/api";

export interface AuthContextType {
  user: User | null;
  token: string | null;
  role: UserRole | null;
  isAdmin: boolean;
  isDeveloper: boolean;
  isViewer: boolean;
  isAuthenticated: boolean;
  loading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
