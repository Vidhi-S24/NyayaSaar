"use client";

/**
 * AuthProvider — client-side session state backed by the FastAPI JWT API.
 *
 * The bearer token is kept in localStorage and injected into every API call
 * by the api-client. Case data is protected server-side; this provider only
 * manages UI state (who is signed in, and whether we're still checking).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import type { User } from "@nyayasaar/shared";
import {
  setApiAuthToken,
  setUnauthorizedHandler,
} from "@/lib/api-client";
import {
  fetchMe,
  loadStoredToken,
  login as loginApi,
  register as registerApi,
  storeToken,
} from "@/lib/api/auth";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName?: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();
  const mounted = useRef(true);

  const clearSession = useCallback(() => {
    setApiAuthToken(null);
    storeToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  // Register the global 401 handler once.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSession();
    });
    return () => {
      mounted.current = false;
      setUnauthorizedHandler(null);
    };
  }, [clearSession]);

  // Restore session on first mount.
  useEffect(() => {
    const token = loadStoredToken();
    if (!token) {
      setStatus("unauthenticated");
      return;
    }
    setApiAuthToken(token);
    fetchMe()
      .then((envelope) => {
        if (!mounted.current) return;
        setUser(envelope.data ?? null);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!mounted.current) return;
        clearSession();
      });
  }, [clearSession]);

  const applySession = useCallback(
    (token: string, profile: User) => {
      setApiAuthToken(token);
      storeToken(token);
      setUser(profile);
      setStatus("authenticated");
    },
    [],
  );

  const signIn = useCallback(
    async (email: string, password: string) => {
      const envelope = await loginApi(email, password);
      const token = envelope.data?.access_token;
      if (!token) throw new Error("Sign-in failed — no token returned");
      setApiAuthToken(token); // needed before /auth/me
      const me = await fetchMe();
      if (!me.data) throw new Error("Sign-in failed — no profile returned");
      applySession(token, me.data);
      router.push("/dashboard");
    },
    [applySession, router],
  );

  const signUp = useCallback(
    async (email: string, password: string, fullName?: string) => {
      const envelope = await registerApi(email, password, fullName);
      const token = envelope.data?.access_token;
      if (!token) throw new Error("Registration failed — no token returned");
      setApiAuthToken(token);
      const me = await fetchMe();
      if (!me.data) throw new Error("Registration failed — no profile returned");
      applySession(token, me.data);
      router.push("/dashboard");
    },
    [applySession, router],
  );

  const signOut = useCallback(() => {
    clearSession();
    router.push("/signin");
  }, [clearSession, router]);

  return (
    <AuthContext.Provider value={{ status, user, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
