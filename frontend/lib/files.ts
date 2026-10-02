/** Browser-facing download URL via the Next.js API proxy to the backend. */
export function fileDownloadUrl(fileId: number): string {
  return `/api/proxy/api/files/download/${fileId}`;
}
