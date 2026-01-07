import { createContext, useContext, useEffect, useState } from "react";
import { fetchMe, Me } from "../api/me";
import { supabase } from "../auth/supabaseClient";

type MeState = {
  me: Me | null;
  loading: boolean;
  error: string | null;
};

const MeContext = createContext<MeState>({
  me: null,
  loading: true,
  error: null,
});

export function MeProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMe = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMe();
      setMe(data);
    } catch (e: any) {
      // If 401, user is not authenticated - this is expected
      if (e?.response?.status === 401) {
        setMe(null);
        setError(null);
      } else {
        setError(e?.message ?? "Failed to load /me");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial load
    loadMe();

    // Listen for auth state changes to refresh /me
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        // User logged in - fetch /me
        loadMe();
      } else {
        // User logged out - clear /me
        setMe(null);
        setLoading(false);
        setError(null);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  return (
    <MeContext.Provider value={{ me, loading, error }}>
      {children}
    </MeContext.Provider>
  );
}

export function useMe() {
  return useContext(MeContext);
}

