import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Municipal Budget Visualization",
  description: "Greek municipal budget and technical program viewer",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="el">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: "1200px", margin: "0 auto" }}>
        <header style={{ marginBottom: "2rem", borderBottom: "1px solid #ccc", paddingBottom: "1rem" }}>
          <h1 style={{ margin: 0 }}>Municipal Budget Viewer</h1>
          <nav style={{ marginTop: "0.5rem" }}>
            <a href="/" style={{ marginRight: "1rem" }}>Documents</a>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
