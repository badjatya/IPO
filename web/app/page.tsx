import { PRODUCT_NAME } from "@/lib/site";

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{PRODUCT_NAME}</h1>
    </main>
  );
}
