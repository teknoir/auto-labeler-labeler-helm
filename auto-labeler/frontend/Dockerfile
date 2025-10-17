FROM node:20-alpine AS build
WORKDIR /app

RUN apk add --no-cache gettext

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html

# Ensure the app knows where to reach the API.
# Use envsubst during start to inject API base URL when needed.
COPY deploy/nginx.conf /etc/nginx/nginx.conf.template
COPY deploy/entrypoint.sh /entrypoint.sh

EXPOSE 80
CMD ["/entrypoint.sh"]
