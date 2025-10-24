import axios from "axios";

const apiToken = import.meta.env.VITE_CONFIG_API_TOKEN;
const baseURL = import.meta.env.VITE_CONFIG_API_URL ?? "http://127.0.0.1:8080";

export const api = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json"
  }
});

api.interceptors.request.use((config) => {
  if (apiToken) {
    config.headers["x-api-token"] = apiToken;
  }
  return config;
});

export const fetchConfig = async () => {
  const { data } = await api.get("/config");
  return data;
};

export const updateConfig = async (payload) => {
  const { data } = await api.put("/config", payload);
  return data;
};

export const patchSection = async ({ section, payload }) => {
  const { data } = await api.patch(`/config/${section}`, payload);
  return data;
};

export const fetchPreferences = async (sessionId) => {
  const { data } = await api.get(`/sessions/${sessionId}/preferences`);
  return data.preferences;
};

export const setPreference = async ({ sessionId, key, value }) => {
  const { data } = await api.put(`/sessions/${sessionId}/preferences/${key}`, {
    value
  });
  return data.preferences;
};

export const fetchSafetyLog = async (limit = 100) => {
  const { data } = await api.get("/safety/log", { params: { limit } });
  return data.entries;
};

export const fetchToolingConsent = async () => {
  const { data } = await api.get("/tooling/consent");
  return data;
};
