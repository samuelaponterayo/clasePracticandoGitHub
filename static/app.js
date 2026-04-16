document.addEventListener('DOMContentLoaded', function () {
  const promptInput  = document.getElementById('prompt');
  const sendBtn      = document.getElementById('send');
  const chatEl       = document.getElementById('chat');
  const newConvBtn   = document.getElementById('new-conv-btn');
  const convListEl   = document.getElementById('conv-list');
  const authOverlay  = document.getElementById('auth-overlay');
  const loginForm    = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  const loginError   = document.getElementById('login-error');
  const regError     = document.getElementById('reg-error');
  const userAvatar   = document.getElementById('user-avatar');
  const userNameEl   = document.getElementById('user-name');
  const logoutBtn    = document.getElementById('logout-btn');
  const chatHeader   = document.getElementById('chat-header');

  let currentConvId = null;
  let currentUser   = null;

  // ── Auth ──────────────────────────────────────────────

  function loadUser() {
    const saved = localStorage.getItem('chat_user');
    if (saved) {
      currentUser = JSON.parse(saved);
      showApp();
    }
  }

  function saveUser(user) {
    currentUser = user;
    localStorage.setItem('chat_user', JSON.stringify(user));
    showApp();
  }

  function showApp() {
    authOverlay.classList.add('hidden');
    userNameEl.textContent = currentUser.username;
    userAvatar.textContent = currentUser.username[0].toUpperCase();
    loadConversations();
  }

  function logout() {
    localStorage.removeItem('chat_user');
    currentUser   = null;
    currentConvId = null;
    convListEl.innerHTML = '';
    resetChat();
    promptInput.disabled = true;
    sendBtn.disabled     = true;
    authOverlay.classList.remove('hidden');
  }

  function resetChat() {
    chatEl.innerHTML = `
      <div id="empty-state">
        <div class="empty-icon">💬</div>
        <p>Seleccioná o creá una conversación</p>
      </div>`;
    chatHeader.textContent = 'Seleccioná una conversación';
  }

  document.querySelectorAll('.auth-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      loginForm.classList.toggle('hidden',    tab.dataset.tab !== 'login');
      registerForm.classList.toggle('hidden', tab.dataset.tab !== 'register');
      loginError.textContent = '';
      regError.textContent   = '';
    });
  });

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    loginError.textContent = '';
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    try {
      const res = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) { loginError.textContent = (await res.json()).detail || 'Error al ingresar'; return; }
      saveUser(await res.json());
    } catch { loginError.textContent = 'Error de red'; }
  });

  registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    regError.textContent = '';
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;
    try {
      const res = await fetch('/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) { regError.textContent = (await res.json()).detail || 'Error al registrarse'; return; }
      saveUser(await res.json());
    } catch { regError.textContent = 'Error de red'; }
  });

  logoutBtn.addEventListener('click', logout);

  // ── Render helpers ─────────────────────────────────────

  function mdToHtml(text) {
    try {
      if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined')
        return DOMPurify.sanitize(marked.parse(String(text)));
    } catch (_) {}
    return String(text).replace(/</g, '&lt;');
  }

  function renderMessage(role, content, createdAt) {
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.remove();

    const wrapper  = document.createElement('div');
    wrapper.className = 'message ' + role;

    const bubble   = document.createElement('div');
    bubble.className  = 'bubble';
    bubble.innerHTML  = mdToHtml(content);

    const meta     = document.createElement('div');
    meta.className    = 'meta';
    meta.textContent  = createdAt ? new Date(createdAt).toLocaleTimeString() : '';

    wrapper.appendChild(bubble);
    wrapper.appendChild(meta);
    chatEl.appendChild(wrapper);
    chatEl.scrollTop = chatEl.scrollHeight;
    return wrapper;
  }

  function renderTyping() {
    const wrapper = document.createElement('div');
    wrapper.className = 'message model';
    const bubble  = document.createElement('div');
    bubble.className  = 'bubble';
    bubble.textContent = '…';
    wrapper.appendChild(bubble);
    chatEl.appendChild(wrapper);
    chatEl.scrollTop = chatEl.scrollHeight;
    return wrapper;
  }

  // ── Conversaciones ─────────────────────────────────────

  async function loadConversations() {
    const url = `/conversations/${currentUser ? `?user_id=${currentUser.id}` : ''}`;
    const res = await fetch(url);
    if (!res.ok) return;
    convListEl.innerHTML = '';
    (await res.json()).forEach(renderConvItem);
  }

  function renderConvItem(conv) {
    const item = document.createElement('div');
    item.className   = 'conv-item' + (conv.id === currentConvId ? ' active' : '');
    item.dataset.id  = conv.id;
    item.textContent = conv.title || `Conversación #${conv.id}`;

    item.addEventListener('click', () => selectConversation(conv.id, item.textContent));

    // Doble clic → renombrar inline
    item.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      startRename(item, conv.id);
    });

    convListEl.appendChild(item);
  }

  function startRename(item, convId) {
    const current = item.textContent;
    item.textContent = '';

    const input = document.createElement('input');
    input.className   = 'rename-input';
    input.value       = current;
    item.appendChild(input);
    input.focus();
    input.select();

    async function commitRename() {
      const newTitle = input.value.trim();
      if (!newTitle || newTitle === current) {
        item.textContent = current;
        return;
      }
      const res = await fetch(`/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle }),
      });
      if (res.ok) {
        item.textContent = newTitle;
        if (convId === currentConvId) chatHeader.textContent = newTitle;
      } else {
        item.textContent = current;
      }
    }

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter')  { e.preventDefault(); input.blur(); }
      if (e.key === 'Escape') { item.textContent = current; }
    });
    input.addEventListener('blur', commitRename);
  }

  async function selectConversation(convId, title) {
    currentConvId          = convId;
    chatHeader.textContent = title || `Conversación #${convId}`;

    document.querySelectorAll('.conv-item').forEach(el => {
      el.classList.toggle('active', Number(el.dataset.id) === convId);
    });

    promptInput.disabled = false;
    sendBtn.disabled     = false;
    promptInput.focus();

    chatEl.innerHTML = '';
    const res = await fetch(`/conversations/${convId}/messages`);
    if (!res.ok) return;
    const messages = await res.json();
    if (messages.length === 0) {
      chatEl.innerHTML = '<div id="empty-state"><div class="empty-icon">💬</div><p>Aún no hay mensajes. ¡Escribí algo!</p></div>';
    } else {
      messages.forEach(m => renderMessage(m.role, m.content, m.created_at));
    }
  }

  newConvBtn.addEventListener('click', async () => {
    const url = `/conversations/${currentUser ? `?user_id=${currentUser.id}` : ''}`;
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) return;
    const conv = await res.json();
    renderConvItem(conv);
    selectConversation(conv.id, conv.title);
  });

  // ── Envío de mensajes ──────────────────────────────────

  async function sendMessage() {
    const text = promptInput.value.trim();
    if (!text || !currentConvId) return;
    promptInput.value        = '';
    promptInput.style.height = 'auto';
    sendBtn.disabled         = true;

    renderMessage('user', text, new Date().toISOString());
    const typingEl = renderTyping();

    try {
      const res = await fetch(`/conversations/${currentConvId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      typingEl.remove();
      if (!res.ok) { renderMessage('model', `Error ${res.status}`, new Date().toISOString()); return; }
      const msg = await res.json();
      renderMessage(msg.role, msg.content, msg.created_at);
    } catch (err) {
      typingEl.remove();
      renderMessage('model', `Error de red: ${err.message}`, new Date().toISOString());
    } finally {
      sendBtn.disabled = false;
      promptInput.focus();
    }
  }

  sendBtn.addEventListener('click', sendMessage);
  promptInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  promptInput.addEventListener('input', () => {
    promptInput.style.height = 'auto';
    promptInput.style.height = Math.min(promptInput.scrollHeight, 140) + 'px';
  });

  // ── Init ──────────────────────────────────────────────
  loadUser();
});
