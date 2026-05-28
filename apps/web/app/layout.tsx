import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "artemis · climb",
  description: "Strava for indoor bouldering — pose-driven climb stats.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
