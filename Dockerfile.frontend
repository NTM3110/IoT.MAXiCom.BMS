# --- Stage 1: Build Angular App ---
FROM node:20-alpine AS builder

WORKDIR /app

# 1. Cài đặt thư viện múi giờ (tzdata)
RUN apk add --no-cache tzdata

# 2. Thiết lập biến môi trường múi giờ
ENV TZ=Asia/Bangkok

RUN date

# Copy package files và cài dependencies
COPY package*.json ./
RUN npm ci

# Copy toàn bộ source code
COPY . .

# Build Angular (Production mode)
RUN npm run build

# --- Stage 2: Setup Node Server (No Nginx) ---
FROM node:20-alpine

WORKDIR /app

# Cài đặt Express và Http-Proxy-Middleware để chạy server.js
# Chúng ta cài trực tiếp ở bước này để không làm nặng image với các devDependencies của Angular
RUN npm install express http-proxy-middleware

# Copy thư mục đã build từ Stage 1
# LƯU Ý: Angular 17+ thường build ra dist/project-name/browser.
# Hãy kiểm tra xem lệnh build của bạn tạo ra cấu trúc nào.
# Nếu build ra có thư mục 'browser', hãy đổi dòng dưới thành:
# COPY --from=builder /app/dist/maxicom-bms/browser ./dist/maxicom-bms
COPY --from=builder /app/dist/maxicom-bms/browser ./dist/maxicom-bms

# Copy file server.js vào container
COPY server.js .

# Expose port 80
EXPOSE 80
# Khởi chạy server
CMD ["node", "server.js"]
