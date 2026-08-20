import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MafiaSim Viewer",
  description: "Replay viewer for LLM Mafia games",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
