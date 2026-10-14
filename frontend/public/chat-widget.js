/**
 * GraphRAG Chat Widget — Engine-Vue Stage 1
 *
 * Zero-dependency floating AI assistant. Embed with one line:
 *   <script src="http://localhost:8000/static/chat-widget.js"
 *           data-endpoint="http://localhost:8000"
 *           data-title="HSE 知识助手"
 *           data-theme="light"></script>
 *
 * @license MIT
 */
(function () {
  'use strict';

  // ── Configuration ──────────────────────────────────────────────────
  const script = document.currentScript;
  const CONFIG = {
    endpoint: script?.dataset?.endpoint || (script?.src ? new URL(script.src).origin : ''),
    title: script?.dataset?.title || 'AI 助手',
    theme: script?.dataset?.theme || 'light',
    orgId: script?.dataset?.orgId || '',
    projectId: script?.dataset?.projectId || '',
  };

  // Colors
  const LIGHT = {
    bg: '#ffffff',
    text: '#1e293b',
    textSecondary: '#64748b',
    border: '#e2e8f0',
    userBubble: '#3b82f6',
    userText: '#ffffff',
    assistantBubble: '#f1f5f9',
    headerBg: '#3b82f6',
    headerText: '#ffffff',
    inputBg: '#f8fafc',
    inputBorder: '#cbd5e1',
    sendBtn: '#3b82f6',
    sendBtnText: '#ffffff',
    feedbackActive: '#3b82f6',
    feedbackInactive: '#94a3b8',
    errorBg: '#fef2f2',
    errorText: '#dc2626',
    toggleBg: '#3b82f6',
    toggleIcon: '#ffffff',
    shadow: '0 4px 24px rgba(0,0,0,0.12)',
  };

  const DARK = {
    bg: '#1e293b',
    text: '#f1f5f9',
    textSecondary: '#94a3b8',
    border: '#334155',
    userBubble: '#2563eb',
    userText: '#ffffff',
    assistantBubble: '#334155',
    headerBg: '#1e40af',
    headerText: '#f1f5f9',
    inputBg: '#0f172a',
    inputBorder: '#475569',
    sendBtn: '#3b82f6',
    sendBtnText: '#ffffff',
    feedbackActive: '#60a5fa',
    feedbackInactive: '#64748b',
    errorBg: '#450a0a',
    errorText: '#fca5a5',
    toggleBg: '#2563eb',
    toggleIcon: '#ffffff',
    shadow: '0 4px 24px rgba(0,0,0,0.4)',
  };

  const C = CONFIG.theme === 'dark' ? DARK : LIGHT;

  // ── State ───────────────────────────────────────────────────────────
  let sessionId = '';
  let lastQueryId = '';
  let isOpen = false;
  let isLoading = false;

  // ── Markdown renderer ───────────────────────────────────────────────
  function renderMarkdown(text) {
    if (!text) return '';
    let html = text
      // Escape HTML
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      // Code blocks ```
      .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="md-code-block"><code>$2</code></pre>')
      // Inline code `
      .replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
      // Bold **text**
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      // Italic *text*
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      // Headers
      .replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
      .replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
      .replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
      // Unordered lists
      .replace(/^[*-] (.+)$/gm, '<li class="md-li">$1</li>')
      // Ordered lists
      .replace(/^\d+\. (.+)$/gm, '<li class="md-li">$1</li>')
      // Citations [citation:N]
      .replace(/\[citation:(\d+)\]/g, '<sup class="md-citation">[$1]</sup>')
      // Paragraphs (double newline)
      .replace(/\n\n/g, '</p><p class="md-p">')
      // Single newline → <br>
      .replace(/\n/g, '<br>');

    return '<p class="md-p">' + html + '</p>';
  }

  // ── API calls ───────────────────────────────────────────────────────
  async function apiCall(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };
    if (CONFIG.orgId) headers['X-Org-Id'] = CONFIG.orgId;
    if (CONFIG.projectId) headers['X-Project-Id'] = CONFIG.projectId;

    const res = await fetch(CONFIG.endpoint + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function askQuestion(question) {
    sessionId = sessionId || 'widget_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    const data = await apiCall('POST', '/api/v1/rag/query', {
      query: question,
      session_id: sessionId,
    });
    lastQueryId = data.metadata?.query_id || '';
    return data;
  }

  async function sendFeedback(rating) {
    if (!lastQueryId) return;
    await apiCall('POST', '/api/v1/feedback', {
      query_id: lastQueryId,
      rating: rating,
    });
  }

  // ── DOM builder ─────────────────────────────────────────────────────
  function createElement(tag, attrs, children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === 'className') el.className = v;
        else if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
        else el.setAttribute(k, v);
      }
    }
    if (children) {
      if (typeof children === 'string') el.textContent = children;
      else if (Array.isArray(children)) children.forEach(c => { if (c) el.appendChild(c); });
      else el.appendChild(children);
    }
    return el;
  }

  function buildStyles() {
    return `
      * { box-sizing: border-box; margin: 0; padding: 0; }

      .widget-container {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 99999;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 14px;
        line-height: 1.6;
      }

      .chat-toggle {
        width: 52px;
        height: 52px;
        border-radius: 50%;
        border: none;
        background: ${C.toggleBg};
        color: ${C.toggleIcon};
        cursor: pointer;
        font-size: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: ${C.shadow};
        transition: transform 0.2s, box-shadow 0.2s;
        position: absolute;
        bottom: 0;
        right: 0;
      }
      .chat-toggle:hover { transform: scale(1.08); box-shadow: 0 6px 32px rgba(0,0,0,0.18); }
      .chat-toggle:active { transform: scale(0.95); }

      .chat-panel {
        position: absolute;
        bottom: 68px;
        right: 0;
        width: 380px;
        height: 520px;
        background: ${C.bg};
        border-radius: 12px;
        box-shadow: ${C.shadow};
        display: flex;
        flex-direction: column;
        overflow: hidden;
        border: 1px solid ${C.border};
        transition: opacity 0.25s, transform 0.25s;
      }
      .chat-panel.hidden {
        opacity: 0;
        transform: translateY(12px) scale(0.96);
        pointer-events: none;
      }

      .chat-header {
        background: ${C.headerBg};
        color: ${C.headerText};
        padding: 12px 16px;
        font-weight: 600;
        font-size: 15px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-shrink: 0;
      }
      .chat-close {
        background: none;
        border: none;
        color: ${C.headerText};
        cursor: pointer;
        font-size: 18px;
        padding: 0 4px;
        opacity: 0.8;
      }
      .chat-close:hover { opacity: 1; }

      .chat-messages {
        flex: 1;
        overflow-y: auto;
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      .chat-messages::-webkit-scrollbar { width: 5px; }
      .chat-messages::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 3px; }

      .chat-empty {
        text-align: center;
        color: ${C.textSecondary};
        padding: 40px 20px;
        font-size: 13px;
      }

      .message {
        max-width: 88%;
        padding: 10px 14px;
        border-radius: 12px;
        font-size: 13.5px;
        word-wrap: break-word;
        animation: msgIn 0.25s ease-out;
      }
      @keyframes msgIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

      .message.user {
        align-self: flex-end;
        background: ${C.userBubble};
        color: ${C.userText};
        border-bottom-right-radius: 4px;
      }

      .message.assistant {
        align-self: flex-start;
        background: ${C.assistantBubble};
        color: ${C.text};
        border-bottom-left-radius: 4px;
      }

      .message.error {
        align-self: center;
        background: ${C.errorBg};
        color: ${C.errorText};
        font-size: 12.5px;
        max-width: 95%;
      }

      .message.loading {
        align-self: flex-start;
        background: ${C.assistantBubble};
        color: ${C.textSecondary};
        display: flex;
        gap: 4px;
        padding: 14px 18px;
      }
      .loading-dot {
        width: 7px; height: 7px;
        background: ${C.textSecondary};
        border-radius: 50%;
        animation: dotBounce 1.4s infinite ease-in-out both;
      }
      .loading-dot:nth-child(1) { animation-delay: -0.32s; }
      .loading-dot:nth-child(2) { animation-delay: -0.16s; }
      @keyframes dotBounce { 0%,80%,100% { transform: scale(0); } 40% { transform: scale(1); } }

      .md-p { margin-bottom: 6px; }
      .md-p:last-child { margin-bottom: 0; }
      .md-h2 { font-size: 16px; font-weight: 700; margin: 8px 0 4px; }
      .md-h3 { font-size: 15px; font-weight: 600; margin: 6px 0 3px; }
      .md-h4 { font-size: 14px; font-weight: 600; margin: 4px 0 2px; }
      .md-li { margin-left: 16px; }
      .md-code-block {
        background: ${CONFIG.theme === 'dark' ? '#0f172a' : '#f1f5f9'};
        border-radius: 6px;
        padding: 10px;
        margin: 6px 0;
        overflow-x: auto;
        font-size: 12.5px;
        line-height: 1.5;
      }
      .md-inline-code {
        background: ${CONFIG.theme === 'dark' ? '#334155' : '#e2e8f0'};
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 12.5px;
      }
      .md-citation {
        color: ${C.toggleBg};
        cursor: pointer;
        font-size: 11px;
        font-weight: 600;
      }

      .msg-footer { margin-top: 8px; }
      .feedback-btns {
        display: flex;
        gap: 8px;
        margin-bottom: 4px;
      }
      .fb-btn {
        background: none;
        border: none;
        cursor: pointer;
        font-size: 15px;
        padding: 2px 4px;
        color: ${C.feedbackInactive};
        transition: color 0.15s, transform 0.15s;
      }
      .fb-btn:hover { color: ${C.feedbackActive}; transform: scale(1.15); }
      .fb-btn.active { color: ${C.feedbackActive}; }
      .sources-toggle {
        font-size: 12px;
        color: ${C.feedbackActive};
        cursor: pointer;
        background: none;
        border: none;
        padding: 0;
      }
      .sources-list {
        margin-top: 6px;
        padding: 8px;
        background: ${C.inputBg};
        border-radius: 6px;
        font-size: 11.5px;
        color: ${C.textSecondary};
        display: none;
      }
      .sources-list.open { display: block; }
      .source-item {
        padding: 3px 0;
        border-bottom: 1px solid ${C.border};
      }
      .source-item:last-child { border-bottom: none; }
      .source-label { font-weight: 600; color: ${C.text}; }
      .source-type { opacity: 0.7; }

      .chat-input-area {
        padding: 10px 12px;
        border-top: 1px solid ${C.border};
        display: flex;
        gap: 8px;
        flex-shrink: 0;
      }
      .chat-input-area textarea {
        flex: 1;
        border: 1px solid ${C.inputBorder};
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 13.5px;
        font-family: inherit;
        resize: none;
        background: ${C.inputBg};
        color: ${C.text};
        outline: none;
        min-height: 38px;
        max-height: 100px;
      }
      .chat-input-area textarea:focus { border-color: ${C.sendBtn}; }
      .chat-send-btn {
        background: ${C.sendBtn};
        color: ${C.sendBtnText};
        border: none;
        border-radius: 8px;
        padding: 0 16px;
        font-size: 13.5px;
        font-weight: 600;
        cursor: pointer;
        transition: opacity 0.15s;
      }
      .chat-send-btn:hover { opacity: 0.9; }
      .chat-send-btn:disabled { opacity: 0.5; cursor: default; }

      @media (max-width: 440px) {
        .widget-container { bottom: 12px; right: 12px; }
        .chat-panel {
          width: calc(100vw - 24px);
          height: calc(100vh - 100px);
          bottom: 60px;
          right: 0;
        }
      }
    `;
  }

  function buildWidget() {
    // Create shadow host
    const host = createElement('div', { id: 'graphrag-chat-widget-root' });
    document.body.appendChild(host);
    const shadow = host.attachShadow({ mode: 'open' });

    // Styles
    const style = createElement('style', {}, buildStyles());
    shadow.appendChild(style);

    // Container
    const container = createElement('div', { className: 'widget-container' });

    // Toggle button
    const toggleBtn = createElement('button', {
      className: 'chat-toggle',
      'aria-label': '打开 AI 助手',
    }, '\u{1F4AC}');

    // Panel
    const panel = createElement('div', { className: 'chat-panel hidden' });

    // Header
    const header = createElement('div', { className: 'chat-header' }, [
      createElement('span', {}, CONFIG.title),
      createElement('button', {
        className: 'chat-close',
        'aria-label': '关闭',
        onClick: () => togglePanel(false),
      }, '\u{2715}'),
    ]);

    // Messages area
    const messagesEl = createElement('div', { className: 'chat-messages' });
    messagesEl.appendChild(createElement('div', { className: 'chat-empty' },
      '\u{1F44B} 你好！我是' + CONFIG.title + '，可以回答文档相关问题。'));

    // Input area
    const textarea = createElement('textarea', {
      placeholder: '输入你的问题...',
      rows: '1',
      onKeydown: (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      },
      onInput: (e) => {
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px';
      },
    });

    const sendBtn = createElement('button', {
      className: 'chat-send-btn',
      onClick: () => sendMessage(),
    }, '发送');

    const inputArea = createElement('div', { className: 'chat-input-area' }, [
      textarea, sendBtn,
    ]);

    panel.appendChild(header);
    panel.appendChild(messagesEl);
    panel.appendChild(inputArea);
    container.appendChild(panel);
    container.appendChild(toggleBtn);
    shadow.appendChild(container);

    // ── Internal functions ──────────────────────────────────────────
    function togglePanel(open) {
      isOpen = open;
      if (open) {
        panel.classList.remove('hidden');
        toggleBtn.style.display = 'none';
        setTimeout(() => textarea.focus(), 300);
      } else {
        panel.classList.add('hidden');
        toggleBtn.style.display = '';
      }
    }

    function addMessage(role, content) {
      // Remove empty state
      const emptyEl = messagesEl.querySelector('.chat-empty');
      if (emptyEl) emptyEl.remove();

      const msg = createElement('div', { className: 'message ' + role });
      if (role === 'assistant') {
        // Only the renderer's HTML is trusted: it escapes all API text first.
        msg.innerHTML = renderMarkdown(content);
      } else if (role === 'loading') {
        // Static, developer-owned markup; no API or document text is interpolated.
        msg.innerHTML = '<div class="loading-dot"></div><div class="loading-dot"></div><div class="loading-dot"></div>';
      } else {
        msg.textContent = content;
      }
      messagesEl.appendChild(msg);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return msg;
    }

    function removeLoading() {
      const loadingEl = messagesEl.querySelector('.message.loading');
      if (loadingEl) loadingEl.remove();
    }

    function addSources(msgEl, sources) {
      if (!sources || !sources.length) return;

      const footer = createElement('div', { className: 'msg-footer' });

      // Feedback buttons
      const fbDiv = createElement('div', { className: 'feedback-btns' });
      const thumbsUp = createElement('button', {
        className: 'fb-btn',
        title: '有帮助',
        onClick: async function () {
          if (thumbsUp.classList.contains('active')) return;
          thumbsUp.classList.add('active');
          thumbsDown.classList.remove('active');
          await sendFeedback('positive');
        },
      }, '\u{1F44D}');
      const thumbsDown = createElement('button', {
        className: 'fb-btn',
        title: '不满意',
        onClick: async function () {
          if (thumbsDown.classList.contains('active')) return;
          thumbsDown.classList.add('active');
          thumbsUp.classList.remove('active');
          await sendFeedback('negative');
        },
      }, '\u{1F44E}');
      fbDiv.appendChild(thumbsUp);
      fbDiv.appendChild(thumbsDown);
      footer.appendChild(fbDiv);

      // Sources toggle
      const sourcesToggle = createElement('button', {
        className: 'sources-toggle',
        onClick: function () {
          sourcesList.classList.toggle('open');
          this.textContent = sourcesList.classList.contains('open')
            ? '\u{25B2} 收起 ' + sources.length + ' 条引用'
            : '\u{25BC} 查看 ' + sources.length + ' 条引用';
        },
      }, '\u{25BC} 查看 ' + sources.length + ' 条引用');
      footer.appendChild(sourcesToggle);

      // Sources list
      const sourcesList = createElement('div', { className: 'sources-list' });
      sources.forEach((s, i) => {
        const item = createElement('div', { className: 'source-item' }, [
          createElement('span', { className: 'source-label' }, '[' + (i + 1) + '] ' + s.label),
          createElement('span', { className: 'source-type' }, ' \u{2022} ' + (s.entity_type || 'unknown') + (typeof s.relevance_score === 'number' ? ' (' + (s.relevance_score * 100).toFixed(0) + '%)' : '')),
        ]);
        sourcesList.appendChild(item);
      });
      footer.appendChild(sourcesList);

      msgEl.appendChild(footer);
    }

    async function sendMessage() {
      const question = textarea.value.trim();
      if (!question || isLoading) return;

      textarea.value = '';
      textarea.style.height = 'auto';
      isLoading = true;
      sendBtn.disabled = true;

      addMessage('user', question);
      const loadingEl = addMessage('loading');
      messagesEl.scrollTop = messagesEl.scrollHeight;

      try {
        const data = await askQuestion(question);
        removeLoading();
        const msgEl = addMessage('assistant', data.answer);
        addSources(msgEl, data.sources);
      } catch (err) {
        removeLoading();
        addMessage('error', '⚠️ ' + (err.message || '请求失败，请稍后重试'));
      } finally {
        isLoading = false;
        sendBtn.disabled = false;
        textarea.focus();
      }
    }

    toggleBtn.addEventListener('click', () => togglePanel(true));

    // Expose toggle API globally
    window.GraphRAGChat = {
      open: () => togglePanel(true),
      close: () => togglePanel(false),
      toggle: () => togglePanel(!isOpen),
      ask: (q) => { textarea.value = q; togglePanel(true); sendMessage(); },
    };
  }

  // ── Bootstrap ───────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildWidget);
  } else {
    buildWidget();
  }
})();
