import { render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import Home from "@/app/page";
import RootLayout, { metadata } from "@/app/layout";
import { SiteFooter } from "@/components/site-footer";
import { DISCLAIMER, PRODUCT_NAME } from "@/lib/site";

// next/font only works inside the Next.js compiler.
vi.mock("next/font/google", () => ({
  Geist: () => ({ className: "font-geist", variable: "font-geist-variable" }),
}));

describe("disclaimer", () => {
  it("says the research is not investment advice", () => {
    expect(DISCLAIMER.toLowerCase()).toContain("not investment advice");
  });

  it("is in the footer", () => {
    render(<SiteFooter />);
    expect(screen.getByRole("contentinfo")).toHaveTextContent(DISCLAIMER);
  });

  it("is in the root layout, so every page shows it", () => {
    const html = renderToStaticMarkup(
      <RootLayout>
        <p>any page</p>
      </RootLayout>,
    );
    expect(html).toContain("<p>any page</p>");
    expect(html).toMatch(/<footer[^>]*>Research, not investment advice\.<\/footer>/);
  });
});

describe("home page", () => {
  it("shows the product name as its heading", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(PRODUCT_NAME);
  });

  it("uses the product name as the page title", () => {
    expect(metadata.title).toBe(PRODUCT_NAME);
  });
});
