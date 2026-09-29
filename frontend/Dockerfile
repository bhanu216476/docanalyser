# ==============================================================================
# DocAnalyser Frontend - Multi-Stage Production Dockerfile
# ==============================================================================

# Stage 1: Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies using package-lock.json for reproducible builds
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit

# Copy source code and build production bundle
COPY . .

ARG VITE_API_URL=http://localhost:8080
ARG VITE_RAG_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_RAG_URL=$VITE_RAG_URL

RUN npm run build

# Stage 2: Production runtime with lightweight Nginx
FROM nginx:1.27-alpine

# Copy built static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration with SPA fallback and healthcheck
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose container port
EXPOSE 5173

# Container healthcheck using Nginx health endpoint
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:5173/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
