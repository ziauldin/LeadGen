import type { MetadataRoute } from "next";
import { SITE } from "@/lib/marketing";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // The signed-in app and auth flows aren't useful in search results.
        disallow: ["/dashboard", "/leads", "/companies", "/campaigns", "/approvals", "/replies", "/settings", "/admin", "/api/", "/impersonate", "/invite", "/reset-password", "/verify-email"],
      },
    ],
    sitemap: `${SITE.url}/sitemap.xml`,
  };
}
