import type { NextConfig } from "next";

// The browser only ever talks to Next.js. Calls to /api/* are passed on to the
// FastAPI backend, so there's one origin and no CORS setup.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default config;
