import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output bundles everything Vercel needs into .next/standalone,
  // avoiding the immutable static file upload / preview comment patching conflict.
  output: "standalone",
  // Disable telemetry prompt in CI and Vercel build logs
  env: {
    NEXT_TELEMETRY_DISABLED: "1",
  },
};

export default nextConfig;
