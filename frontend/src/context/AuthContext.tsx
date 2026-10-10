"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { jwtDecode } from "jwt-decode";
import { GoogleOAuthProvider } from "@react-oauth/google";

export interface GoogleUser {
  sub: string;
  name: string;
  email: string;
  picture?: string;
}

interface AuthContextType {
  user: GoogleUser | null;
  token: string | null;
  login: (credential: string) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  login: () => {},
  logout: () => {},
  isLoading: true,
});

const NEON_AUTH_URL = "https://ep-mute-wave-axp0uhye.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth";
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<GoogleUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    try {
      const savedToken = localStorage.getItem("truthchain_auth_token");
      if (savedToken) {
        const decoded = jwtDecode<GoogleUser>(savedToken);
        setToken(savedToken);
        setUser(decoded);
      }
    } catch {
      localStorage.removeItem("truthchain_auth_token");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = (credential: string) => {
    try {
      const decoded = jwtDecode<GoogleUser>(credential);
      setToken(credential);
      setUser(decoded);
      localStorage.setItem("truthchain_auth_token", credential);
      
      // Optionally sync auth session to Neon Auth endpoint
      fetch(`${NEON_AUTH_URL}/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: credential, user: decoded }),
      }).catch(() => {});
    } catch (err) {
      console.error("Authentication error:", err);
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("truthchain_auth_token");
  };

  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <AuthContext.Provider value={{ user, token, login, logout, isLoading }}>
        {children}
      </AuthContext.Provider>
    </GoogleOAuthProvider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
