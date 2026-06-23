FROM node:22-bookworm-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./

EXPOSE 5173

CMD ["sh", "-c", "if [ ! -x node_modules/.bin/vite ]; then echo 'Installing frontend dependencies...'; npm ci --no-audit --no-fund; fi && exec npm run dev -- --host 0.0.0.0 --port 5173"]
