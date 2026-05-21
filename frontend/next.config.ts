import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["10.7.5.80"],
  experimental: {
    turbopackMemoryLimit: 512,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;