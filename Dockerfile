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

# CSP montada em tempo de build a partir dos placeholders __CSP_*__ da conf.
# Defaults = valores anteriores (backend.devlopplay.site / localhost:9000),
# entao builds sem esses args continuam funcionando como antes.
ARG CSP_API_URL=https://backend.devlopplay.site
ARG CSP_WS_URL=wss://backend.devlopplay.site
ARG CSP_IMG_SRC=http://localhost:9000
# (delimitador "|" evita conflito com "/" das URLs; URLs nao usam "|")
RUN sed -i "s|__CSP_API_URL__|${CSP_API_URL}|g; s|__CSP_WS_URL__|${CSP_WS_URL}|g; s|__CSP_IMG_SRC__|${CSP_IMG_SRC}|g" /etc/nginx/conf.d/default.conf

EXPOSE 80
