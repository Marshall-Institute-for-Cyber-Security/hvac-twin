# syntax=docker/dockerfile:1
#
# All five HTML entries (index.html the room picker, closet.html and
# office.html each twin's operator console, attack.html the red-team
# console, defenses.html the defenses catalog) build into one dist/ and
# are served as plain static files -- no server-side routing needed, each
# is reachable at its own path exactly as Vite names it.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
