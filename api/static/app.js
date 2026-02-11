/**
 * 小红书发布工具 PWA — 前端逻辑
 */

// ============ 状态 ============
let ws = null;
let isProcessing = false;

// ============ 初始化 ============
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    connectWebSocket();
    setupPasteButton();
});

// ============ 加载配置 ============
async function loadConfig() {
    try {
        const resp = await fetch('/api/config');
        const data = await resp.json();

        // 填充模型下拉
        const modelSelect = document.getElementById('modelSelect');
        modelSelect.innerHTML = '';
        data.models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m === data.defaults.model) opt.selected = true;
            modelSelect.appendChild(opt);
        });

        // 填充模板下拉
        const templateSelect = document.getElementById('templateSelect');
        templateSelect.innerHTML = '';
        data.templates.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = `${t.name}`;
            if (t.id === data.defaults.template) opt.selected = true;
            templateSelect.appendChild(opt);
        });

        // 填充提示词下拉
        const promptSelect = document.getElementById('promptSelect');
        promptSelect.innerHTML = '';
        data.prompt_styles.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.name;
            opt.textContent = `${p.name} — ${p.description}`;
            if (p.name === data.defaults.prompt_style) opt.selected = true;
            promptSelect.appendChild(opt);
        });

        if (!data.defaults.api_key_set) {
            showToast('⚠️ 未设置 API Key，请在电脑端配置');
        }

    } catch (e) {
        showToast('❌ 无法连接后端服务');
        console.error('加载配置失败:', e);
    }
}

// ============ WebSocket 连接 ============
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws/logs`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        document.getElementById('connectionStatus').textContent = '已连接';
        document.getElementById('statusDot').style.background = 'var(--success)';
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'log') {
            appendLog(data.message);
        } else if (data.type === 'progress') {
            updateProgress(data.value);
        }
    };

    ws.onclose = () => {
        document.getElementById('connectionStatus').textContent = '连接断开，重连中...';
        document.getElementById('statusDot').style.background = 'var(--danger)';
        // 自动重连
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
        document.getElementById('connectionStatus').textContent = '连接失败';
        document.getElementById('statusDot').style.background = 'var(--danger)';
    };

    // 心跳
    setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
        }
    }, 30000);
}

// ============ 粘贴按钮 ============
function setupPasteButton() {
    document.getElementById('pasteBtn').addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            document.getElementById('urlInput').value = text;
            showToast('📋 已粘贴');
        } catch {
            showToast('⚠️ 无法访问剪贴板，请手动粘贴');
        }
    });
}

// ============ 获取当前配置 ============
function getConfig() {
    return {
        url: document.getElementById('urlInput').value.trim(),
        model: document.getElementById('modelSelect').value,
        template: document.getElementById('templateSelect').value,
        prompt_style: document.getElementById('promptSelect').value,
    };
}

// ============ 手动模式 ============
async function handleManual() {
    const config = getConfig();
    if (!config.url) {
        showToast('⚠️ 请先输入文章链接');
        return;
    }

    setProcessing(true);
    showLogPanel();
    hidePreview();
    clearLogs();
    appendLog('📱 手动模式启动...');

    try {
        const resp = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });

        const data = await resp.json();

        if (resp.ok && data.success) {
            showPreview(data);
            showToast('✅ 生成完成，请预览确认');
        } else {
            showToast(`❌ ${data.error || '生成失败'}`);
        }
    } catch (e) {
        showToast('❌ 请求失败，请检查后端是否运行');
        console.error(e);
    } finally {
        setProcessing(false);
    }
}

// ============ 自动模式 ============
async function handleAuto() {
    const config = getConfig();
    if (!config.url) {
        showToast('⚠️ 请先输入文章链接');
        return;
    }

    if (!confirm('🚀 确认自动发布？将直接抓取、生成并发布到小红书。')) {
        return;
    }

    setProcessing(true);
    showLogPanel();
    hidePreview();
    clearLogs();
    appendLog('🤖 自动发布模式启动...');

    try {
        const resp = await fetch('/api/auto-publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });

        const data = await resp.json();

        if (resp.ok && data.success) {
            showToast('✅ 自动发布成功！');
        } else {
            showToast(`❌ ${data.error || '发布失败'}`);
        }
    } catch (e) {
        showToast('❌ 请求失败');
        console.error(e);
    } finally {
        setProcessing(false);
    }
}

// ============ 确认发布 ============
async function handlePublish() {
    if (!confirm('✅ 确认发布到小红书？')) return;

    const btn = document.getElementById('btnPublish');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> 发布中...';

    try {
        const resp = await fetch('/api/publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auto_publish: true }),
        });

        const data = await resp.json();

        if (resp.ok && data.success) {
            showToast('✅ 发布成功！');
            btn.innerHTML = '✅ 已发布';
        } else {
            showToast(`❌ ${data.error || '发布失败'}`);
            btn.innerHTML = '✅ 确认发布到小红书';
            btn.disabled = false;
        }
    } catch (e) {
        showToast('❌ 请求失败');
        btn.innerHTML = '✅ 确认发布到小红书';
        btn.disabled = false;
    }
}

// ============ UI 工具函数 ============

function setProcessing(state) {
    isProcessing = state;
    const btnManual = document.getElementById('btnManual');
    const btnAuto = document.getElementById('btnAuto');

    if (state) {
        btnManual.disabled = true;
        btnAuto.disabled = true;
        btnManual.innerHTML = '<span class="spinner"></span> 处理中...';
        btnAuto.innerHTML = '<span class="spinner"></span> 处理中...';
        document.getElementById('progressWrapper').classList.add('active');
    } else {
        btnManual.disabled = false;
        btnAuto.disabled = false;
        btnManual.innerHTML = '<span>🔍</span> <span>手动生成</span>';
        btnAuto.innerHTML = '<span>🚀</span> <span>自动发布</span>';
        document.getElementById('progressWrapper').classList.remove('active');
    }
}

function showLogPanel() {
    document.getElementById('logPanel').classList.add('active');
}

function clearLogs() {
    document.getElementById('logContainer').innerHTML = '';
}

function appendLog(msg) {
    const container = document.getElementById('logContainer');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = msg;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function updateProgress(value) {
    const bar = document.getElementById('progressBar');
    const text = document.getElementById('progressText');
    const wrapper = document.getElementById('progressWrapper');
    wrapper.classList.add('active');
    bar.style.width = `${value}%`;
    text.textContent = `${Math.round(value)}%`;
}

function showPreview(data) {
    const panel = document.getElementById('previewPanel');
    const title = document.getElementById('previewTitle');
    const subtitle = document.getElementById('previewSubtitle');
    const carousel = document.getElementById('imageCarousel');

    title.textContent = data.caption_title || '';
    subtitle.textContent = `封面标题: ${(data.cover_title || '').replace(/\n/g, ' | ')}`;

    carousel.innerHTML = '';
    (data.images || []).forEach((url, i) => {
        const img = document.createElement('img');
        img.className = 'preview-image';
        img.src = url;
        img.alt = `页面 ${i + 1}`;
        img.onclick = () => openViewer(url);
        carousel.appendChild(img);
    });

    // 重置发布按钮
    const btn = document.getElementById('btnPublish');
    btn.disabled = false;
    btn.innerHTML = '✅ 确认发布到小红书';

    panel.classList.add('active');
}

function hidePreview() {
    document.getElementById('previewPanel').classList.remove('active');
}

function openViewer(src) {
    const viewer = document.getElementById('imageViewer');
    document.getElementById('viewerImage').src = src;
    viewer.classList.add('active');
}

function closeViewer() {
    document.getElementById('imageViewer').classList.remove('active');
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

// ============ Service Worker (PWA 离线缓存) ============
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
}
