# syntax=docker/dockerfile:1.6

# ---------- Stage 1: build the Vite bundle ----------
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .

# Empty API base => the bundled app calls /api/... on its own origin, which
# nginx (next stage) reverse-proxies to the backend service. This keeps
# cookies same-origin and sidesteps CORS entirely.
ENV VITE_API_BASE=""
RUN npm run build

# ---------- Stage 2: nginx static server + reverse proxy ----------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx:alpine's default CMD already runs nginx in the foreground.
