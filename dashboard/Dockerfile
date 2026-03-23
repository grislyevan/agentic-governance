FROM node:20-alpine AS build

WORKDIR /build

# Branding colors needed by tailwind.config.cjs (require('../branding/tailwind-colors'))
COPY branding/tailwind-colors.js ./branding/tailwind-colors.js

COPY dashboard/package.json dashboard/package-lock.json ./dashboard/
WORKDIR /build/dashboard
RUN npm ci
COPY dashboard/ .
RUN npm run build

FROM node:20-alpine

WORKDIR /app
COPY --from=build /build/dashboard/dist ./dist
COPY --from=build /build/dashboard/server.js ./server.js
COPY --from=build /build/dashboard/package.json ./package.json

RUN adduser -D -H appuser
USER appuser

EXPOSE 3001

CMD ["node", "server.js"]
