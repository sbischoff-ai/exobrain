FROM node:20-alpine AS builder
WORKDIR /app
COPY apps/assistant-frontend/package.json ./
RUN npm install
COPY apps/assistant-frontend .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json ./package.json
RUN npm install --omit=dev
EXPOSE 3000
CMD ["node", "build"]
