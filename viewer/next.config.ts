import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false, // don't auto-generate AGENTS.md/CLAUDE.md; this repo has its own conventions
};

export default nextConfig;
