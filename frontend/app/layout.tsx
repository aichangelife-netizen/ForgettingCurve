import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ForgettingCurve",
  description: "Local research MVP for Korean-to-English vocabulary recall.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
