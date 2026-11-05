# Build context: repository root.
FROM node:22-alpine AS deps
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/contracts/package.json packages/contracts/
COPY tests/e2e/package.json tests/e2e/
RUN pnpm install --frozen-lockfile --filter @2ajar/web...

FROM deps AS build
COPY apps/web apps/web
COPY packages/contracts packages/contracts
# Rewrites (/api/v1, /media -> API) are resolved at build time, so the API URL must be known here.
ARG API_INTERNAL_URL=http://localhost:8000
ENV NEXT_TELEMETRY_DISABLED=1 API_INTERNAL_URL=${API_INTERNAL_URL}
RUN pnpm --filter @2ajar/web build

FROM node:22-alpine AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /repo/apps/web/.next/standalone ./
COPY --from=build --chown=app:app /repo/apps/web/.next/static ./apps/web/.next/static
USER app
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
