import { DISCLAIMER } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="border-t px-4 py-3 text-center text-xs text-muted-foreground">
      {DISCLAIMER}
    </footer>
  );
}
