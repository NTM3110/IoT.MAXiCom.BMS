const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 80;

// --- CẤU HÌNH TARGET ---
// Lấy từ biến môi trường Docker (đã khai báo trong docker-compose.yml)
const TARGET_8081 = process.env.API_TARGET_8081 || 'http://localhost:8081';
const TARGET_8888 = process.env.API_TARGET_8888 || 'http://localhost:8888';
// Target cho Network Service (Cổng 5000)
const TARGET_NETWORK = process.env.API_TARGET_NETWORK || 'http://host.docker.internal:5000';

console.log('--- SERVER CONFIG ---');
console.log(`Backend Target: ${TARGET_8081}`);
console.log(`OpenMUC Target: ${TARGET_8888}`);
console.log(`Network Target: ${TARGET_NETWORK}`);

// --- CẤU HÌNH PROXY (QUAN TRỌNG: Thứ tự là mấu chốt) ---

// 1. Network API (PHẢI ĐẶT LÊN ĐẦU TIÊN)
// Khi request vào /api/network, Express sẽ cắt bỏ '/api/network', chỉ còn '/'
// và gửi sang Python Service (đang lắng nghe ở '/') -> KHỚP!
app.use('/api/network', createProxyMiddleware({
  target: TARGET_NETWORK,
  changeOrigin: true,
  logger: console
}));

// 2. Schedule API
app.use('/api/schedule', createProxyMiddleware({
  target: TARGET_8081,
  changeOrigin: true,
  pathRewrite: { '^/': '/soh-schedule/' },
  logger: console
}));

// 3. Latest Value API
app.use('/api/latest-value', createProxyMiddleware({
  target: TARGET_8081,
  changeOrigin: true,
  pathRewrite: { '^/': '/latest-value/' },
  logger: console
}));

// 4. Generic API (OpenMUC) - PHẢI ĐỂ CUỐI CÙNG
// Bắt tất cả các request /api/... còn lại
app.use('/api', createProxyMiddleware({
  target: TARGET_8888,
  changeOrigin: true,
  pathRewrite: { '^/': '/rest/' },
  headers: { 'Authorization': 'Basic YWRtaW46YWRtaW4=' },
  logger: console
}));

// --- CẤU HÌNH STATIC FILES (Angular) ---
// Đường dẫn đến thư mục build của Angular
const distPath = path.join(__dirname, 'dist/maxicom-bms/browser');

app.use(express.static(distPath));

// Fallback cho Angular Routing
app.get(/.*/, (req, res) => {
  res.sendFile(path.join(distPath, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
