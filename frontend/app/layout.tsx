import type { Metadata } from "next";
import Link from "next/link";
import { ActingAsPicker, ActingAsProvider, ApiStatus } from "./acting-as";
import "./globals.css";

export const metadata: Metadata = {
  title: "ServiceOps Workbench",
  description: "Service requests from intake to a human-approved action, with an audit trail.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ActingAsProvider>
          <header className="top">
            <Link href="/" className="brand">
              ServiceOps Workbench
            </Link>
            <nav>
              <Link href="/">Requests</Link>
              <Link href="/audit">Audit log</Link>
            </nav>
            <ActingAsPicker />
          </header>
          <main>
            <ApiStatus />
            {children}
          </main>
          <footer>Personal learning project. Every person and request here is made up.</footer>
        </ActingAsProvider>
      </body>
    </html>
  );
}
