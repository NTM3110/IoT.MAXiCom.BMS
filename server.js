const express = require('express');
const {createProxyMiddleware} = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 80;

// Cấu hình API Target (Lấy từ biến môi trường hoặc mặc định như proxy.conf.json)
const TARGET_8081 = process.env.API_TARGET_8081 || 'http://192.168.4.45:8081';
const TARGET_8888 = process.env.API_TARGET_8888 || 'http://192.168.4.45:8888';

// --- CẤU HÌNH PROXY ---
// LƯU Ý: Phải đặt các route chi tiết lên TRƯỚC route chung

// 1. Proxy cho /api/schedule
// Express tự động cắt '/api/schedule' khỏi req.url khi dùng app.use
// Nên ta cần rewrite '^/' thành '/soh-schedule/' để bù lại
app.use('/api/schedule', createProxyMiddleware({
  target: TARGET_8081,
  changeOrigin: true,
  pathRewrite: {
    '^/': '/soh-schedule/'
  },
  logger: console
}));

// 2. Proxy cho /api/latest-value
// Express tự động cắt '/api/latest-value', ta rewrite '^/' thành '/latest-value/'
app.use('/api/latest-value', createProxyMiddleware({
  target: TARGET_8081,
  changeOrigin: true,
  pathRewrite: {
    '^/': '/latest-value/'
  },
  logger: console
}));

// 3. Proxy cho /api (Generic)
// Express tự động cắt '/api', ta rewrite '^/' thành '/rest/'
app.use('/api', createProxyMiddleware({
  target: TARGET_8888,
  changeOrigin: true,
  pathRewrite: {
    '^/': '/rest/'
  },
  headers: {
    'Authorization': 'Basic YWRtaW46YWRtaW4=' // admin:admin base64
  },
  logger: console
}));

// --- CẤU HÌNH STATIC FILES (Angular) ---

// Đường dẫn đến thư mục build của Angular
// Với Angular 17+, cấu trúc build thường là dist/project-name/browser
const distPath = path.join(__dirname, 'dist/maxicom-bms');

app.use(express.static(distPath));

// Xử lý Routing của Angular (SPA Fallback)
// Sử dụng Regex /.*/ để bắt tất cả các request còn lại (tránh lỗi path-to-regexp mới)
app.get(/.*/, (req, res) => {
  res.sendFile(path.join(distPath, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
  console.log(`Proxy Config:`);
  console.log(` - /api/schedule -> ${TARGET_8081}/soh-schedule`);
  console.log(` - /api/latest-value -> ${TARGET_8081}/latest-value`);
  console.log(` - /api -> ${TARGET_8888}/rest`);
});
