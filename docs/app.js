/**
 * GitHub Actions 云端版控制台逻辑
 */

// ============ 初始化 ============
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    setupEventListeners();
    if (getSettings().pat) {
        loadRuns();
    } else {
        document.querySelector('.empty-runs').textContent = '请先配置 GitHub PAT';
        showSettings();
    }
});

// ============ 事件监听 ============
function setupEventListeners() {
    // 设置折叠
    document.getElementById('toggleSettings').addEventListener('click', () => {
        document.getElementById('settingsContent').classList.toggle('open');
        document.querySelector('.arrow').textContent =
            document.getElementById('settingsContent').classList.contains('open') ? '▲' : '▼';
    });

    // 保存设置
    document.getElementById('repoInput').addEventListener('change', saveSettings);
    document.getElementById('patInput').addEventListener('change', saveSettings);

    // 粘贴
    document.getElementById('pasteBtn').addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            document.getElementById('urlInput').value = text;
            showToast('📋 已粘贴');
        } catch {
            showToast('⚠️ 请手动粘贴');
        }
    });

    // 自动刷新
    setInterval(() => {
        if (getSettings().pat) loadRuns();
    }, 30000);
}

// ============ 设置管理 ============
function getSettings() {
    return {
        repo: localStorage.getItem('xhs_repo') || '',
        pat: localStorage.getItem('xhs_pat') || ''
    };
}

function saveSettings() {
    const repo = document.getElementById('repoInput').value.trim();
    const pat = document.getElementById('patInput').value.trim();

    if (repo) localStorage.setItem('xhs_repo', repo);
    if (pat) localStorage.setItem('xhs_pat', pat);

    showToast('💾 设置已保存');
    if (repo && pat) loadRuns();
}

function loadSettings() {
    const settings = getSettings();
    document.getElementById('repoInput').value = settings.repo;
    document.getElementById('patInput').value = settings.pat;
}

function showSettings() {
    document.getElementById('settingsContent').classList.add('open');
    document.querySelector('.arrow').textContent = '▲';
}

// ============ 触发 Actions ============
async function triggerAction() {
    const { repo, pat } = getSettings();
    if (!repo || !pat) {
        showToast('⚠️ 请先配置 Repo 和 PAT');
        showSettings();
        return;
    }

    const url = document.getElementById('urlInput').value.trim();
    if (!url) {
        showToast('⚠️ 请输入文章链接');
        return;
    }

    const btn = document.getElementById('btnTrigger');
    btn.disabled = true;
    btn.innerHTML = '🚀 发送指令...';

    const payload = {
        event_type: "publish_trigger",
        client_payload: {
            url: url,
            model: document.getElementById('modelSelect').value,
            template: document.getElementById('templateSelect').value,
            prompt_style: document.getElementById('promptSelect').value
        }
    };

    try {
        const resp = await fetch(`https://api.github.com/repos/${repo}/dispatches`, {
            method: 'POST',
            headers: {
                'Authorization': `token ${pat}`,
                'Accept': 'application/vnd.github.v3+json'
            },
            body: JSON.stringify(payload)
        });

        if (resp.ok) {
            showToast('✅ 指令已发送！Actions 即将开始');
            document.getElementById('statusMsg').textContent = '✅ 指令已发送，请等待下方列表刷新...';
            setTimeout(loadRuns, 3000); // 3秒后刷新列表
        } else {
            const err = await resp.json();
            showToast(`❌ 发送失败: ${err.message || resp.status}`);
            document.getElementById('statusMsg').textContent = `❌ 错误: ${err.message}`;
        }
    } catch (e) {
        showToast('❌ 网络错误');
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>🚀</span> <span>触发云端发布</span>';
    }
}

// ============ 获取运行列表 ============
async function loadRuns() {
    const { repo, pat } = getSettings();
    if (!repo || !pat) return;

    const list = document.getElementById('runsList');

    try {
        const resp = await fetch(`https://api.github.com/repos/${repo}/actions/runs?per_page=5`, {
            headers: {
                'Authorization': `token ${pat}`,
                'Accept': 'application/vnd.github.v3+json'
            }
        });

        if (!resp.ok) return;

        const data = await resp.json();
        list.innerHTML = '';

        if (data.workflow_runs.length === 0) {
            list.innerHTML = '<div class="empty-runs">暂无运行记录</div>';
            return;
        }

        data.workflow_runs.forEach(run => {
            const item = document.createElement('div');
            item.className = 'run-item';

            let statusClass = 'status-queued';
            if (run.status === 'completed') {
                statusClass = run.conclusion === 'success' ? 'status-success' : 'status-failure';
            } else if (run.status === 'in_progress') {
                statusClass = 'status-in_progress';
            }

            // 时间格式化 (简单版)
            const time = new Date(run.created_at).toLocaleString('zh-CN', {
                month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
            });

            item.innerHTML = `
                <div class="run-status ${statusClass}"></div>
                <div class="run-info">
                    <div style="font-weight: 500;">${run.name} #${run.run_number}</div>
                    <div class="run-time">${time} · ${run.status}</div>
                </div>
                <a href="${run.html_url}" target="_blank" class="run-link">查看 ></a>
            `;
            list.appendChild(item);
        });

    } catch (e) {
        console.error('加载列表失败', e);
    }
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}
