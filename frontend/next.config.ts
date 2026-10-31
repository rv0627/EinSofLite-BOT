import type { NextConfig } from "next";
import { loadEnvConfig } from "@next/env";
import path from "path";

// Load environment variables from the parent directory
loadEnvConfig(path.resolve(process.cwd(), ".."));

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1",
    NEXT_PUBLIC_ADMIN_KEY: process.env.NEXT_PUBLIC_ADMIN_KEY || "CF_3Ixj81GkCrZ1FedgzUrEXuyWsXngd1I5FHv7yx-5KY8wxWqVk8edGaksyahd0",
  },
};

export default nextConfig;
