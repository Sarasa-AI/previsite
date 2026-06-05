import ProtectedRoute from "@/components/ProtectedRoute";
import FileUploader from "@/components/ui/FileUploader";

// نکته آموزشی:
// این route به‌صورت Server Component باقی مانده تا فقط leaf تعاملی یعنی `FileUploader`
// client باشد. این الگو به SEO و TTFB کمک می‌کند و سطح hydration را کوچک نگه می‌دارد.
export default function UploadPage({ params }: { params: { sessionId: string } }) {
  return (
    <ProtectedRoute>
      <main className="page-container">
        <FileUploader sessionId={params.sessionId} />
      </main>
    </ProtectedRoute>
  );
}
