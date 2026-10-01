import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Orbit · Operations",
  description: "Enterprise workflows for people and agents.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
