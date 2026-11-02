import type { NextConfig } from "next";
import path from "node:path";

const config: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  turbopack: { root: path.join(__dirname, "../..") },
};

export default config;
