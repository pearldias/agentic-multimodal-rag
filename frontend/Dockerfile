# Stage 1: Build the React/Vite application
FROM node:22-alpine AS build

WORKDIR /app

# Copy package definition and lockfile
COPY package.json package-lock.json ./

# Install dependencies using the existing lockfile
RUN npm ci

# Copy frontend source files (excluding items in .dockerignore)
COPY . .

# Build the production bundle using the existing Vite build script
RUN npm run build

# Stage 2: Serve the production build with lightweight nginx
FROM nginx:alpine

# Copy the generated dist directory from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
