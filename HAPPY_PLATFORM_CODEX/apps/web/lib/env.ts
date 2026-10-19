export const env = {
  apiBaseUrl:
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1",
  environment: process.env.NEXT_PUBLIC_APP_ENV ?? "development",
  releaseVersion: process.env.NEXT_PUBLIC_RELEASE_VERSION ?? "1.0.0-rc.1",
};
