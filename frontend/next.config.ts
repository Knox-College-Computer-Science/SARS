import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["10.7.5.80"],
  experimental: {
    turbopackMemoryLimit: 512,
  },
};

export default nextConfig;