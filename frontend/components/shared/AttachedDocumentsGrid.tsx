"use client";

import { useMemo } from "react";
import { ImageIcon } from "lucide-react";
import ClinicalDocumentViewer from "@/components/shared/ClinicalDocumentViewer";
import { fileDownloadUrl } from "@/lib/files";

export type AttachedDocumentFile = {
  id: number;
  filename: string;
  mime_type: string;
  url?: string;
};

type AttachedDocumentsGridProps = {
  files: AttachedDocumentFile[];
};

function fileHref(file: AttachedDocumentFile): string {
  return file.url ? `/api/proxy${file.url}` : fileDownloadUrl(file.id);
}

export default function AttachedDocumentsGrid({ files }: AttachedDocumentsGridProps) {
  const images = useMemo(
    () => files.filter((f) => f.mime_type.startsWith("image/")),
    [files],
  );

  if (images.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-trust">
        <ImageIcon className="h-5 w-5" />
        <h3 className="text-xl font-bold text-slate-900">تصاویر و مدارک پیوست</h3>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {images.map((img) => (
          <ClinicalDocumentViewer
            key={img.id}
            documentId={img.id}
            imageUrl={fileHref(img)}
            documentTitle={img.filename}
          />
        ))}
      </div>
    </div>
  );
}
