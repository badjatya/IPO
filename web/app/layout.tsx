import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "IPO Research",
  description: "Research on Indian mainboard IPOs",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {children}
        <footer>
          <p>Research, not investment advice.</p>
        </footer>
      </body>
    </html>
  );
}
