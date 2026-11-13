import type { NextConfig } from "next";

// The browser only ever talks to Next.js. Calls to /api/* are passed on to the
// FastAPI backend, so there's one origin and no CORS setup.
// API_URL is read when the app is built, not when it starts: the rewrite is
// written into the build output.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  devIndicators: false,
  // The container build sets BUILD_STANDALONE=1 to get a self-contained server in
  // .next/standalone with only the packages it uses. `next start` doesn't support
  // that layout, so a normal build leaves it off.
  output: process.env.BUILD_STANDALONE ? "standalone" : undefined,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default config;
