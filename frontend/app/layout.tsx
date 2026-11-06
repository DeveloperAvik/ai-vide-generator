import "./globals.css";
import type { Metadata } from "next";
import Shell from "@/components/Shell";
import { THEME_INIT } from "@/components/ThemeToggle";
import { ToastProvider } from "@/components/ui";

export const metadata: Metadata = { title: "AI Video Studio", description: "AI teaching video production dashboard for any subject" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: THEME_INIT }} /></head>
      <body className="font-sans"><ToastProvider><Shell>{children}</Shell></ToastProvider></body>
    </html>
  );
}
