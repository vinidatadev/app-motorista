FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .

# Build args injetados pelo EasyPanel / docker-compose
ARG VITE_API_URL
ARG VITE_MAPBOX_TOKEN
ARG VITE_OPENCAGE_KEY

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_MAPBOX_TOKEN=$VITE_MAPBOX_TOKEN
ENV VITE_OPENCAGE_KEY=$VITE_OPENCAGE_KEY

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# ARG NGINX_CONF define qual conf usar: "nginx.conf" (prod) ou "nginx.local.conf" (dev)
ARG NGINX_CONF=nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf

EXPOSE 80
