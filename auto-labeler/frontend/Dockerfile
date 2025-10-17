# syntax=docker/dockerfile:1
FROM node:20-alpine AS base
WORKDIR /app
ENV NODE_ENV=development
# Set your sub-route (adjust if serving at root)
ARG VITE_BASE_PATH=/dataset-curation/auto-labeler-labeler/
ENV VITE_BASE_PATH=$VITE_BASE_PATH
# Install deps
COPY frontend/package*.json ./
RUN npm ci
# App source
COPY frontend/ ./

# ---- Dev image (runs Vite dev server) ----
FROM base AS dev
ENV HOST=0.0.0.0
EXPOSE 5173
# package.json "dev": "vite --host 0.0.0.0"
CMD ["npm","run","dev"]


#FROM node:20-alpine AS build
#WORKDIR /app
#
#ARG VITE_BASE_PATH=/dataset-curation/auto-labeler-labeler/
#ENV VITE_BASE_PATH=$VITE_BASE_PATH
#
#COPY frontend/package.json frontend/package-lock.json ./
#RUN npm ci
#
#COPY frontend/ ./
#RUN npm run build
#
#FROM nginx:1.27-alpine
#COPY --from=build /app/dist /usr/share/nginx/html
#
## Ensure the app knows where to reach the API.
## Use envsubst during start to inject API base URL when needed.
#COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
#
#EXPOSE 80
#CMD ["nginx", "-g", "daemon off;"]
