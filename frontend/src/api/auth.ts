// src/api/auth.ts — sin cambios de firma, solo se simplifica login()
import client from "./client";
export const login = (email: string, password: string) => {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);
  return client.post("/auth/login", formData, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
};