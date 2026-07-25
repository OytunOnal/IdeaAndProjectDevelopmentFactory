"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { supabase, authEnabled } from "@/lib/supabase";
import type { User, Session } from "@supabase/supabase-js";

// Local stand-in used when Supabase is not configured (demo mode)
const DEMO_USER = {
  id: "demo-user",
  email: "demo@projectfactory.local",
  app_metadata: {},
  user_metadata: { name: "Demo User" },
  aud: "authenticated",
  created_at: "",
} as User;

interface AuthContext {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContext>({
  user: null,
  session: null,
  loading: true,
  signOut: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Demo mode (no Supabase configured): start signed-in as a local user
  const [user, setUser] = useState<User | null>(authEnabled ? null : DEMO_USER);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(authEnabled);

  useEffect(() => {
    if (!authEnabled) return;

    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
        setLoading(false);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    if (!authEnabled) return;
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider value={{ user, session, loading, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
