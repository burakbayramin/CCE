import type { NextConfig } from "next";

const config: NextConfig = {
  output: process.env.CCE_STANDALONE_BUILD === "1" ? "standalone" : undefined,
  poweredByHeader: false,
};

export default config;
