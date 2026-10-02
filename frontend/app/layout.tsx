import type { Metadata } from "next";
import type { ReactNode } from "react";
import Providers from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "PreVisit MVP",
  description: "سیستم مصاحبه پزشکی هوشمند پیش از ویزیت",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <body className="page-shell">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
