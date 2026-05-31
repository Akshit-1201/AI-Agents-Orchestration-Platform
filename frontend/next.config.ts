import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app (a stray lockfile sits one level up).
  turbopack: { root: __dirname },
  // Emit a self-contained server bundle (.next/standalone) for a minimal Docker image.
  output: "standalone",
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
