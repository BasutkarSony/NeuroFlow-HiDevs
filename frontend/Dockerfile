FROM node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
RUN groupadd -r neuroflow && useradd -r -g neuroflow neuroflow
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
RUN chown -R neuroflow:neuroflow /app
USER neuroflow
EXPOSE 3000
CMD ["node", "server.js"]
