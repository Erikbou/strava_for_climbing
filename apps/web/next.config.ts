import type { NextConfig } from "next";

const config: NextConfig = {
  experimental: {
    serverActions: { bodySizeLimit: "200mb" },
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos" },
    ],
  },
};

export default config;
