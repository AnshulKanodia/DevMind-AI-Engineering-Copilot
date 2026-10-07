import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DevMind | AI Engineering Copilot",
  description: "Autonomous code Q&A, SAST security review, test generation, and PR automation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#090d16] text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
