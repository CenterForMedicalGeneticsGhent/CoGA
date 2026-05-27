FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

FROM deps AS build
ARG VITE_API_BASE_URL
ARG VITE_GITHUB_REPOSITORY_URL
ARG VITE_GITHUB_RELEASES_URL
ARG VITE_GITHUB_ISSUES_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_GITHUB_REPOSITORY_URL=${VITE_GITHUB_REPOSITORY_URL} \
    VITE_GITHUB_RELEASES_URL=${VITE_GITHUB_RELEASES_URL} \
    VITE_GITHUB_ISSUES_URL=${VITE_GITHUB_ISSUES_URL}
COPY . .
RUN npm run build

FROM node:20-alpine AS production
ENV NODE_ENV=production
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
COPY --from=build /app/server.mjs ./server.mjs
EXPOSE 3000
CMD ["node", "server.mjs"]
