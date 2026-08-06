import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: `${process.env.NEXT_PUBLIC_ORG_NAME || "Org"} — Secure Agent Portal`,
  description: "Secure cross-org agent communication",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const theme = process.env.NEXT_PUBLIC_ORG_THEME || "blue";
  return (
    <html lang="en" data-theme={theme}>
      <body>{children}</body>
    </html>
  );
}
