// src/api/client.ts
import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true,  // el navegador manda las cookies httpOnly en cada request — sin esto, no viajan
});

// Ya no hace falta interceptor de request inyectando el token —
// el navegador lo hace solo, porque es una cookie.

let isRefreshing = false;
let refreshQueue: (() => void)[] = [];

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      if (isRefreshing) {
        return new Promise((resolve) => {
          refreshQueue.push(() => resolve(client(originalRequest)));
        });
      }

      isRefreshing = true;
      try {
        // Sin body — el refresh_token viaja solo, como cookie httpOnly
        await axios.post(`${import.meta.env.VITE_API_URL}/auth/refresh`, {}, { withCredentials: true });
        refreshQueue.forEach((cb) => cb());
        refreshQueue = [];
        return client(originalRequest);
      } catch {
        window.location.href = "/login";
        return Promise.reject(error);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export default client;