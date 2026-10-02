import type { AxiosProgressEvent } from "axios";
import type { Demographics } from "./intake";
import type { MedicalOverview } from "./pmh/types";
import { apiClient } from "./api";

export type MedicationSearchResult = {
  id: number;
  display_name: string;
  brand_name?: string | null;
  brand_name_fa: string | null;
  brand_name_en: string | null;
  generic_name?: string | null;
  generic_name_en: string | null;
  generic_slug?: string | null;
  brand_slug?: string | null;
  form: string | null;
  strength: string | null;
  manufacturer: string | null;
  company_name?: string | null;
  company_slug?: string | null;
  dose_unit: string;
};

export type MedicationSearchResponse = {
  query: string;
  results: MedicationSearchResult[];
};

export const frontendApi = {
  register: (payload: { email: string; password: string; full_name: string; role: string }) =>
    apiClient.post("/auth/register", payload),
  login: (payload: { email: string; password: string }) => apiClient.post("/auth/login", payload),
  logout: () => apiClient.post("/auth/logout"),
  listSessions: () => apiClient.get("/proxy/api/chat/sessions"),
  createSession: (payload: { initial_complaint: string }) => apiClient.post("/proxy/api/chat/session", payload),
  chatHistory: (sessionId: string) => apiClient.get(`/proxy/api/chat/${sessionId}`),
  sendMessage: (sessionId: string, payload: { content: string }) => apiClient.post(`/proxy/api/chat/${sessionId}`, payload),
  uploadFile: (
    sessionId: string,
    formData: FormData,
    onUploadProgress?: (event: AxiosProgressEvent) => void,
  ) => {
    return apiClient.post(`/proxy/api/files/${sessionId}/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress,
    });
  },
  listFiles: (sessionId: string) => apiClient.get(`/proxy/api/files/${sessionId}/list`),
  getDocumentOcr: (documentId: number) =>
    apiClient.get<{ ocr_text: string }>(`/proxy/api/documents/${documentId}/ocr`),
  unlinkFile: (sessionId: string, fileId: number) =>
    apiClient.patch(`/proxy/api/files/${sessionId}/files/${fileId}`, { condition_id: null }),
  summary: (sessionId: string) => apiClient.get(`/proxy/api/summary/${sessionId}`),
  submitSession: (sessionId: string) => apiClient.post(`/proxy/api/chat/${sessionId}/submit`),
  getIntake: (sessionId: string) => apiClient.get(`/proxy/api/intake/${sessionId}`),
  saveLayer1: (sessionId: string, payload: Demographics) =>
    apiClient.post(`/proxy/api/intake/${sessionId}/layer1`, payload),
  generateLayer2: (sessionId: string) => apiClient.post(`/proxy/api/intake/${sessionId}/layer2/generate`),
  saveLayer2Answer: (sessionId: string, payload: { question_id: string; answer: string }) =>
    apiClient.post(`/proxy/api/intake/${sessionId}/layer2/answer`, payload),
  generateLayer3: (sessionId: string) => apiClient.post(`/proxy/api/intake/${sessionId}/layer3/generate`),
  searchMedications: (query: string, limit = 20) =>
    apiClient.get<MedicationSearchResponse>("/proxy/api/medications/search", {
      params: { query, limit },
    }),
  saveLayer4: (sessionId: string, payload: MedicalOverview) =>
    apiClient.post(`/proxy/api/intake/${sessionId}/layer4`, payload),
  submitIntake: (sessionId: string) => apiClient.post(`/proxy/api/intake/${sessionId}/submit`),
  getPatientProfile: () => apiClient.get("/proxy/api/patients/me/profile"),
  retrySoap: (sessionId: string) => apiClient.post(`/proxy/api/summary/${sessionId}/retry-soap`),
  getPatientOverview: (patientId: string) => apiClient.get(`/proxy/api/pmh/overview/${patientId}`),
  getMyConsents: () => apiClient.get("/proxy/api/consent/me"),
  grantConsent: (payload: { consent_key: string; policy_version?: string }) =>
    apiClient.post("/proxy/api/consent/grant", payload),
  withdrawConsent: (payload: { consent_key: string }) =>
    apiClient.post("/proxy/api/consent/withdraw", payload),
};
