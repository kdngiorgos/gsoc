FROM node:20-alpine AS base

RUN apk add --no-cache openssl

WORKDIR /app
COPY package.json ./
COPY prisma ./prisma
RUN npm install

COPY . .
RUN npx prisma generate
RUN npm run build

EXPOSE 3000
ENV NODE_ENV=production
ENV PRISMA_QUERY_ENGINE_LIBRARY=/app/node_modules/.prisma/client/libquery_engine-linux-musl-openssl-3.0.x.so.node
COPY start.sh ./start.sh
RUN chmod +x ./start.sh
CMD ["./start.sh"]
