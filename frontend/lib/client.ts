import type { AxiosProgressEvent } from "axios";
import type { Demographics } from "./intake";
import type { MedicalOverview, PMHSubmission } from "./pmh/types";
import { apiClient } from "./api";

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
  saveLayer4: (sessionId: string, payload: MedicalOverview) =>
    apiClient.post(`/proxy/api/intake/${sessionId}/layer4`, payload),
  submitIntake: (sessionId: string) => apiClient.post(`/proxy/api/intake/${sessionId}/submit`),
  getPatientProfile: () => apiClient.get("/proxy/api/patients/me/profile"),
  updatePatientProfile: (payload: Record<string, unknown>) =>
    apiClient.patch("/proxy/api/patients/me/profile", payload),
  retrySoap: (sessionId: string) => apiClient.post(`/proxy/api/summary/${sessionId}/retry-soap`),
  getPMHSchema: () => apiClient.get("/proxy/api/pmh/schema"),
  submitPMH: (payload: PMHSubmission) => apiClient.post("/proxy/api/pmh/submit", payload),
  getPatientOverview: (patientId: string) => apiClient.get(`/proxy/api/pmh/overview/${patientId}`),
};
