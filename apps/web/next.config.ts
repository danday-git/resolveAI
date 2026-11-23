import type { NextConfig } from "next";

const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Local models on a CPU can take minutes; the default 30 s proxy timeout hangs up mid-answer.
  experimental: { proxyTimeout: 300_000 },
  // The browser only talks to this origin; the API URL and any credentials stay server-side.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
