import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadProjectEnvironment } from "@happy/config/env";

const appDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(appDirectory, "../..");
loadProjectEnvironment(projectRoot, appDirectory);

/** @type {import('next').NextConfig} */
const nextConfig = {
  distDir:
    process.env.HAPPY_LOCAL_PRODUCTION === "1"
      ? ".next-local-production"
      : ".next",
  typedRoutes: true,
  typescript: {
    tsconfigPath:
      process.env.HAPPY_LOCAL_PRODUCTION === "1"
        ? "tsconfig.local-production.json"
        : "tsconfig.json",
  },
  devIndicators: false,
  output: process.platform === "win32" ? undefined : "standalone",
  outputFileTracingRoot: projectRoot,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; form-action 'self'; img-src 'self' data:; font-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'",
          },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination:
          (process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000") +
          "/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
