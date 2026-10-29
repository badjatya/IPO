import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

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
    <html lang="en" className={cn("font-sans", geist.variable)}>
      <body className="flex min-h-svh flex-col">
        <div className="flex-1">{children}</div>
        <footer className="border-t px-4 py-3 text-center text-xs text-muted-foreground">
          Research, not investment advice.
        </footer>
      </body>
    </html>
  );
}
