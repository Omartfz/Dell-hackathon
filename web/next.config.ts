import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The parsers load their own workers and binaries at runtime, so let Node
  // resolve them from node_modules instead of bundling them into a chunk.
  serverExternalPackages: ["pdfjs-dist", "mammoth", "xlsx"],
  // The agent contract for this repo lives in the root CLAUDE.md.
  agentRules: false,
};

export default nextConfig;
