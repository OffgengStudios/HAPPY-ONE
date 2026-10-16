import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "HAPPY Management Platform",
  description: "Programme management platform for HAPPY operations",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}
