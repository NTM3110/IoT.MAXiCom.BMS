const express = require('express');
const {createProxyMiddleware} = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 80;

// --- CẤU HÌNH TARGET (Lấy từ biến môi trường Docker) ---
// Nếu không có biến môi trường thì mới fallback về localhost (dev)
const TARGET_8081 = process.env.API_TARGET_8081 || 'http://localhost:8081';
const TARGET_8888 = process.env.API_TARGET_8888 || 'http://localhost:8888';
const TARGET_NETWORK = process.env.API_TARGET_NETWORK || 'http://host.docker.internal:5000';

console.log(`Connecting to Backend at: ${TARGET_8081}`);
console.log(`Connecting to OpenMUC at: ${TARGET_8888}`);

// --- CẤU HÌNH PROXY ---

// 1. Schedule API
app.use('/api/schedule', createProxyMiddleware({
    target: TARGET_8081,
    changeOrigin: true,
    pathRewrite: {'^/': '/soh-schedule/'},
    logger: console
}));

// 2. Latest Value API
app.use('/api/latest-value', createProxyMiddleware({
    target: TARGET_8081,
    changeOrigin: true,
    pathRewrite: {'^/': '/latest-value/'},
    logger: console
}));

// 3. General API (OpenMUC)
app.use('/api', createProxyMiddleware({
    target: TARGET_8888,
    changeOrigin: true,
    pathRewrite: {'^/': '/rest/'},
    headers: {'Authorization': 'Basic YWRtaW46YWRtaW4='},
    logger: console
}));

app.use('/api/network', createProxyMiddleware({
    target: TARGET_NETWORK,
    changeOrigin: true,
    // Không cần pathRewrite vì Python API cũng lắng nghe ở /api/network
    logger: console
}));
// --- CẤU HÌNH STATIC FILES ---
// Đường dẫn này phải khớp với lệnh COPY trong Dockerfile
// Vì ta COPY dist ./dist -> Trong container là /app/dist/maxicom-bms/browser (nếu Angular 17+)
// Hoặc /app/dist/maxicom-bms (nếu cũ hơn). Bạn kiểm tra folder dist thật của bạn nhé.
// Giả sử cấu trúc chuẩn là dist/maxicom-bms/browser:
const distPath = path.join(__dirname, 'dist/maxicom-bms/browser');
// Nếu chạy bị lỗi đường dẫn, thử bỏ '/browser' đi:
// const distPath = path.join(__dirname, 'dist/maxicom-bms');

app.use(express.static(distPath));

app.get(/.*/, (req, res) => {
    res.sendFile(path.join(distPath, 'index.html'));
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
