FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
COPY . .
RUN pnpm install --frozen-lockfile
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_APP_ENV=staging
ARG NEXT_PUBLIC_RELEASE_VERSION=1.0.0-rc.1
ARG API_INTERNAL_URL=http://api:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} NEXT_PUBLIC_APP_ENV=${NEXT_PUBLIC_APP_ENV} NEXT_PUBLIC_RELEASE_VERSION=${NEXT_PUBLIC_RELEASE_VERSION} API_INTERNAL_URL=${API_INTERNAL_URL}
RUN pnpm --filter web build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -g 10001 happy && adduser -D -u 10001 -G happy happy
COPY --from=build --chown=happy:happy /app/apps/web/.next/standalone ./
COPY --from=build --chown=happy:happy /app/apps/web/.next/static ./apps/web/.next/static
USER happy
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
