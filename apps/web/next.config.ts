import path from "node:path";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Monorepo: trace files from the repository root so the standalone bundle includes workspace packages.
  outputFileTracingRoot: path.join(__dirname, "../../"),
  poweredByHeader: false,
  transpilePackages: ["@2ajar/contracts"],
  // The browser talks to the API through the web origin, so auth cookies are first-party and no CORS is needed.
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${API_INTERNAL_URL}/api/v1/:path*` },
      { source: "/media/:path*", destination: `${API_INTERNAL_URL}/media/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default createNextIntlPlugin("./i18n/request.ts")(nextConfig);
