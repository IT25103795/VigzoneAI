/* Vigzone AI Main Client Script */
  const $ = (s) => document.querySelector(s);
  const main = $('#main');
  const chatInner = $('#chatInner');
  let emptyState = $('#emptyState');
  const input = $('#input');
  const sendBtn = $('#sendBtn');
  const pauseBtn = $('#pauseBtn');
  const statusDot = $('#statusDot');
  const statusText = $('#statusText');
  const newChatBtn = $('#newChatBtn');
  const newChatBtnSidebar = $('#newChatBtnSidebar');
  const attachBtn = $('#attachBtn');
  const driveImportBtn = $('#driveImportBtn');
  const driveImportModalOverlay = $('#driveImportModalOverlay');
  const driveImportCloseBtn = $('#driveImportCloseBtn');
  const drivePickerOpenBtn = $('#drivePickerOpenBtn');
  const driveLinkImportBtn = $('#driveLinkImportBtn');
  const driveLinkInput = $('#driveLinkInput');
  const driveImportStatus = $('#driveImportStatus');
  const imageModeBtn = $('#imageModeBtn');
  const aiModeSelect = $('#aiModeSelect');
  const modeMenuWrap = $('#modeMenuWrap');
  const modeMenuBtn = $('#modeMenuBtn');
  const modeMenu = $('#modeMenu');
  const modeMenuCloseBtn = $('#modeMenuCloseBtn');
  const plusMenuCloseBtn = $('#plusMenuCloseBtn');
  const modeMenuCurrent = $('#modeMenuCurrent');
  const workspacePill = $('#workspacePill');
  const workspaceSidebarBtn = $('#workspaceSidebarBtn');
  const workspaceModalOverlay = $('#workspaceModalOverlay');
  const workspaceModalCloseBtn = $('#workspaceModalCloseBtn');
  const workspaceModalBody = $('#workspaceModalBody');
  const exportChatBtn = $('#exportChatBtn');
  const exportMenu = $('#exportMenu');
  const exportTxtBtn = $('#exportTxtBtn');
  const exportHtmlBtn = $('#exportHtmlBtn');
  const exportMenuCloseBtn = $('#exportMenuCloseBtn');
  const fileInput = $('#fileInput');
  const attachmentsBar = $('#attachmentsBar');
  const scrollToBottomBtn = $('#scrollToBottomBtn');
  const goToBottomBtn = $('#goToBottomBtn');
  const sidebar = $('#sidebar');
  const sidebarOverlay = $('#sidebarOverlay');
  const sidebarToggleBtn = $('#sidebarToggleBtn');
  const historyList = $('#historyList');
  const signOutBtn = $('#signOutBtn');
  const exportAccountBtn = $('#exportAccountBtn');
  const changePasswordBtn = $('#changePasswordBtn');
  const deleteAccountBtn = $('#deleteAccountBtn');
  const refreshSharedLinksBtn = $('#refreshSharedLinksBtn');
  const sharedLinksList = $('#sharedLinksList');
  const sidebarUserName = $('#sidebarUserName');
  const sidebarUserDot = $('#sidebarUserDot');
  const settingsBtn = $('#settingsBtn');
  const vigzoneBrainBtn = $('#vigzoneBrainBtn');
  const brainModalOverlay = $('#brainModalOverlay');
  const brainModalCloseBtn = $('#brainModalCloseBtn');
  const brainModalBody = $('#brainModalBody');
  const brainTabs = $('#brainTabs');
  const brainSearchInput = $('#brainSearchInput');
  const brainRefreshBtn = $('#brainRefreshBtn');
  const brainExportBtn = $('#brainExportBtn');
  const settingsModalOverlay = $('#settingsModalOverlay');
  const settingsModalCloseBtn = $('#settingsModalCloseBtn');
  const settingsUserName = $('#settingsUserName');
  const settingsUserDot = $('#settingsUserDot');
  const sandboxPreviewOverlay = $('#sandboxPreviewOverlay');
  const sandboxPreviewCloseBtn = $('#sandboxPreviewCloseBtn');
  const sandboxPreviewFrame = $('#sandboxPreviewFrame');
  const chatThemeBtnSidebar = $('#chatThemeBtnSidebar');
  const chatThemeSettingsSection = $('#chatThemeSettingsSection');
  const chatThemeGrid = $('#chatThemeGrid');
  const teachVigzoneBtn = $('#teachVigzoneBtn');
  const learningModalOverlay = $('#learningModalOverlay');
  const learningModalCloseBtn = $('#learningModalCloseBtn');
  const learningModalBody = $('#learningModalBody');
  const usageTodayBtn = $('#usageTodayBtn');
  const usageModalOverlay = $('#usageModalOverlay');
  const usageModalCloseBtn = $('#usageModalCloseBtn');
  const usageModalBody = $('#usageModalBody');
  const usageCycleWrap = $('#usageCycleWrap');
  const usageCycleBtn = $('#usageCycleBtn');
  const usageCycleFill = $('#usageCycleFill');
  const usageCycleCenter = $('#usageCycleCenter');
  const usageCyclePopover = $('#usageCyclePopover');
  const usageCycleCloseBtn = $('#usageCycleCloseBtn');
  const usageCyclePercent = $('#usageCyclePercent');
  const usageCycleNote = $('#usageCycleNote');
  const floatingMenuBackdrop = document.createElement('div');
  floatingMenuBackdrop.className = 'floating-menu-backdrop';
  floatingMenuBackdrop.setAttribute('aria-hidden', 'true');
  document.body.appendChild(floatingMenuBackdrop);

  // Keep small floating menus above all chat bubbles by moving them to <body>

  // and positioning them with viewport coordinates. This avoids clipping/stacking
  // issues from the chat scroll container and animated message bubbles.
  if (usageCyclePopover && usageCyclePopover.parentElement !== document.body) document.body.appendChild(usageCyclePopover);
  if (exportMenu && exportMenu.parentElement !== document.body) document.body.appendChild(exportMenu);

  function clampNumber(value, min, max){ return Math.max(min, Math.min(max, value)); }

  function positionFloatingMenu(menu, anchor, preferred='bottom-right'){
    if (!menu || !anchor) return;
    const rect = anchor.getBoundingClientRect();
    const vw = window.innerWidth || document.documentElement.clientWidth;
    const vh = window.innerHeight || document.documentElement.clientHeight;
    menu.style.visibility = 'hidden';
    menu.style.display = menu.classList.contains('visible') ? 'grid' : 'block';
    const mw = menu.offsetWidth || 210;
    const mh = menu.offsetHeight || 140;
    let left;
    let top;
    if (preferred === 'side-left') {
      left = rect.left - mw - 10;
      top = rect.bottom - mh;
    } else if (preferred === 'side-right') {
      left = rect.right + 10;
      top = rect.bottom - mh;
    } else {
      left = rect.right - mw;
      top = rect.bottom + 10;
    }
    if (top + mh > vh - 10) top = rect.top - mh - 10;
    left = clampNumber(left, 10, Math.max(10, vw - mw - 10));
    top = clampNumber(top, 10, Math.max(10, vh - mh - 10));
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.style.visibility = '';
    if (!menu.classList.contains('visible')) menu.style.display = 'none';
  }

  function positionUsageCyclePopover(){ positionFloatingMenu(usageCyclePopover, usageCycleBtn, 'bottom-right'); }
  function positionExportMenu(){ positionFloatingMenu(exportMenu, exportChatBtn, 'side-right'); }
  function anyFloatingMenuOpen(){
    return !!(usageCyclePopover?.classList.contains('visible') || exportMenu?.classList.contains('visible'));
  }
  function hideFloatingMenu(menu){
    if (!menu) return;
    menu.classList.remove('visible');
    menu.style.display = 'none';
    menu.style.visibility = '';
  }

  function showFloatingMenu(menu){
    if (!menu) return;
    menu.classList.add('visible');
    menu.style.display = '';
    menu.style.visibility = '';
  }

  function syncFloatingMenuBackdrop(){
    if (!floatingMenuBackdrop) return;
    floatingMenuBackdrop.classList.toggle('visible', anyFloatingMenuOpen());
  }
  const adminPanelRow = $('#adminPanelRow');
  const adminPanelBtn = $('#adminPanelBtn');
  const adminModalOverlay = $('#adminModalOverlay');
  const adminModalCloseBtn = $('#adminModalCloseBtn');
  const adminModalBody = $('#adminModalBody');
  const apiKeyModeBadge = $('#apiKeyModeBadge');
  const apiKeyInputSection = $('#apiKeyInputSection');
  const apiKeyActiveSection = $('#apiKeyActiveSection');
  const groqKeyInput = $('#groqKeyInput');
  const groqKeyCheckBtn = $('#groqKeyCheckBtn');
  const groqKeyStatus = $('#groqKeyStatus');
  const groqKeyDeactivateBtn = $('#groqKeyDeactivateBtn');
  let greetingText = $('#greetingText');

  const EMPTY_STATE_HTML = `
    <div class="empty-state" id="emptyState">
      <div class="empty-shell">
        <div class="empty-mark"><img src="/static/icons/vigzone-icon.svg?v=logo1-simple" alt="" width="56" height="56" /></div>
        <div class="empty-topline">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"></path></svg>
          Start with a real task
        </div>
        <h1><span class="greeting-mark">\u2731</span><span id="greetingText">Welcome to Vigzone AI</span></h1>
        <p>Open a fresh chat for one focused goal. Tell Vigzone what you are trying to finish, attach useful files, or choose a starter below.</p>
        <div class="starter-row" aria-label="New chat capabilities">
          <div class="starter-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.44 11.05 12.25 20.24a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>
            <span>Attach files</span>
          </div>
          <div class="starter-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><path d="M21 15l-5-5L5 21"></path></svg>
            <span>Use image mode</span>
          </div>
          <div class="starter-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2a5 5 0 0 0-5 5v2a5 5 0 0 0 0 10 5 5 0 0 0 5 3 5 5 0 0 0 5-3 5 5 0 0 0 0-10V7a5 5 0 0 0-5-5z"></path></svg>
            <span>Keep context</span>
          </div>
        </div>
        <div class="suggestions">
          <div class="suggestion" data-prompt="I need to finish this today: [describe the task]. Help me turn it into a clear plan with the next 3 actions." tabindex="0" role="button" aria-label="Turn a task into a plan">
            <div class="suggestion-top">
              <div class="s-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg></div>
              <div><div class="s-title">Turn a task into a plan</div><div class="s-sub">Get next steps for work you need to finish</div></div>
            </div>
          </div>
          <div class="suggestion" data-prompt="Review this text and make it clearer, more professional, and easier to act on: [paste text here]." tabindex="0" role="button" aria-label="Improve writing">
            <div class="suggestion-top">
              <div class="s-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"></path></svg></div>
              <div><div class="s-title">Improve writing</div><div class="s-sub">Polish an email, report, or message</div></div>
            </div>
          </div>
          <div class="suggestion" data-prompt="I have a problem in my project: [describe what is happening]. Ask focused questions, then help me find the cause." tabindex="0" role="button" aria-label="Solve a project problem">
            <div class="suggestion-top">
              <div class="s-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><path d="M12 8v4"></path><path d="M12 16h.01"></path></svg></div>
              <div><div class="s-title">Solve a project problem</div><div class="s-sub">Debug code, logic, or a stuck decision</div></div>
            </div>
          </div>
          <div class="suggestion" data-prompt="Summarize this into decisions, risks, and action items: [paste notes here]." tabindex="0" role="button" aria-label="Summarize notes">
            <div class="suggestion-top">
              <div class="s-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"></path><path d="M14 2v6h6"></path><path d="M8 13h8"></path><path d="M8 17h5"></path></svg></div>
              <div><div class="s-title">Summarize notes</div><div class="s-sub">Extract decisions, risks, and action items</div></div>
            </div>
          </div>
          <div class="suggestion" data-image-prompt="A clean product dashboard for an AI assistant, realistic interface, modern lighting, high detail" tabindex="0" role="button" aria-label="Generate a realistic image concept">
            <div class="suggestion-top">
              <div class="s-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><path d="M21 15l-5-5L5 21"></path></svg></div>
              <div><div class="s-title">Generate a visual</div><div class="s-sub">Create a realistic image or concept mockup</div></div>
            </div>
          </div>
        </div>
      </div>
    </div>`;

  function restoreEmptyState(){
    chatInner.innerHTML = EMPTY_STATE_HTML;
    emptyState = document.getElementById('emptyState');
    greetingText = document.getElementById('greetingText');
    updateGreeting();
    showAllMessages = false;
  }

  // ---------- Multi-conversation store (chat history, like a typical AI chat app) ----------
  const CONV_STORE_KEY_BASE = 'vigzone_conversations_v1';
  const LEGACY_KEY_BASE = 'vigzone_ai_conversation';
  const LAST_SCOPE_KEY = 'vigzone_last_user_scope';
  let accountStorageScope = localStorage.getItem(LAST_SCOPE_KEY) || 'guest';
  let CONV_STORE_KEY = scopedLocalKey(CONV_STORE_KEY_BASE);
  let LEGACY_KEY = scopedLocalKey(LEGACY_KEY_BASE);
  const SIDEBAR_KEY = 'vigzone_sidebar_collapsed';
  const CHAT_THEME_KEY = 'vigzone_doodle_theme';
  const CHAT_THEMES = Object.freeze({
    charcoal: { tone:'dark', browserColor:'#0c0f16' },
    midnight: { tone:'dark', browserColor:'#071827' },
    forest: { tone:'dark', browserColor:'#071b19' },
    plum: { tone:'dark', browserColor:'#1a0e21' },
    ember: { tone:'dark', browserColor:'#21100e' },
    paper: { tone:'light', browserColor:'#f5eedf' }
  });
  const LEGACY_APPEARANCE_KEYS = Object.freeze([
    'vigzone_chat_wallpaper_data_url',
    'vigzone_chat_wallpaper_blur',
    'vigzone_chat_wallpaper_brightness',
    'vigzone_theme'
  ]);

  function safeStorageScope(value){
    return String(value || 'guest').trim().toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'guest';
  }
  function scopedLocalKey(base){
    return `${base}__${safeStorageScope(accountStorageScope)}`;
  }

  function getChatTheme(){
    const active = document.documentElement.getAttribute('data-chat-theme');
    if (CHAT_THEMES[active]) return active;
    try {
      const saved = localStorage.getItem(CHAT_THEME_KEY);
      if (CHAT_THEMES[saved]) return saved;
    } catch {}
    return 'charcoal';
  }

  function applyChatTheme(themeId, persist){
    const next = CHAT_THEMES[themeId] ? themeId : 'charcoal';
    const theme = CHAT_THEMES[next];
    document.documentElement.setAttribute('data-chat-theme', next);
    document.documentElement.setAttribute('data-theme', theme.tone);
    if (persist) {
      try { localStorage.setItem(CHAT_THEME_KEY, next); } catch {}
    }
    document.querySelectorAll('[data-chat-theme-option]').forEach((option) => {
      const selected = option.dataset.chatThemeOption === next;
      option.classList.toggle('selected', selected);
      option.setAttribute('aria-checked', selected ? 'true' : 'false');
      option.tabIndex = selected ? 0 : -1;
    });
    const meta = document.getElementById('themeColorMeta');
    if (meta) meta.setAttribute('content', theme.browserColor);
  }

  function selectChatTheme(themeId){
    document.documentElement.classList.add('theme-transition');
    applyChatTheme(themeId, true);
    window.setTimeout(() => document.documentElement.classList.remove('theme-transition'), 260);
  }

  function clearLegacyAppearanceSettings(){
    try { LEGACY_APPEARANCE_KEYS.forEach((key) => localStorage.removeItem(key)); } catch {}
    document.body.classList.remove('has-chat-wallpaper');
    ['--chat-wallpaper-image', '--chat-wallpaper-blur', '--chat-wallpaper-brightness']
      .forEach((property) => document.documentElement.style.removeProperty(property));
  }

  clearLegacyAppearanceSettings();

  function genId(){
    return 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  }

  // Grapheme-aware truncation. Plain `.slice(0, n)` cuts by UTF-16 code unit,
  // which can split a surrogate pair (breaking many emoji) or a combining
  // sequence (breaking Sinhala and other complex-script characters, plus
  // ZWJ emoji like 👨‍👩‍👧‍👦) right down the middle, leaving mangled output.
  // Intl.Segmenter (supported in all current browsers) splits on real
  // user-perceived characters instead, so truncation always lands on a
  // clean boundary regardless of script or emoji complexity.
  const _graphemeSegmenter = (typeof Intl !== 'undefined' && Intl.Segmenter)
    ? new Intl.Segmenter(undefined, { granularity: 'grapheme' })
    : null;

  function truncateText(text, maxLen){
    text = text || '';
    if (_graphemeSegmenter){
      const chars = Array.from(_graphemeSegmenter.segment(text), s => s.segment);
      return chars.length > maxLen ? chars.slice(0, maxLen).join('') + '…' : text;
    }
    // Fallback: split on code points (not full grapheme clusters), which at
    // least keeps surrogate-pair emoji intact even without Intl.Segmenter.
    const codePoints = Array.from(text);
    return codePoints.length > maxLen ? codePoints.slice(0, maxLen).join('') + '…' : text;
  }

  function titleFromMessages(msgs){
    const firstUser = (msgs || []).find(m => m.role === 'user');
    if (!firstUser) return 'New chat';
    let t = firstUser.displayText !== undefined ? firstUser.displayText : (typeof firstUser.content === 'string' ? firstUser.content : '');
    t = (t || '').replace(/\s+/g, ' ').trim();
    if (!t) return firstUser.imageSrc ? 'Generated image' : 'New chat';
    return truncateText(t, 48);
  }

  function loadStore(){
    let store = null;
    try { store = JSON.parse(localStorage.getItem(CONV_STORE_KEY) || 'null'); } catch { store = null; }
    if (store && store.conversations) {
      store.pins = store.pins || {};
      return store;
    }

    // Migrate the old single-conversation format if present.
    store = { conversations: {}, order: [], activeId: null, pins: {} };
    let legacy = [];
    try { legacy = JSON.parse(localStorage.getItem(LEGACY_KEY) || '[]'); } catch { legacy = []; }
    if (Array.isArray(legacy) && legacy.length) {
      const id = genId();
      store.conversations[id] = { id, title: titleFromMessages(legacy), messages: legacy, createdAt: Date.now(), updatedAt: Date.now() };
      store.order.push(id);
      store.activeId = id;
    }
    return store;
  }

  let store = loadStore();
  let messages = (store.activeId && store.conversations[store.activeId])
          ? store.conversations[store.activeId].messages
          : [];
  let userName = '';
  let streaming = false;
  let currentStreamId = null;
  let isPaused = false;
  // Set while a streaming reply is in flight so pause/resume can control the
  // paced on-screen reveal without losing text already received from Groq.
  let activeStreamRenderer = null;
  let imageMode = false;
  // Message display limit for performance - only show last N messages by default
  let messageDisplayLimit = 50;
  let showAllMessages = false;

  function currentConversation(){
    return (store && store.activeId && store.conversations && store.conversations[store.activeId])
      ? store.conversations[store.activeId]
      : null;
  }

  // The message currently staged from the Reply item in the message context
  // menu, or null if nothing is being quoted.
  // Shape: { role: 'user'|'assistant', fullText: string, index: number|null }
  let quotedMessage = null;

  // Files the user has picked but not yet sent. Each entry:
  // { id, file, name, kind: 'image'|'document', status: 'uploading'|'ready'|'error',
  //   dataUri?, mime?, text?, truncated?, error? }
  let pendingFiles = [];
  const MAX_ATTACHMENTS = 5;
  const MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024;
  const MAX_UPLOAD_SIZE_MB = Math.round(MAX_UPLOAD_SIZE_BYTES / (1024 * 1024));
  let activeWorkspaceId = Number(localStorage.getItem('vigzone_active_workspace_id') || 0) || null;
  let workspaces = [];
  let activeAiMode = localStorage.getItem('vigzone_ai_mode') || 'general';


  // ---------- Living config: no stale hardcoded product text ----------
  let liveConfig = {
    app_name: 'Vigzone AI',
    short_name: 'Vigzone AI',
    build_name: 'Vigzone Brain Pro Suite',
    version: '',
    groq_keys_url: 'https://console.groq.com/keys',
    groq_hint: 'Groq is fast and generous on the free tier — cheaper than most alternatives for a project like this.',
    google_drive_api_key: '',
    google_drive_client_id: '',
    drive_picker_enabled: false,
    new_chat_topline: 'Start with a real task',
    new_chat_subtitle: 'Open a fresh chat for one focused goal. Tell Vigzone AI what you are trying to finish, attach useful files, or choose a starter below.',
    greetings: ['Back at it,', 'Welcome back,', 'Good to see you,', 'Hey there,'],
    labels: { assistant: 'Vigzone AI', settings_signed_in: 'Signed in to Vigzone AI', api_default: 'Groq (default)', api_own: 'Groq (your key)' }
  };

  function applyLiveConfig(cfg = {}){
    liveConfig = {
      ...liveConfig,
      ...cfg,
      labels: {...(liveConfig.labels || {}), ...((cfg && cfg.labels) || {})}
    };

    document.title = liveConfig.app_name || 'Vigzone AI';

    document.querySelectorAll('.brand-name').forEach(el => { el.textContent = liveConfig.app_name || 'Vigzone AI'; });
    document.querySelectorAll('.settings-user-sub').forEach(el => { el.textContent = liveConfig.labels.settings_signed_in || `Signed in to ${liveConfig.app_name}`; });

    const topLine = document.querySelector('.empty-topline');
    if (topLine) {
      const icon = topLine.querySelector('svg');
      topLine.textContent = '';
      if (icon) topLine.appendChild(icon);
      topLine.append(document.createTextNode(' ' + (liveConfig.new_chat_topline || 'Start with a real task')));
    }

    const emptyP = document.querySelector('.empty-state .empty-shell > p');
    if (emptyP) emptyP.textContent = liveConfig.new_chat_subtitle || '';

    const apiHint = document.querySelector('.api-key-hint');
    if (apiHint) {
      const details = apiHint.querySelector('details');
      apiHint.childNodes.forEach(node => {
        if (node.nodeType === Node.TEXT_NODE) node.textContent = '';
      });
      apiHint.insertBefore(document.createTextNode('💡 ' + (liveConfig.groq_hint || 'Groq is available for API access.') + ' '), details || null);
      const link = apiHint.querySelector('a[href*="console.groq.com"]');
      if (link) {
        link.href = liveConfig.groq_keys_url || 'https://console.groq.com/keys';
        link.textContent = (liveConfig.groq_keys_url || 'https://console.groq.com/keys').replace(/^https?:\/\//, '');
      }
    }

    if (apiKeyModeBadge) {
      const usingOwn = apiKeyModeBadge.classList.contains('own-key');
      apiKeyModeBadge.textContent = usingOwn ? (liveConfig.labels.api_own || 'Groq (your key)') : (liveConfig.labels.api_default || 'Groq (default)');
    }

    const manifestLink = document.querySelector('link[rel="manifest"]');
    if (manifestLink) manifestLink.setAttribute('data-app-name', liveConfig.app_name || 'Vigzone AI');

    updateGreeting?.();
  }

  async function loadLiveConfig(){
    try {
      const res = await fetch('/api/public/config', { credentials:'same-origin' });
      if (!res.ok) return;
      const cfg = await res.json();
      applyLiveConfig(cfg);
    } catch {}
  }

  const VIGZONE_ICON = '/static/icons/vigzone-icon.svg?v=logo1-simple';
  const ICON_IMAGE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><path d="M21 15l-5-5L5 21"></path></svg>';
  const ICON_DOC = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>';
  const ICON_ARCHIVE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>';
  const ICON_AV = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>';
  const ICON_COPY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
  const ICON_CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
  const ICON_REPLY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 17 4 12 9 7"></polyline><path d="M20 18v-2a4 4 0 0 0-4-4H4"></path></svg>';
  const ICON_THUMBS_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v12"></path><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"></path></svg>';
  const ICON_THUMBS_DOWN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V2"></path><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z"></path></svg>';
  const ICON_SPEAKER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M18.36 5.64a9 9 0 0 1 0 12.73"></path></svg>';
  const ICON_SPEAKER_STOP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="1.5"></rect></svg>';

  function escapeHtml(str){
    return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  // Syntax highlighting for code blocks
  function highlightCode(code, lang){
    const keywords = ['def','class','if','elif','else','for','while','return','import','from','as','try','except',
      'finally','with','raise','pass','break','continue','and','or','not','in','is','lambda','yield','global',
      'nonlocal','assert','del','async','await','const','let','var','function','new','this','extends','export',
      'default','catch','throw','typeof','instanceof','void','delete','of','static','public','private','protected',
      'interface','type','enum','implements','package','abstract','final','native','synchronized','transient',
      'volatile','throws','super','true','false','null','undefined','None','True','False','self',
      // Go
      'func','defer','go','chan','select','range','struct','fallthrough','goto',
      // Rust
      'fn','let','mut','impl','trait','match','pub','use','mod','crate','where','unsafe','dyn','move','ref','loop',
      // C / C++ / C#
      'include','define','typedef','namespace','template','sizeof','nullptr','NULL','char','double','long','short',
      'unsigned','signed','extern','inline','using','virtual','override','friend',
      // PHP
      'echo','require','require_once','include_once','foreach','elseif','endif','array','isset','empty',
      // Ruby
      'end','module','then','unless','until','elsif','require','nil','begin','rescue','ensure','raise',
      'attr_accessor','attr_reader','attr_writer'
    ];
    const builtins = ['print','len','range','str','int','float','list','dict','set','tuple','bool','isinstance',
      'getattr','setattr','hasattr','open','input','map','filter','zip','enumerate','sorted','reversed','min','max',
      'sum','abs','round','any','all','next','iter','format','super','property','classmethod','staticmethod',
      'console','document','window','Math','JSON','Array','Object','String','Number','Boolean','Date','RegExp',
      'Error','Promise','Map','Set','Symbol','Proxy','Reflect',
      'fmt','Println','Printf','Sprintf','append','cap','copy',
      'println','vec','Vec','Box','Option','Some','None','Ok','Err','Self',
      'printf','scanf','malloc','free','puts'
    ];
    let result = '';
    let i = 0;
    const src = code;
    while(i < src.length){
      // Decorators / annotations (e.g. @staticmethod, @Override, @app.route)
      if(src[i] === '@' && /[A-Za-z_]/.test(src[i+1] || '')){
        let end = i + 1;
        while(end < src.length && /[A-Za-z0-9_]/.test(src[end])) end++;
        result += '<span class="tok-deco">' + escapeHtml(src.slice(i, end)) + '</span>';
        i = end;
        continue;
      }
      // Comments
      if(src[i] === '#'){
        let end = src.indexOf('\n', i);
        if(end === -1) end = src.length;
        result += '<span class="tok-cmt">' + escapeHtml(src.slice(i, end)) + '</span>';
        i = end;
        continue;
      }
      if(src[i] === '/' && src[i+1] === '/'){
        let end = src.indexOf('\n', i);
        if(end === -1) end = src.length;
        result += '<span class="tok-cmt">' + escapeHtml(src.slice(i, end)) + '</span>';
        i = end;
        continue;
      }
      if(src[i] === '/' && src[i+1] === '*'){
        let end = src.indexOf('*/', i+2);
        if(end === -1) end = src.length; else end += 2;
        result += '<span class="tok-cmt">' + escapeHtml(src.slice(i, end)) + '</span>';
        i = end;
        continue;
      }
      // Strings (single, double, triple, template literals)
      if(src[i] === '"' || src[i] === "'" || src[i] === '`'){
        const q = src[i];
        let end = i + 1;
        // triple quotes
        if(src.slice(i, i+3) === q+q+q){
          end = src.indexOf(q+q+q, i+3);
          if(end === -1) end = src.length; else end += 3;
        } else {
          while(end < src.length && src[end] !== q && src[end] !== '\n'){
            if(src[end] === '\\') end++;
            end++;
          }
          if(end < src.length && src[end] === q) end++;
        }
        const raw = src.slice(i, end);
        const escRaw = escapeHtml(raw);
        let inner;
        if(q !== '`' && /^f["']/.test(raw)){
          // Python f-string: highlight {expr} segments
          inner = escRaw.replace(/\{([^}]+)\}/g, '</span><span class="tok-op">{</span>$1<span class="tok-op">}</span><span class="tok-str">');
        } else if(q === '`'){
          // JS template literal: highlight ${expr} segments
          inner = escRaw.replace(/\$\{([^}]+)\}/g, '</span><span class="tok-op">${</span>$1<span class="tok-op">}</span><span class="tok-str">');
        } else {
          inner = escRaw;
        }
        result += '<span class="tok-str">' + inner + '</span>';
        i = end;
        continue;
      }
      // Numbers
      if(/[0-9]/.test(src[i]) && (i === 0 || /[\s,;:=+\-*/%(<>[\]{}!&|^~]/.test(src[i-1]))){
        let end = i;
        while(end < src.length && /[0-9.xXa-fA-FeE_]/.test(src[end])) end++;
        result += '<span class="tok-num">' + src.slice(i, end) + '</span>';
        i = end;
        continue;
      }
      // Identifiers (keywords, builtins, functions)
      if(/[a-zA-Z_]/.test(src[i])){
        let end = i;
        while(end < src.length && /[a-zA-Z0-9_]/.test(src[end])) end++;
        const word = src.slice(i, end);
        if(keywords.includes(word)){
          result += '<span class="tok-kw">' + word + '</span>';
        } else if(builtins.includes(word)){
          result += '<span class="tok-bi">' + word + '</span>';
        } else if(end < src.length && src[end] === '('){
          result += '<span class="tok-fn">' + word + '</span>';
        } else {
          result += word;
        }
        i = end;
        continue;
      }
      // Operators
      if('+-*/%=<>!&|^~?:'.includes(src[i])){
        result += '<span class="tok-op">' + escapeHtml(src[i]) + '</span>';
        i++;
        continue;
      }
      result += escapeHtml(src[i]);
      i++;
    }

    // Highlight the type/class/function name that follows a declaration keyword,
    // regardless of which language fence was used (works across Python/JS/Go/Rust/Java/C#/etc.)
    result = result.replace(/(<span class="tok-kw">(?:class|struct|interface|trait|enum)<\/span>\s+)(\w+)/g, '$1<span class="tok-fn">$2</span>');
    result = result.replace(/(<span class="tok-kw">(?:def|function|fn|func)<\/span>\s+)(\w+)/g, '$1<span class="tok-fn">$2</span>');

    return result;
  }

  // ---------- "Complex request" detection (mirrors the backend's own
  // website/code/long-form regexes in vigzone_ai.py, so the frontend shows
  // the glitchy "thinking" treatment for the same kinds of requests that
  // get a bigger token budget on the server) ----------
  const COMPLEX_WEBSITE_RE = /\b(web ?site|web ?page|web ?app|webapp|landing page|portfolio (?:site|page|website)|home ?page|homepage|login page|signup page|dashboard ui|single[- ]page app|spa|html5?|css3?|tailwind|bootstrap|front[- ]?end|frontend|web design|ui\/?ux|react (?:app|component|site|website)|vue (?:app|component|site)|svelte (?:app|site)|online store|web ?store|web ?shop|menu page|booking site|reservation site|coming soon page|(?:build|create|make|design|develop|write|code|generate)\s+(?:me\s+)?(?:a|an|the\s+)?(?:modern|responsive|professional|full|complete|excellent\s+)?(?:web ?site|site|web ?page|web ?app|landing page)|(?:web ?site|site|web ?page|landing page|web ?app)\s+(?:for|about)\s+(?:my|a|an|the)?\s*[\w &'-]{2,80}|\.html\b|index\.html)\b/i;
  const COMPLEX_CODE_RE = /\b(function|class \w|script|program|algorithm|snippet|api endpoint|refactor|debug|code for|code (?:to|that)|write (?:a|the) code|python|javascript|typescript|java\b|c\+\+|c#|sql query|regex)\b/i;
  const COMPLEX_LONGFORM_RE = /\b(explain|step[- ]by[- ]step|write a|essay|guide|tutorial|list all|detail|elaborate|summarize|generate|create a|compare|difference between|how does|how do|walk me through)\b/i;
  const CONTINUATION_RE = /^\s*(continue|keep going|go on|more|next|and then|carry on|finish (?:it|that|this)|what('?s| is) next)[\s.!?]*$/i;

  function isComplexRequest(text, priorAssistantText){
    if (!text) return false;
    // A bare "continue" inherits the complexity of what it's continuing,
    // since it carries no topic keywords of its own.
    const probe = CONTINUATION_RE.test(text) && priorAssistantText
      ? text + ' ' + priorAssistantText
      : text;
    return COMPLEX_WEBSITE_RE.test(probe) || COMPLEX_CODE_RE.test(probe) || COMPLEX_LONGFORM_RE.test(probe);
  }

  // ---------- "Thinking" glitch tag shown beside the avatar ----------
  function showThinkingTag(avatarEl){
    const tag = document.createElement('div');
    tag.className = 'thinking-tag';
    tag.innerHTML = '<span class="dot"></span><span>Thinking</span>';
    avatarEl.insertAdjacentElement('afterend', tag);
    return tag;
  }
  function clearAvatarThinkingState(avatarEl, tagEl){
    if (avatarEl) avatarEl.classList.remove('pulsing', 'thinking-glitch');
    if (tagEl && tagEl.remove) tagEl.remove();
  }

  // ---------- Extracting fenced code blocks as "files" ----------
  const FILE_EXT_MAP = {
    python:'py', javascript:'js', typescript:'ts', jsx:'jsx', tsx:'tsx',
    java:'java', kotlin:'kt', swift:'swift',
    c:'c', cpp:'cpp', csharp:'cs',
    go:'go', rust:'rs', php:'php', ruby:'rb',
    html:'html', css:'css', scss:'scss',
    sql:'sql', bash:'sh', shell:'sh', sh:'sh',
    json:'json', yaml:'yml', yml:'yml', xml:'xml',
    markdown:'md', md:'md', dockerfile:'dockerfile', plaintext:'txt', text:'txt'
  };

  // Pull fenced code blocks out of the raw reply text, plus whatever label
  // (e.g. "**index.html**" or "`UserService.java`") sits right before the
  // fence, so each block can be offered as a named, downloadable file.
  function extractCodeFiles(text){
    if (!text) return [];
    const files = [];
    const fenceRe = /```(\w*)\n?([\s\S]*?)```/g;
    let match, idx = 0;
    while ((match = fenceRe.exec(text)) !== null) {
      const lang = (match[1] || '').toLowerCase();
      const code = match[2].replace(/\n$/, '');
      if (!code.trim()) continue;
      idx += 1;

      // Look at the ~120 chars right before the fence for a filename label.
      const before = text.slice(Math.max(0, match.index - 120), match.index);
      const labelMatch = before.match(/[`*]{1,2}([\w.\-]+\.[A-Za-z0-9]{1,10})[`*]{0,2}\s*:?\s*$/);
      let name = labelMatch ? labelMatch[1] : null;

      if (!name) {
        // Fall back to sniffing an identifier out of the code itself.
        const classMatch = code.match(/\b(?:public\s+|export\s+)?(?:class|interface)\s+(\w+)/);
        const ext = FILE_EXT_MAP[lang] || 'txt';
        if (lang === 'html' || /^\s*<!doctype html/i.test(code)) name = 'index.html';
        else if (lang === 'css') name = 'style.css';
        else if ((lang === 'javascript' || lang === 'js') && /<html|<!doctype/i.test(text) === false && idx === 1) name = 'script.js';
        else if (classMatch) name = `${classMatch[1]}.${ext}`;
        else name = `file${idx}.${ext}`;
      }
      files.push({ name, lang, code, lines: code.split('\n').length });
    }
    return files;
  }

  // Decide whether a reply is "heavy" enough to warrant a downloadable file
  // bundle instead of (or in addition to) inline code blocks: a website-type
  // request, several files at once, or one long block.
  function isHeavyCodeResponse(userText, files){
    if (!files.length) return false;
    if (userText && COMPLEX_WEBSITE_RE.test(userText)) return true;
    if (files.length >= 2) return true;
    return files.some(f => f.lines > 35);
  }

  let _jsZipLoadPromise = null;
  function ensureJSZip(){
    if (window.JSZip) return Promise.resolve(window.JSZip);
    if (_jsZipLoadPromise) return _jsZipLoadPromise;
    _jsZipLoadPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = '/static/vendor/jszip.min.js';
      s.onload = () => resolve(window.JSZip);
      s.onerror = () => reject(new Error('Could not load the zip library'));
      document.head.appendChild(s);
    });
    return _jsZipLoadPromise;
  }

  function downloadTextFile(name, text){
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  }

  function fileTypeIcon(){
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="17" height="17"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>';
  }

  // Build the Claude-style "files ready to download" panel and append it to
  // the message bubble.
  function buildFileBundlePanel(files){
    const panel = document.createElement('div');
    panel.className = 'file-bundle';

    files.forEach(f => {
      const ext = (f.name.split('.').pop() || 'txt');
      const row = document.createElement('div');
      row.className = 'file-bundle-item';
      row.innerHTML = `
        <div class="file-bundle-icon">${fileTypeIcon()}</div>
        <div class="file-bundle-meta">
          <div class="file-bundle-name">${escapeHtml(f.name.replace(/\.[^.]+$/, ''))}</div>
          <div class="file-bundle-ext">${escapeHtml(ext)}</div>
        </div>
        <button class="file-bundle-dl" type="button">Download</button>
      `;
      row.querySelector('.file-bundle-dl').addEventListener('click', () => downloadTextFile(f.name, f.code));
      panel.appendChild(row);
    });

    if (files.length > 1) {
      const allBtn = document.createElement('button');
      allBtn.className = 'file-bundle-all';
      allBtn.type = 'button';
      allBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="15" height="15"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download all';
      allBtn.addEventListener('click', async () => {
        const original = allBtn.innerHTML;
        allBtn.textContent = 'Zipping…';
        try {
          const JSZip = await ensureJSZip();
          const zip = new JSZip();
          files.forEach(f => zip.file(f.name, f.code));
          const blob = await zip.generateAsync({ type: 'blob' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url; a.download = 'vigzone-files.zip';
          document.body.appendChild(a); a.click();
          document.body.removeChild(a); URL.revokeObjectURL(url);
        } catch (e) {
          // Fall back to downloading each file individually if the zip lib fails to load.
          files.forEach(f => downloadTextFile(f.name, f.code));
        } finally {
          allBtn.innerHTML = original;
        }
      });
      panel.appendChild(allBtn);
    }
    return panel;
  }

  // Called once a reply has finished streaming: if it looks like a heavy
  // code/website build, attach a downloadable file bundle under the message.
  function attachFileBundleIfHeavy(bubbleEl, fullReplyText, userText){
    const files = extractCodeFiles(fullReplyText);
    if (!isHeavyCodeResponse(userText, files)) return;
    const caption = document.createElement('div');
    caption.className = 'file-bundle-caption';
    caption.textContent = files.length > 1
      ? `📦 Implemented ${files.length} files — ready to download individually or as a zip.`
      : `📦 Implemented ${files[0].name} — ready to download.`;
    bubbleEl.appendChild(caption);
    bubbleEl.appendChild(buildFileBundlePanel(files));
    syncAssistantOutputPresentation(bubbleEl, true);
  }

  // Enhance code blocks with header, copy, and download buttons
  function enhanceCodeBlocks(container){
    const extMap = {
      python:'py', javascript:'js', typescript:'ts', jsx:'jsx', tsx:'tsx',
      java:'java', kotlin:'kt', swift:'swift',
      c:'c', cpp:'cpp', csharp:'cs',
      go:'go', rust:'rs', php:'php', ruby:'rb',
      html:'html', css:'css', scss:'scss',
      sql:'sql', bash:'sh', shell:'sh', sh:'sh',
      json:'json', yaml:'yml', yml:'yml', xml:'xml',
      markdown:'md', md:'md', dockerfile:'dockerfile', plaintext:'txt', text:'txt'
    };
    container.querySelectorAll('pre').forEach(pre => {
      if(pre.closest('.code-block-wrap')) return;
      const code = pre.querySelector('code');
      if(!code) return;
      const raw = code.textContent;

      let lang = (pre.dataset.lang || '').toLowerCase();
      // detect language from the first line or content if not specified
      if (!lang) {
        const firstLine = raw.split('\n')[0] || '';
        if(firstLine.match(/^(def |class |import |from |print\()/)) lang = 'python';
        else if(firstLine.match(/^(interface |type \w+\s*=|enum )/)) lang = 'typescript';
        else if(firstLine.match(/^(function |const |let |var |import |export )/)) lang = 'javascript';
        else if(firstLine.match(/^(package |func )/)) lang = 'go';
        else if(firstLine.match(/^(fn |use |mod |pub )/)) lang = 'rust';
        else if(firstLine.match(/^(<\?php)/)) lang = 'php';
        else if(firstLine.match(/^(#include|using namespace)/)) lang = 'cpp';
        else if(firstLine.match(/^(public |private |package |import )/)) lang = 'java';
        else if(firstLine.match(/^(&lt;|<!DOCTYPE|<html)/i)) lang = 'html';
        else if(firstLine.match(/^(SELECT |INSERT |UPDATE |DELETE |CREATE )/i)) lang = 'sql';
        else if(firstLine.match(/^(#!\/|echo |cd |ls |mkdir )/)) lang = 'bash';
        else if(raw.trim().match(/^[{[]/)) lang = 'json';
      }

      // wrap
      const wrap = document.createElement('div');
      wrap.className = 'code-block-wrap';
      const header = document.createElement('div');
      header.className = 'code-block-header';
      header.innerHTML = `<span class="code-lang">${lang || 'code'}</span>
      <div class="code-block-actions">
        <button class="code-copy-btn" title="Copy code" aria-label="Copy code">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
        </button>
        <button class="code-download-btn" title="Download code" aria-label="Download code">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
        </button>
      </div>`;
      const looksLikeHtml = (lang === 'html') || /^\s*(?:<!doctype html|<html|<head|<body)/i.test(raw);
      if (looksLikeHtml) {
        const previewBtn = document.createElement('button');
        previewBtn.className = 'code-preview-btn';
        previewBtn.title = 'Preview website';
        previewBtn.setAttribute('aria-label', 'Preview website');
        previewBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
        previewBtn.addEventListener('click', () => {
          openSandboxedWebsitePreview(raw);
        });
        const actions = header.querySelector('.code-block-actions');
        if (actions) actions.insertBefore(previewBtn, actions.firstChild);
      }
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(header);
      wrap.appendChild(pre);
      // syntax highlight
      code.innerHTML = highlightCode(raw, lang);
      // store raw text for copy/download
      wrap.dataset.raw = raw;
      wrap.dataset.lang = lang || 'code';
      // copy button
      header.querySelector('.code-copy-btn').addEventListener('click', function(){
        navigator.clipboard.writeText(raw).then(() => {
          this.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
          setTimeout(() => {
            this.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
          }, 1500);
        });
      });
      // download button
      header.querySelector('.code-download-btn').addEventListener('click', function(){
        const ext = extMap[lang] || 'txt';
        const blob = new Blob([raw], {type:'text/plain'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `code.${ext}`;
        document.body.appendChild(a); a.click();
        document.body.removeChild(a); URL.revokeObjectURL(url);
      });
    });
  }

  function closeSandboxedWebsitePreview(){
    sandboxPreviewOverlay?.classList.remove('visible');
    if (sandboxPreviewFrame) {
      sandboxPreviewFrame.srcdoc = '<!doctype html><title>Preview closed</title>';
    }
  }

  function openSandboxedWebsitePreview(html){
    if (!sandboxPreviewOverlay || !sandboxPreviewFrame) {
      downloadTextFile('index.html', html);
      return;
    }
    sandboxPreviewFrame.srcdoc = String(html || '');
    sandboxPreviewOverlay.classList.add('visible');
  }

  sandboxPreviewCloseBtn?.addEventListener('click', closeSandboxedWebsitePreview);
  sandboxPreviewOverlay?.addEventListener('click', event => {
    if (event.target === sandboxPreviewOverlay) closeSandboxedWebsitePreview();
  });

  // Safe markdown rendering with DeepSeek-R1 thinking parser & Live Code Sandbox runner
  function renderContent(text){
    if (!text) return '';
    let thinkHtml = '';
    let mainText = text;

    // DeepSeek-R1 <think> tag parser
    const thinkOpen = mainText.indexOf('<think>');
    if (thinkOpen !== -1) {
      const thinkClose = mainText.indexOf('</think>');
      let rawThink = '';
      if (thinkClose !== -1) {
        rawThink = mainText.slice(thinkOpen + 7, thinkClose).trim();
        mainText = (mainText.slice(0, thinkOpen) + '\n' + mainText.slice(thinkClose + 8)).trim();
      } else {
        rawThink = mainText.slice(thinkOpen + 7).trim();
        mainText = mainText.slice(0, thinkOpen).trim();
      }
      if (rawThink) {
        thinkHtml = `
          <div class="think-accordion">
            <div class="think-header" onclick="this.parentElement.classList.toggle('collapsed')">
              <span class="think-meta"><span class="think-pulse-dot"></span> 🧠 Thought Process</span>
              <span class="think-toggle-btn">Toggle ▼</span>
            </div>
            <div class="think-body">${escapeHtml(rawThink)}</div>
          </div>`;
      }
    }

    const escaped = escapeHtml(mainText);
    let withFences = escaped.replace(/```(\w*)\n?([\s\S]*?)```/g, (m, lang, code) => {
      const cleanLang = (lang || '').toLowerCase().trim();
      const isRunnable = ['html', 'htm', 'svg', 'xml', 'javascript', 'js'].includes(cleanLang);
      const runBtn = isRunnable
        ? `<button class="run-sandbox-btn" onclick="openLiveCodeSandbox(this)" type="button">▶️ Run Preview</button>`
        : '';
      return `
        <div class="code-card-wrap">
          <div class="code-block-header">
            <span>${cleanLang || 'code'}</span>
            <div class="code-actions-group">
              ${runBtn}
              <button class="copy-code-btn" onclick="copyCodeSnippet(this)" type="button">Copy</button>
            </div>
          </div>
          <pre data-lang="${cleanLang}"><code>${code}</code></pre>
        </div>`;
    });

    const openFence = withFences.match(/```(\w*)\n?([\s\S]*)$/);
    if (openFence) {
      withFences = withFences.slice(0, openFence.index) +
              `<pre data-lang="${openFence[1] || ''}"><code>${openFence[2]}</code></pre>`;
    }
    const withInline = withFences.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    const withBold = withInline.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return thinkHtml + withBold;
  }

  function storageSafeStore(source){
    const copy = JSON.parse(JSON.stringify(source || {conversations:{}, order:[], activeId:null, pins:{}}));
    let strippedImages = 0;
    Object.values(copy.conversations || {}).forEach((conversation) => {
      (conversation.messages || []).forEach((message) => {
        if (typeof message.imageSrc === 'string' &&
            message.imageSrc.startsWith('data:') &&
            message.imageSrc.length > 350000) {
          delete message.imageSrc;
          message.imageStorageNote = 'Large generated image omitted from browser storage.';
          strippedImages += 1;
        }
        (message.attachments || []).forEach((attachment) => {
          if (attachment && typeof attachment.dataUri === 'string' && attachment.dataUri.length > 180000) {
            delete attachment.dataUri;
          }
        });
      });
    });
    return {copy, strippedImages};
  }

  function persistStore(){
    try {
      localStorage.setItem(CONV_STORE_KEY, JSON.stringify(store));
      return;
    } catch (error) {
      const safe = storageSafeStore(store);
      localStorage.setItem(CONV_STORE_KEY, JSON.stringify(safe.copy));
      if (safe.strippedImages) {
        console.warn(`${safe.strippedImages} large generated image(s) were kept in this tab but omitted from browser history storage.`);
      }
    }
  }

  function saveConversation(){
    if (!store.activeId) {
      const id = genId();
      store.activeId = id;
      store.order.push(id);
      store.conversations[id] = { id, title: 'New chat', messages, createdAt: Date.now(), updatedAt: Date.now() };
    }
    const conv = store.conversations[store.activeId];
    conv.messages = messages;
    conv.updatedAt = Date.now();
    if (!conv.title || conv.title === 'New chat') conv.title = titleFromMessages(messages);
    persistStore();
    renderHistoryList();
    refreshBrainIfOpen();
  }

  function renderHistoryList(){
    store.pins = store.pins || {};
    const ids = Object.keys(store.conversations)
            .filter(id => store.conversations[id])
            .sort((a, b) => {
              const pa = store.pins[a] ? 1 : 0;
              const pb = store.pins[b] ? 1 : 0;
              if (pa !== pb) return pb - pa;
              if (pa && pb) return (store.pins[b] || 0) - (store.pins[a] || 0);
              return (store.conversations[b].updatedAt || 0) - (store.conversations[a].updatedAt || 0);
            });

    if (!ids.length) {
      historyList.innerHTML = `<div class="history-empty">No saved chats yet. Start with one focused task, then it will appear here.</div>`;
      return;
    }
    historyList.innerHTML = ids.map(id => {
      const c = store.conversations[id];
      const activeClass = id === store.activeId ? ' active' : '';
      const pinnedClass = store.pins[id] ? ' pinned' : '';
      const pinTitle = store.pins[id] ? 'Unpin chat' : 'Pin chat';
      return `
      <div class="history-item${activeClass}${pinnedClass}" data-id="${id}" tabindex="0" role="button" aria-label="${escapeHtml(c.title || 'New chat')}">
        <span class="history-title">${escapeHtml(c.title || 'New chat')}</span>
        <button class="history-pin" data-pin="${id}" aria-label="${pinTitle}" title="${pinTitle}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.05" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4.5l5 5-3.2 3.2.8 4.6-1.4 1.4-4.6-.8L7.9 21H6.5v-1.4l3.1-3.2-.8-4.6 1.4-1.4 4.3.8 3.2-3.2-3.2-3.5Z"></path></svg>
        </button>
        <button class="history-delete" data-delete="${id}" aria-label="Delete chat" title="Delete chat">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6M14 11v6"></path></svg>
        </button>
      </div>`;
    }).join('');
  }

  function switchConversation(id){
    if (id === store.activeId) return;
    const c = store.conversations[id];
    if (!c) return;
    store.activeId = id;
    messages = c.messages;
    persistStore();
    showAllMessages = false;
    renderAll();
    renderHistoryList();
    if (isMobile()) setSidebarCollapsed(true);
  }

  function togglePinConversation(id){
    if (!store.conversations[id]) return;
    store.pins = store.pins || {};
    if (store.pins[id]) delete store.pins[id];
    else store.pins[id] = Date.now();
    persistStore();
    renderHistoryList();
    refreshBrainIfOpen();
  }

  function deleteConversation(id){
    if (!store.conversations[id]) return;
    delete store.conversations[id];
    if (store.pins) delete store.pins[id];
    store.order = store.order.filter(x => x !== id);
    if (store.activeId === id) {
      store.activeId = null;
      messages = [];
      showAllMessages = false;
      renderAll();
    }
    persistStore();
    renderHistoryList();
    refreshBrainIfOpen();
  }

  historyList.addEventListener('click', (e) => {
    const pinBtn = e.target.closest('[data-pin]');
    if (pinBtn) { e.stopPropagation(); togglePinConversation(pinBtn.dataset.pin); return; }

    const delBtn = e.target.closest('[data-delete]');
    if (delBtn) { e.stopPropagation(); deleteConversation(delBtn.dataset.delete); return; }

    const item = e.target.closest('.history-item');
    if (item) switchConversation(item.dataset.id);
  });


  function switchAccountStorageScope(user){
    const nextScope = safeStorageScope((user && (user.id || user.email)) || 'guest');
    if (nextScope === accountStorageScope) return;

    // Save whatever anonymous/previous state exists before switching.
    try { persistStore(); } catch {}

    accountStorageScope = nextScope;
    CONV_STORE_KEY = scopedLocalKey(CONV_STORE_KEY_BASE);
    LEGACY_KEY = scopedLocalKey(LEGACY_KEY_BASE);
    BRAIN_META_KEY = scopedLocalKey(BRAIN_META_KEY_BASE);
    localStorage.setItem(LAST_SCOPE_KEY, accountStorageScope);

    store = loadStore();
    messages = (store.activeId && store.conversations[store.activeId])
      ? store.conversations[store.activeId].messages
      : [];

    showAllMessages = false;
    renderHistoryList();
    renderAll();
    refreshBrainIfOpen();
  }

  function startNewChat(){
    messages = [];
    pendingFiles = [];
    setImageMode(false);
    store.activeId = null;
    showAllMessages = false;
    renderAll();
    setTimeout(renderContinueBanner, 80);
    renderAttachmentsBar();
    renderHistoryList();
    if (isMobile()) setSidebarCollapsed(true);
    input.focus();
  }



  // ---------- Collapsed sidebar floating quick launcher ----------
  const sidebarQuickLauncher = $('#sidebarQuickLauncher');
  const quickLauncherToggle = $('#quickLauncherToggle');
  const quickLauncherPanel = $('#quickLauncherPanel');
  const quickThemeBtn = $('#quickThemeBtn');
  const quickWorkspaceBtn = $('#quickWorkspaceBtn');
  const quickLearningBtn = $('#quickLearningBtn');
  const quickBrainBtn = $('#quickBrainBtn');
  const quickUsageBtn = $('#quickUsageBtn');
  const quickExportBtn = $('#quickExportBtn');
  const quickSettingsBtn = $('#quickSettingsBtn');
  const quickAdminBtn = $('#quickAdminBtn');

  function closeQuickLauncher(){
    sidebarQuickLauncher?.classList.remove('open');
    quickLauncherToggle?.setAttribute('aria-expanded', 'false');
    quickLauncherToggle?.setAttribute('aria-label', 'Open quick tools');
    quickLauncherPanel?.setAttribute('aria-hidden', 'true');
  }

  function toggleQuickLauncher(e){
    e?.preventDefault?.();
    e?.stopPropagation?.();
    if (!sidebarQuickLauncher) return;
    const open = !sidebarQuickLauncher.classList.contains('open');
    sidebarQuickLauncher.classList.toggle('open', open);
    quickLauncherToggle?.setAttribute('aria-expanded', open ? 'true' : 'false');
    quickLauncherToggle?.setAttribute('aria-label', open ? 'Close quick tools' : 'Open quick tools');
    quickLauncherPanel?.setAttribute('aria-hidden', open ? 'false' : 'true');
    syncQuickAdminButton();
  }

  function syncQuickAdminButton(){
    if (!quickAdminBtn) return;
    const row = $('#adminPanelRow');
    const visible = row && getComputedStyle(row).display !== 'none';
    quickAdminBtn.style.display = visible ? 'flex' : 'none';
  }

  function quickClick(target, close=true){
    if (!target) return;
    if (close) closeQuickLauncher();
    target.click();
  }

  quickLauncherToggle?.addEventListener('click', toggleQuickLauncher);
  quickThemeBtn?.addEventListener('click', () => {
    closeQuickLauncher();
    openChatThemePicker();
  });
  quickWorkspaceBtn?.addEventListener('click', () => quickClick($('#workspaceSidebarBtn')));
  quickLearningBtn?.addEventListener('click', () => quickClick($('#teachVigzoneBtn')));
  quickBrainBtn?.addEventListener('click', () => quickClick($('#vigzoneBrainBtn')));
  quickUsageBtn?.addEventListener('click', () => quickClick($('#usageTodayBtn')));
  quickSettingsBtn?.addEventListener('click', () => quickClick($('#settingsBtn')));
  quickAdminBtn?.addEventListener('click', () => quickClick($('#adminPanelBtn')));

  quickExportBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeQuickLauncher();
    if (!exportMenu) return;
    const open = !exportMenu.classList.contains('visible');
    exportMenu.classList.toggle('visible', open);
    floatingMenuBackdrop.classList.toggle('visible', open);
    if (open) {
      positionFloatingMenu(exportMenu, quickExportBtn, 'top-left');
      requestAnimationFrame(() => positionFloatingMenu(exportMenu, quickExportBtn, 'top-left'));
    }
  });

  document.addEventListener('click', (e) => {
    if (sidebarQuickLauncher?.classList.contains('open') && !sidebarQuickLauncher.contains(e.target)) {
      closeQuickLauncher();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeQuickLauncher();
  });

  try {
    new MutationObserver(() => {
      if (!sidebar?.classList.contains('collapsed')) closeQuickLauncher();
      syncQuickAdminButton();
    }).observe(sidebar, { attributes:true, attributeFilter:['class'] });
    const adminRow = $('#adminPanelRow');
    if (adminRow) new MutationObserver(syncQuickAdminButton).observe(adminRow, { attributes:true, attributeFilter:['style', 'class'] });
  } catch {}

  syncQuickAdminButton();


  // ---------- Vigzone Brain: visual memory room / Life OS ----------
  const BRAIN_META_KEY_BASE = 'vigzone_brain_meta_v1';
  let BRAIN_META_KEY = scopedLocalKey(BRAIN_META_KEY_BASE);
  let brainActiveTab = 'overview';

  function loadBrainMeta(){
    try {
      const meta = JSON.parse(localStorage.getItem(BRAIN_META_KEY) || '{}');
      return {
        done: meta.done || {},
        pinned: meta.pinned || {},
        notes: meta.notes || {},
      };
    } catch {
      return { done: {}, pinned: {}, notes: {} };
    }
  }

  function saveBrainMeta(meta){
    try { localStorage.setItem(BRAIN_META_KEY, JSON.stringify(meta || {done:{}, pinned:{}, notes:{}})); } catch {}
  }

  function brainMsgText(m){
    if (!m) return '';
    if (typeof m.displayText === 'string') return m.displayText;
    if (typeof m.content === 'string') return m.content;
    if (Array.isArray(m.content)) {
      return m.content.map(part => {
        if (typeof part === 'string') return part;
        if (part && part.type === 'text') return part.text || '';
        return '';
      }).join(' ');
    }
    return '';
  }

  function brainPlainText(text, max = 240){
    return truncateText(String(text || '').replace(/\s+/g, ' ').trim(), max);
  }

  function brainAllConversations(){
    const convs = Object.values((store && store.conversations) || {}).filter(Boolean);
    return convs.sort((a,b) => {
      const meta = loadBrainMeta();
      const pa = meta.pinned?.[a.id] ? 1 : 0;
      const pb = meta.pinned?.[b.id] ? 1 : 0;
      if (pa !== pb) return pb - pa;
      return (b.updatedAt || b.createdAt || 0) - (a.updatedAt || a.createdAt || 0);
    });
  }

  const BRAIN_CATEGORIES = [
    { id:'projects', icon:'🚀', name:'Projects', terms:/\b(project|vigzone|app|system|feature|implement|build|deploy|railway|dashboard|workspace)\b/i },
    { id:'code', icon:'💻', name:'Code', terms:/\b(code|bug|error|fix|debug|javascript|python|html|css|api|zip|repo|backend|frontend|function|database)\b/i },
    { id:'design', icon:'🎨', name:'Designs', terms:/\b(design|logo|image|photo|wallpaper|theme|label|poster|ui|ux|color|pdf|visual|generate image)\b/i },
    { id:'websites', icon:'🌐', name:'Websites', terms:/\b(website|landing page|web page|portfolio|hotel|hospital|site|navbar|hero|responsive)\b/i },
    { id:'study', icon:'📚', name:'Study', terms:/\b(study|exam|revision|assignment|lecture|mcq|mock|answers|queue|stack|tree|sliit|university)\b/i },
    { id:'files', icon:'🧾', name:'Files', terms:/\b(file|upload|pdf|doc|document|spreadsheet|attachment|analyze|extract|zip)\b/i },
    { id:'business', icon:'💼', name:'Business', terms:/\b(business|money|earn|pricing|customer|market|plan|brand|product|sell|subscription)\b/i },
    { id:'personal', icon:'❤️', name:'Personal', terms:/\b(girlfriend|whatsapp|cute|personal|photo of|memory|remember)\b/i },
    { id:'general', icon:'💬', name:'General', terms:/.*/i },
  ];

  function brainCategoryForConversation(conv){
    const text = [
      conv.title || '',
      ...(conv.messages || []).slice(0, 8).map(brainMsgText),
      ...(conv.messages || []).slice(-5).map(brainMsgText),
    ].join(' ');
    const found = BRAIN_CATEGORIES.find(c => c.id !== 'general' && c.terms.test(text));
    return found || BRAIN_CATEGORIES[BRAIN_CATEGORIES.length - 1];
  }

  function brainConversationSummary(conv){
    const msgs = conv.messages || [];
    const userMsgs = msgs.filter(m => m.role === 'user').map(brainMsgText).filter(Boolean);
    const assistantMsgs = msgs.filter(m => m.role === 'assistant').map(brainMsgText).filter(Boolean);
    const lastUser = userMsgs[userMsgs.length - 1] || '';
    const lastAssistant = assistantMsgs[assistantMsgs.length - 1] || '';
    const fileCount = msgs.reduce((sum, m) => sum + ((m.attachments || []).length || 0), 0);
    const imageCount = msgs.reduce((sum, m) => sum + (m.imageSrc ? 1 : 0), 0);
    const category = brainCategoryForConversation(conv);
    const meta = loadBrainMeta();
    return {
      id: conv.id,
      title: conv.title || titleFromMessages(msgs),
      category,
      updatedAt: conv.updatedAt || conv.createdAt || Date.now(),
      createdAt: conv.createdAt || conv.updatedAt || Date.now(),
      messageCount: msgs.length,
      fileCount,
      imageCount,
      lastUser,
      lastAssistant,
      done: !!meta.done?.[conv.id],
      pinned: !!meta.pinned?.[conv.id],
      description: brainPlainText(lastUser || lastAssistant || 'No summary yet.', 180),
    };
  }

  function brainTimeAgo(ts){
    if (!ts) return 'unknown';
    const diff = Date.now() - Number(ts);
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(ts).toLocaleDateString();
  }

  function brainTaskPriority(text){
    const t = (text || '').toLowerCase();
    if (/\b(error|not working|can't|cannot|failed|rejecting|bug|broken|truncat|limit|issue)\b/.test(t)) return 'High';
    if (/\b(implement|fix|update|remove|add|create|make|build)\b/.test(t)) return 'Medium';
    return 'Low';
  }

  function brainExtractTasks(convs){
    const meta = loadBrainMeta();
    const taskTerms = /\b(fix|implement|add|remove|update|create|make|build|need|want|can't|cannot|not working|error|bug|issue|improve|change|move|replace|design)\b/i;
    const tasks = [];

    convs.forEach(conv => {
      if (meta.done?.[conv.id]) return;
      const msgs = conv.messages || [];
      const users = msgs.map((m, i) => ({ m, i })).filter(x => x.m.role === 'user');
      const category = brainCategoryForConversation(conv);
      const lastRelevant = [...users].reverse().find(x => taskTerms.test(brainMsgText(x.m)));
      if (!lastRelevant) return;
      const txt = brainPlainText(brainMsgText(lastRelevant.m), 170);
      if (!txt || txt.length < 4) return;
      tasks.push({
        id: `${conv.id}-${lastRelevant.i}`,
        convId: conv.id,
        title: txt,
        convTitle: conv.title || titleFromMessages(msgs),
        category,
        priority: brainTaskPriority(txt),
        updatedAt: conv.updatedAt || conv.createdAt || Date.now(),
      });
    });

    return tasks.sort((a,b) => {
      const pr = {High:3, Medium:2, Low:1};
      if (pr[a.priority] !== pr[b.priority]) return pr[b.priority] - pr[a.priority];
      return b.updatedAt - a.updatedAt;
    });
  }

  function brainExtractFiles(convs){
    const files = [];
    convs.forEach(conv => {
      const category = brainCategoryForConversation(conv);
      (conv.messages || []).forEach((m, idx) => {
        (m.attachments || []).forEach(a => {
          files.push({
            id: `${conv.id}-${idx}-${a.name}`,
            convId: conv.id,
            convTitle: conv.title || titleFromMessages(conv.messages || []),
            name: a.name || 'file',
            kind: a.kind || 'document',
            category,
            updatedAt: conv.updatedAt || conv.createdAt || Date.now(),
          });
        });
        if (m.imageSrc) {
          files.push({
            id: `${conv.id}-${idx}-generated-image`,
            convId: conv.id,
            convTitle: conv.title || titleFromMessages(conv.messages || []),
            name: brainPlainText(m.displayText || m.content || 'Generated image', 60),
            kind: 'image',
            category,
            updatedAt: conv.updatedAt || conv.createdAt || Date.now(),
          });
        }
      });
    });
    return files.sort((a,b) => b.updatedAt - a.updatedAt);
  }

  function brainBuildData(){
    const convs = brainAllConversations();
    const summaries = convs.map(brainConversationSummary);
    const tasks = brainExtractTasks(convs);
    const files = brainExtractFiles(convs);
    const categories = BRAIN_CATEGORIES.map(cat => {
      const count = summaries.filter(s => s.category.id === cat.id).length;
      return { ...cat, count };
    }).filter(c => c.count || c.id !== 'general');
    return { convs, summaries, tasks, files, categories };
  }

  function brainMatchesSearch(item, query){
    if (!query) return true;
    const q = query.toLowerCase();
    const blob = [
      item.title, item.convTitle, item.description, item.name, item.priority,
      item.category?.name, item.category?.id
    ].filter(Boolean).join(' ').toLowerCase();
    return blob.includes(q);
  }

  function brainCard(summary){
    const icon = summary.category.icon;
    return `
      <div class="brain-card" data-brain-card="${escapeHtml(summary.id)}">
        <div class="brain-card-icon">${icon}</div>
        <div class="brain-card-main">
          <div class="brain-card-title">${summary.pinned ? '📌 ' : ''}${escapeHtml(summary.title)}</div>
          <div class="brain-card-meta">
            <span class="brain-pill">${escapeHtml(summary.category.name)}</span>
            <span class="brain-pill">${summary.messageCount} msgs</span>
            ${summary.fileCount ? `<span class="brain-pill">${summary.fileCount} files</span>` : ''}
            ${summary.imageCount ? `<span class="brain-pill">${summary.imageCount} images</span>` : ''}
            <span class="brain-pill">${brainTimeAgo(summary.updatedAt)}</span>
            ${summary.done ? '<span class="brain-pill">Done</span>' : ''}
          </div>
          <div class="brain-card-desc">${escapeHtml(summary.description)}</div>
          <div class="brain-actions">
            <button class="brain-mini-btn primary" data-brain-open="${escapeHtml(summary.id)}" type="button">Open</button>
            <button class="brain-mini-btn" data-brain-continue="${escapeHtml(summary.id)}" type="button">Continue</button>
            <button class="brain-mini-btn ${summary.pinned ? 'done' : ''}" data-brain-pin="${escapeHtml(summary.id)}" type="button">${summary.pinned ? 'Pinned' : 'Pin'}</button>
            <button class="brain-mini-btn ${summary.done ? 'done' : ''}" data-brain-done="${escapeHtml(summary.id)}" type="button">${summary.done ? 'Done ✓' : 'Mark done'}</button>
          </div>
        </div>
      </div>`;
  }

  function brainTaskCard(task){
    return `
      <div class="brain-card">
        <div class="brain-card-icon">${task.priority === 'High' ? '🔥' : task.category.icon}</div>
        <div class="brain-card-main">
          <div class="brain-card-title">${escapeHtml(task.title)}</div>
          <div class="brain-card-meta">
            <span class="brain-pill">${escapeHtml(task.priority)} priority</span>
            <span class="brain-pill">${escapeHtml(task.category.name)}</span>
            <span class="brain-pill">${brainTimeAgo(task.updatedAt)}</span>
          </div>
          <div class="brain-card-desc">From: ${escapeHtml(task.convTitle)}</div>
          <div class="brain-actions">
            <button class="brain-mini-btn primary" data-brain-continue="${escapeHtml(task.convId)}" data-brain-focus="${escapeHtml(task.title)}" type="button">Continue task</button>
            <button class="brain-mini-btn" data-brain-open="${escapeHtml(task.convId)}" type="button">Open chat</button>
            <button class="brain-mini-btn" data-brain-done="${escapeHtml(task.convId)}" type="button">Mark done</button>
          </div>
        </div>
      </div>`;
  }

  function brainFileCard(file){
    return `
      <div class="brain-card">
        <div class="brain-card-icon">${file.kind === 'image' ? '🖼️' : '📄'}</div>
        <div class="brain-card-main">
          <div class="brain-card-title">${escapeHtml(file.name)}</div>
          <div class="brain-card-meta">
            <span class="brain-pill">${escapeHtml(file.kind)}</span>
            <span class="brain-pill">${escapeHtml(file.category.name)}</span>
            <span class="brain-pill">${brainTimeAgo(file.updatedAt)}</span>
          </div>
          <div class="brain-card-desc">Linked chat: ${escapeHtml(file.convTitle)}</div>
          <div class="brain-actions">
            <button class="brain-mini-btn primary" data-brain-open="${escapeHtml(file.convId)}" type="button">Open source chat</button>
          </div>
        </div>
      </div>`;
  }

  function brainEmpty(text){
    return `<div class="brain-empty">${escapeHtml(text)}</div>`;
  }

  function renderBrain(){
    if (!brainModalBody) return;
    const q = (brainSearchInput?.value || '').trim();
    const data = brainBuildData();
    const summaries = data.summaries.filter(s => brainMatchesSearch(s, q));
    const tasks = data.tasks.filter(t => brainMatchesSearch(t, q));
    const files = data.files.filter(f => brainMatchesSearch(f, q));

    brainTabs?.querySelectorAll('.brain-tab').forEach(btn => btn.classList.toggle('active', btn.dataset.brainTab === brainActiveTab));

    const activeTasks = data.tasks.length;
    const pinned = data.summaries.filter(s => s.pinned).length;
    const done = data.summaries.filter(s => s.done).length;
    const recentFocus = tasks[0] || data.tasks[0];

    if (brainActiveTab === 'overview') {
      const maxCat = Math.max(1, ...data.categories.map(c => c.count));
      const categoryHtml = data.categories.map(c => `
        <div class="brain-category-card" data-brain-category="${escapeHtml(c.id)}">
          <div class="brain-category-top">
            <div class="brain-category-name"><span>${c.icon}</span>${escapeHtml(c.name)}</div>
            <div class="brain-category-count">${c.count}</div>
          </div>
          <div class="brain-progress"><span style="width:${Math.max(8, Math.round((c.count / maxCat) * 100))}%"></span></div>
        </div>
      `).join('');

      brainModalBody.innerHTML = `
        <div class="brain-stat-grid">
          <div class="brain-stat-card"><div class="brain-stat-label">Chats mapped</div><div class="brain-stat-value">${data.summaries.length}</div></div>
          <div class="brain-stat-card"><div class="brain-stat-label">Open tasks</div><div class="brain-stat-value">${activeTasks}</div></div>
          <div class="brain-stat-card"><div class="brain-stat-label">Files/images</div><div class="brain-stat-value">${data.files.length}</div></div>
          <div class="brain-stat-card"><div class="brain-stat-label">Pinned / Done</div><div class="brain-stat-value">${pinned}/${done}</div></div>
        </div>
        ${recentFocus ? `
          <div class="brain-focus-banner">
            <div>
              <strong>Today’s focus: ${escapeHtml(recentFocus.title || recentFocus.convTitle)}</strong>
              <span>Vigzone can continue this from where you stopped.</span>
            </div>
            <button class="brain-mini-btn primary" data-brain-continue="${escapeHtml(recentFocus.convId || recentFocus.id)}" data-brain-focus="${escapeHtml(recentFocus.title || '')}" type="button">Continue</button>
          </div>
        ` : ''}
        <div class="brain-grid">
          <div class="brain-panel">
            <div class="brain-panel-title">Memory cards <span class="brain-panel-sub">Click a category to filter</span></div>
            <div class="brain-category-grid">${categoryHtml || brainEmpty('No categories yet. Start chatting and Vigzone Brain will organize your work.')}</div>
          </div>
          <div class="brain-panel">
            <div class="brain-panel-title">Unfinished tasks <span class="brain-panel-sub">${tasks.length} found</span></div>
            <div class="brain-card-list">${tasks.slice(0,5).map(brainTaskCard).join('') || brainEmpty('No obvious unfinished tasks found yet.')}</div>
          </div>
        </div>
        <div class="brain-panel" style="margin-top:12px;">
          <div class="brain-panel-title">Recent project timeline <span class="brain-panel-sub">Latest activity</span></div>
          <div class="brain-card-list">${summaries.slice(0,5).map(brainCard).join('') || brainEmpty('No chats found.')}</div>
        </div>
      `;
      return;
    }

    if (brainActiveTab === 'tasks') {
      brainModalBody.innerHTML = `
        <div class="brain-panel">
          <div class="brain-panel-title">Unfinished task tracker <span class="brain-panel-sub">Auto-detected from your chats</span></div>
          <div class="brain-card-list">${tasks.map(brainTaskCard).join('') || brainEmpty('No unfinished tasks match your search. When you say “fix”, “implement”, “add”, or “not working”, tasks appear here.')}</div>
        </div>`;
      return;
    }

    if (brainActiveTab === 'timeline') {
      brainModalBody.innerHTML = `
        <div class="brain-panel">
          <div class="brain-panel-title">Project timeline <span class="brain-panel-sub">${summaries.length} chats</span></div>
          <div class="brain-timeline">
            ${summaries.map(s => `
              <div class="brain-timeline-item">
                <div class="brain-time">${brainTimeAgo(s.updatedAt)}</div>
                ${brainCard(s)}
              </div>
            `).join('') || brainEmpty('No timeline yet.')}
          </div>
        </div>`;
      return;
    }

    if (brainActiveTab === 'files') {
      brainModalBody.innerHTML = `
        <div class="brain-panel">
          <div class="brain-panel-title">Recent files and generated images <span class="brain-panel-sub">${files.length} items</span></div>
          <div class="brain-card-list">${files.map(brainFileCard).join('') || brainEmpty('No uploaded files or generated images found yet.')}</div>
        </div>`;
    }
  }

  function openBrainModal(){
    renderBrain();
    brainModalOverlay?.classList.add('visible');
  }

  function closeBrainModal(){
    brainModalOverlay?.classList.remove('visible');
  }

  function refreshBrainIfOpen(){
    if (brainModalOverlay?.classList.contains('visible')) renderBrain();
  }

  function brainSwitchToConversation(id){
    if (!store.conversations[id]) return;
    switchConversation(id);
    closeBrainModal();
  }

  function brainContinueConversation(id, focusText=''){
    if (!store.conversations[id]) return;
    switchConversation(id);
    closeBrainModal();
    const conv = store.conversations[id];
    const summary = brainConversationSummary(conv);
    const focus = focusText || summary.description || summary.title;
    input.value = `Continue this ${summary.category.name.toLowerCase()} from where we stopped. Focus on: ${focus}`;
    autoResize();
    input.focus();
  }

  function brainToggleMeta(kind, id){
    const meta = loadBrainMeta();
    if (!meta[kind]) meta[kind] = {};
    if (meta[kind][id]) delete meta[kind][id];
    else meta[kind][id] = Date.now();
    saveBrainMeta(meta);
    renderBrain();
  }

  function brainExport(){
    const data = brainBuildData();
    const exportData = {
      exportedAt: new Date().toISOString(),
      user: userName || '',
      stats: {
        conversations: data.summaries.length,
        tasks: data.tasks.length,
        files: data.files.length,
        categories: data.categories.map(c => ({ id:c.id, name:c.name, count:c.count })),
      },
      tasks: data.tasks.map(t => ({ title:t.title, chat:t.convTitle, category:t.category.name, priority:t.priority, updatedAt:new Date(t.updatedAt).toISOString() })),
      timeline: data.summaries.map(s => ({ title:s.title, category:s.category.name, done:s.done, pinned:s.pinned, updatedAt:new Date(s.updatedAt).toISOString(), description:s.description })),
      files: data.files.map(f => ({ name:f.name, kind:f.kind, chat:f.convTitle, category:f.category.name })),
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type:'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vigzone-brain-${new Date().toISOString().slice(0,10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  vigzoneBrainBtn?.addEventListener('click', openBrainModal);
  brainModalCloseBtn?.addEventListener('click', closeBrainModal);
  brainModalOverlay?.addEventListener('click', e => { if (e.target === brainModalOverlay) closeBrainModal(); });
  brainRefreshBtn?.addEventListener('click', renderBrain);
  brainExportBtn?.addEventListener('click', brainExport);
  brainSearchInput?.addEventListener('input', renderBrain);
  brainTabs?.addEventListener('click', e => {
    const btn = e.target.closest('[data-brain-tab]');
    if (!btn) return;
    brainActiveTab = btn.dataset.brainTab || 'overview';
    renderBrain();
  });

  brainModalBody?.addEventListener('click', e => {
    const openBtn = e.target.closest('[data-brain-open]');
    if (openBtn) { brainSwitchToConversation(openBtn.dataset.brainOpen); return; }

    const continueBtn = e.target.closest('[data-brain-continue]');
    if (continueBtn) { brainContinueConversation(continueBtn.dataset.brainContinue, continueBtn.dataset.brainFocus || ''); return; }

    const doneBtn = e.target.closest('[data-brain-done]');
    if (doneBtn) { brainToggleMeta('done', doneBtn.dataset.brainDone); return; }

    const pinBtn = e.target.closest('[data-brain-pin]');
    if (pinBtn) { brainToggleMeta('pinned', pinBtn.dataset.brainPin); return; }

    const cat = e.target.closest('[data-brain-category]');
    if (cat && brainSearchInput) {
      const category = BRAIN_CATEGORIES.find(c => c.id === cat.dataset.brainCategory);
      brainSearchInput.value = category ? category.name : cat.dataset.brainCategory;
      brainActiveTab = 'timeline';
      renderBrain();
    }
  });


  // ---------- Sidebar open/collapse (in-flow on desktop, overlay drawer on mobile) ----------
  function isMobile(){ return window.innerWidth <= 760; }

  function setSidebarCollapsed(collapsed){
    const expanded = !collapsed;
    sidebar.classList.toggle('collapsed', collapsed);
    sidebarOverlay.classList.toggle('visible', isMobile() && expanded);
    document.body.classList.toggle('sidebar-expanded', expanded);
    document.querySelector('.main-col > header .brand')
      ?.setAttribute('aria-hidden', expanded ? 'true' : 'false');
    sidebarToggleBtn?.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    if (expanded) closeQuickLauncher?.();
    if (!isMobile()) localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0');
  }

  sidebarToggleBtn.addEventListener('click', () => setSidebarCollapsed(!sidebar.classList.contains('collapsed')));
  sidebarOverlay.addEventListener('click', () => setSidebarCollapsed(true));

  // ---------- Learning Center / private memories ----------
  let learningState = { enabled: true, memories: [] };

  async function learningFetch(url, options = {}){
    const res = await fetch(url, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.error || 'Learning request failed.');
    return data;
  }

  function renderLearningCenter(){
    if (!learningModalBody) return;
    const status = learningState.status || { enabled: true, active_count: 0, count: 0 };
    const memories = learningState.memories || [];
    const enabled = !!status.enabled;
    const activeCount = status.active_count ?? memories.filter(m => m.is_active).length;
    const totalCount = status.count ?? memories.length;
    const listHtml = memories.map(m => `
      <div class="learning-card ${m.is_active ? '' : 'paused'}" data-memory-id="${m.id}">
        <div class="learning-card-text">${escapeHtml(m.memory_text || '')}</div>
        <div class="learning-card-meta">
          <span class="learning-badge">${m.is_active ? 'Active memory' : 'Paused'}</span>
          <div class="learning-card-actions">
            <button data-learning-edit="${m.id}">Edit</button>
            <button data-learning-toggle="${m.id}" data-learning-active="${m.is_active ? '1' : '0'}">${m.is_active ? 'Pause' : 'Activate'}</button>
            <button class="danger" data-learning-delete="${m.id}">Delete</button>
          </div>
        </div>
      </div>
    `).join('');

    learningModalBody.innerHTML = `
      <div class="usage-modal-note">
        Vigzone can remember useful instructions you approve. These memories are private to your account and are used only when Learning is ON.
      </div>
      <div class="learning-row">
        <div>
          <div style="font-size:13px;color:var(--text);font-weight:700;">Use memories in chat</div>
          <div style="font-size:11px;color:var(--text-muted);">${activeCount.toLocaleString()} active · ${totalCount.toLocaleString()} total</div>
        </div>
        <button class="learning-switch ${enabled ? 'on' : ''}" id="learningToggleSwitch" aria-label="Toggle Learning"></button>
      </div>
      <div class="learning-add-box">
        <textarea id="learningMemoryInput" maxlength="1200" placeholder="Example: When I ask for code changes, give me the full updated zip file.\nExample: My project is Groq-only production mode."></textarea>
        <div class="learning-actions">
          <span class="learning-count" id="learningCharCount">0 / 1200</span>
          <button class="learning-save-btn" id="learningSaveBtn">Add memory</button>
        </div>
        <div class="learning-status" id="learningStatusText"></div>
      </div>
      <div class="learning-list">
        ${listHtml || '<div class="usage-modal-empty">No memories yet. Add one above.</div>'}
      </div>
    `;

    const textarea = $('#learningMemoryInput');
    const charCount = $('#learningCharCount');
    const statusText = $('#learningStatusText');
    const saveBtn = $('#learningSaveBtn');
    const toggleSwitch = $('#learningToggleSwitch');

    if (textarea && charCount) {
      textarea.addEventListener('input', () => {
        charCount.textContent = `${textarea.value.length} / 1200`;
      });
    }

    if (saveBtn && textarea) {
      saveBtn.addEventListener('click', async () => {
        const value = textarea.value.trim();
        if (value.length < 3) {
          if (statusText) { statusText.textContent = 'Write a useful memory first.'; statusText.className = 'learning-status err'; }
          return;
        }
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving…';
        try {
          await learningFetch('/api/learning/memories', {
            method: 'POST',
            body: JSON.stringify({ memory_text: value }),
          });
          textarea.value = '';
          await loadLearningCenter(false);
        } catch (e) {
          if (statusText) { statusText.textContent = e.message || 'Could not save memory.'; statusText.className = 'learning-status err'; }
          saveBtn.disabled = false;
          saveBtn.textContent = 'Add memory';
        }
      });
    }

    if (toggleSwitch) {
      toggleSwitch.addEventListener('click', async () => {
        toggleSwitch.disabled = true;
        try {
          const next = !enabled;
          const status = await learningFetch('/api/learning/toggle', {
            method: 'POST',
            body: JSON.stringify({ enabled: next }),
          });
          learningState.status = status;
          renderLearningCenter();
        } catch (e) {
          toggleSwitch.disabled = false;
        }
      });
    }

    learningModalBody.querySelectorAll('[data-learning-edit]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = Number(btn.getAttribute('data-learning-edit'));
        const current = memories.find(m => m.id === id);
        const updated = prompt('Edit this memory:', current ? current.memory_text : '');
        if (updated === null) return;
        const memory_text = updated.trim();
        if (memory_text.length < 3) return;
        try {
          await learningFetch(`/api/learning/memories/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ memory_text }),
          });
          await loadLearningCenter(false);
        } catch (e) { alert(e.message || 'Could not edit memory.'); }
      });
    });

    learningModalBody.querySelectorAll('[data-learning-toggle]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = Number(btn.getAttribute('data-learning-toggle'));
        const isActive = btn.getAttribute('data-learning-active') === '1';
        try {
          await learningFetch(`/api/learning/memories/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_active: !isActive }),
          });
          await loadLearningCenter(false);
        } catch (e) { alert(e.message || 'Could not update memory.'); }
      });
    });

    learningModalBody.querySelectorAll('[data-learning-delete]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = Number(btn.getAttribute('data-learning-delete'));
        if (!confirm('Delete this memory permanently?')) return;
        try {
          await learningFetch(`/api/learning/memories/${id}`, { method: 'DELETE' });
          await loadLearningCenter(false);
        } catch (e) { alert(e.message || 'Could not delete memory.'); }
      });
    });
  }

  async function loadLearningCenter(showLoading = true){
    if (showLoading && learningModalBody) learningModalBody.innerHTML = '<div class="usage-modal-loading">Loading memories…</div>';
    try {
      const data = await learningFetch('/api/learning/memories');
      learningState = data;
      renderLearningCenter();
    } catch (e) {
      if (learningModalBody) learningModalBody.innerHTML = `<div class="usage-modal-empty">${escapeHtml(e.message || 'Could not load Learning Center.')}</div>`;
    }
  }


  // Clear any stale invisible overlays that could block composer/sidebar taps.
  document.querySelectorAll('.floating-menu-backdrop.visible').forEach(el => el.classList.remove('visible'));

  // ---------- Deep Features v3: smart modes, workspaces, file intel, export ----------
  const MODE_LABELS = {general:'General', website:'Website Studio', code:'Code Fixer', study:'Study Helper', file:'File Analyzer', business:'Business Writer', voice:'Voice'};
  const MODE_BADGES = {general:'G', website:'W', code:'C', study:'S', file:'F', business:'B', voice:'V'};
  function currentMode(){ return activeAiMode || 'general'; }
  function setSmartMode(mode){
    activeAiMode = MODE_LABELS[mode] ? mode : 'general';
    localStorage.setItem('vigzone_ai_mode', activeAiMode);
    if (aiModeSelect) aiModeSelect.value = activeAiMode;
    if (modeMenuCurrent) modeMenuCurrent.textContent = MODE_BADGES[activeAiMode] || 'G';
    if (modeMenuBtn) modeMenuBtn.title = `Tools • Smart mode: ${MODE_LABELS[activeAiMode] || 'General'}`;
    modeMenu?.querySelectorAll('[data-mode]').forEach(btn => btn.classList.toggle('active', btn.dataset.mode === activeAiMode));
  }
  if (aiModeSelect) {
    aiModeSelect.value = activeAiMode;
    aiModeSelect.addEventListener('change', () => setSmartMode(aiModeSelect.value || 'general'));
  }
  setSmartMode(activeAiMode);

  function closePlusMenu(){
    if (!modeMenu) return;
    modeMenu.classList.remove('visible');
    modeMenu.style.display = 'none';
    modeMenu.querySelectorAll('.plus-submenu.visible').forEach(el => el.classList.remove('visible'));
    modeMenu.querySelectorAll('[data-plus-section][aria-expanded="true"]').forEach(btn => btn.setAttribute('aria-expanded', 'false'));
  }

  function openPlusMenu(){
    if (!modeMenu) return;
    modeMenu.classList.add('visible');
    modeMenu.style.display = 'block';
    modeMenu.style.pointerEvents = 'auto';
  }

  function togglePlusMenu(e){
    e?.preventDefault?.();
    e?.stopPropagation?.();
    if (!modeMenu) return;
    if (modeMenu.classList.contains('visible') || modeMenu.style.display === 'block') {
      closePlusMenu();
    } else {
      openPlusMenu();
    }
  }

  // The + button is handled by the delegated pointerdown listener below.
  // Do not attach another direct listener here, otherwise it toggles twice.

  // Single reliable handler for the composer + button.
  // Pointerdown opens immediately on mobile/desktop and prevents the old click
  // event from firing a second toggle.
  document.addEventListener('pointerdown', (e) => {
    const btn = e.target.closest?.('#modeMenuBtn');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    e.__vigzonePlusHandled = true;
    if (!modeMenu) return;
    if (modeMenu.classList.contains('visible') || modeMenu.style.display === 'block') closePlusMenu();
    else openPlusMenu();
  }, true);

  modeMenuCloseBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    closePlusMenu();
  });
  plusMenuCloseBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    closePlusMenu();
  });

  modeMenu?.querySelectorAll('[data-plus-section]').forEach(btn => btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const targetId = btn.dataset.plusSection === 'moreUploads' ? 'moreUploadsMenu' : 'moreToolsMenu';
    const target = document.getElementById(targetId);
    const willShow = !target?.classList.contains('visible');
    modeMenu.querySelectorAll('.plus-submenu.visible').forEach(el => {
      if (el !== target) el.classList.remove('visible');
    });
    modeMenu.querySelectorAll('[data-plus-section]').forEach(other => {
      if (other !== btn) other.setAttribute('aria-expanded', 'false');
    });
    target?.classList.toggle('visible', willShow);
    btn.setAttribute('aria-expanded', willShow ? 'true' : 'false');
  }));

  modeMenu?.querySelectorAll('[data-mode]').forEach(btn => btn.addEventListener('click', () => {
    if (btn.classList.contains('disabled-row') || btn.classList.contains('disabled')) return;
    setSmartMode(btn.dataset.mode);
    closePlusMenu();
    input?.focus();
  }));

  modeMenu?.querySelectorAll('.disabled-row,.disabled').forEach(btn => btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
  }));

  document.addEventListener('click', e => {
    if ((modeMenu?.classList.contains('visible') || modeMenu?.style.display === 'block') && modeMenuWrap && !modeMenuWrap.contains(e.target)) closePlusMenu();
  });

  function workspaceName(id){
    const ws = workspaces.find(w => Number(w.id) === Number(id));
    return ws ? ws.name : '';
  }
  function updateWorkspacePill(){
    if (!workspacePill) return;
    const name = activeWorkspaceId ? workspaceName(activeWorkspaceId) : '';
    workspacePill.textContent = name ? `📁 ${name}` : 'No workspace';
    workspacePill.classList.toggle('active', !!name);
  }
  async function loadWorkspaces(){
    try {
      const res = await fetch('/api/workspaces', {headers: authHeaders()});
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to load workspaces');
      workspaces = data.workspaces || [];
      if (activeWorkspaceId && !workspaces.some(w => Number(w.id) === Number(activeWorkspaceId))) {
        activeWorkspaceId = null; localStorage.removeItem('vigzone_active_workspace_id');
      }
      updateWorkspacePill();
      return workspaces;
    } catch (e) { console.warn(e); return []; }
  }
  function renderWorkspaceModal(){
    if (!workspaceModalBody) return;
    const cards = workspaces.length ? workspaces.map(w => `
      <div class="workspace-card${Number(w.id)===Number(activeWorkspaceId)?' active':''}" data-ws-id="${w.id}">
        <div class="workspace-card-title">${escapeHtml(w.name)}</div>
        <div class="workspace-card-sub">${escapeHtml(w.mode || 'general')}${w.description ? ' • '+escapeHtml(w.description) : ''}</div>
      </div>
    `).join('') : '<div class="usage-modal-loading">No workspaces yet. Create one below.</div>';
    workspaceModalBody.innerHTML = `
      <div class="workspace-list">${cards}</div>
      <button class="deep-action-btn" id="clearWorkspaceBtn" type="button">Use no workspace</button>
      <div class="workspace-form">
        <input id="workspaceNameInput" placeholder="Workspace name, e.g. Hotel Website Project" />
        <textarea id="workspaceDescInput" placeholder="Short project description / goal"></textarea>
        <select id="workspaceModeInput">
          <option value="general">General</option><option value="website">Website Studio</option><option value="code">Code Fixer</option><option value="study">Study Helper</option><option value="file">File Analyzer</option><option value="business">Business Writer</option>
        </select>
        <button class="deep-action-btn" id="createWorkspaceBtn" type="button">+ Create workspace</button>
      </div>`;
    workspaceModalBody.querySelectorAll('[data-ws-id]').forEach(el => el.addEventListener('click', () => {
      activeWorkspaceId = Number(el.dataset.wsId); localStorage.setItem('vigzone_active_workspace_id', String(activeWorkspaceId));
      updateWorkspacePill(); renderWorkspaceModal();
    }));
    $('#clearWorkspaceBtn')?.addEventListener('click', () => { activeWorkspaceId=null; localStorage.removeItem('vigzone_active_workspace_id'); updateWorkspacePill(); renderWorkspaceModal(); });
    $('#createWorkspaceBtn')?.addEventListener('click', async () => {
      const name = $('#workspaceNameInput').value.trim();
      const description = $('#workspaceDescInput').value.trim();
      const mode = $('#workspaceModeInput').value;
      if (!name) return alert('Enter a workspace name first.');
      const res = await fetch('/api/workspaces', {method:'POST', headers:{'Content-Type':'application/json', ...authHeaders()}, body:JSON.stringify({name, description, mode})});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) return alert(data.detail || 'Could not create workspace');
      activeWorkspaceId = data.workspace.id; localStorage.setItem('vigzone_active_workspace_id', String(activeWorkspaceId));
      await loadWorkspaces(); renderWorkspaceModal();
    });
  }
  async function openWorkspaceModal(){ workspaceModalOverlay?.classList.add('visible'); await loadWorkspaces(); renderWorkspaceModal(); }
  function closeWorkspaceModal(){ workspaceModalOverlay?.classList.remove('visible'); }
  workspaceSidebarBtn?.addEventListener('click', openWorkspaceModal);
  workspacePill?.addEventListener('click', openWorkspaceModal);
  workspaceModalCloseBtn?.addEventListener('click', closeWorkspaceModal);
  workspaceModalOverlay?.addEventListener('click', e => { if(e.target===workspaceModalOverlay) closeWorkspaceModal(); });

  function downloadBlobText(filename, content, type='text/plain'){
    const blob = new Blob([content], {type});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 0);
  }
  function exportMessageText(m){
    if (!m) return '';
    if (m.displayText !== undefined && m.displayText !== null) return String(m.displayText);
    if (typeof m.content === 'string') return m.content;
    if (m.text !== undefined && m.text !== null) return String(m.text);
    try { return JSON.stringify(m.content || m, null, 2); } catch { return ''; }
  }
  function htmlEscapeInline(value){
    return String(value || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function closeExportMenu(){
    hideFloatingMenu(exportMenu);
    syncFloatingMenuBackdrop();
  }

  async function exportChat(format){
    const exportable = (messages || []).filter(m => m && (m.role === 'user' || m.role === 'assistant'));
    if (!exportable.length) {
      alert('No chat messages to export yet.');
      closeExportMenu();
      return;
    }
    const conv = currentConversation();
    const title = conv?.title || (liveConfig.app_name || 'Vigzone') + ' chat';
    const safeTitle = title.replace(/[^a-z0-9-_]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase() || 'vigzone-chat';
    try {
      const res = await fetch('/api/export/chat', {
        method:'POST',
        headers:suiteAuthHeaders(true),
        body:JSON.stringify({title, messages:exportable, format})
      });
      if (!res.ok) throw new Error('Backend export failed');
      const data = await res.json();
      downloadBlobText(data.filename || `${safeTitle}.${format === 'html' ? 'html' : 'txt'}`, data.content || '', data.media_type || (format === 'html' ? 'text/html;charset=utf-8' : 'text/plain;charset=utf-8'));
    } catch {
      const now = new Date().toLocaleString();
      if (format === 'html') {
        const sections = exportable.map(m => `<section><h2>${htmlEscapeInline(m.role === 'user' ? 'You' : (liveConfig.app_name || 'Vigzone AI'))}</h2><pre>${htmlEscapeInline(exportMessageText(m))}</pre></section>`).join('\n');
        const html = `<!doctype html><html><head><meta charset="utf-8"><title>${htmlEscapeInline(title)}</title><style>body{font-family:Inter,Arial,sans-serif;max-width:820px;margin:32px auto;padding:0 18px;line-height:1.55;color:#121622}h1{font-size:26px}h2{font-size:15px;margin-top:22px;color:#ff6b4a}pre{white-space:pre-wrap;background:#f4f6fb;border:1px solid #dfe5f0;border-radius:12px;padding:14px}</style></head><body><h1>${htmlEscapeInline(title)}</h1><p>Exported from ${htmlEscapeInline(liveConfig.app_name || 'Vigzone AI')} • ${htmlEscapeInline(now)}</p>${sections}</body></html>`;
        downloadBlobText(`${safeTitle}.html`, html, 'text/html;charset=utf-8');
      } else {
        const txt = [title, `Exported from ${liveConfig.app_name || 'Vigzone AI'} • ${now}`, '', ...exportable.map(m => `[${m.role === 'user' ? 'YOU' : String(liveConfig.app_name || 'VIGZONE AI').toUpperCase()}]\n${exportMessageText(m)}\n`)].join('\n');
        downloadBlobText(`${safeTitle}.txt`, txt, 'text/plain;charset=utf-8');
      }
    }
    closeExportMenu();
  }
  exportChatBtn?.addEventListener('click', (e)=>{
    e.stopPropagation();
    const wasOpen = !!exportMenu?.classList.contains('visible');
    closeFloatingMenus('export');
    if (wasOpen) {
      closeExportMenu();
    } else {
      showFloatingMenu(exportMenu);
      syncFloatingMenuBackdrop();
      positionExportMenu();
    }
  });
  exportTxtBtn?.addEventListener('click', (e)=>{ e.stopPropagation(); exportChat('txt'); closeExportMenu(); });
  exportHtmlBtn?.addEventListener('click', (e)=>{ e.stopPropagation(); exportChat('html'); closeExportMenu(); });
  if (exportTxtBtn) exportTxtBtn.onclick = (e) => { e?.stopPropagation?.(); exportChat('txt'); closeExportMenu(); };
  if (exportHtmlBtn) exportHtmlBtn.onclick = (e) => { e?.stopPropagation?.(); exportChat('html'); closeExportMenu(); };

  exportMenuCloseBtn?.addEventListener('click', (e)=>{ e.stopPropagation(); closeExportMenu(); });

  async function analyzeReadyFiles(){
    const docs = pendingFiles.filter(f => f.status === 'ready' && f.text);
    if (!docs.length) return;
    const panel = document.createElement('div'); panel.className = 'file-intel-panel'; panel.innerHTML = '<div class="usage-modal-loading">Analyzing files…</div>';
    attachmentsBar.insertAdjacentElement('afterend', panel);
    const reports = [];
    for (const f of docs){
      const res = await fetch('/api/file-intel/analyze', {method:'POST', headers:{'Content-Type':'application/json', ...authHeaders()}, body:JSON.stringify({name:f.name, kind:f.kind, text:f.text || ''})});
      const data = await res.json().catch(()=>({})); if (res.ok) reports.push(data);
    }
    panel.innerHTML = reports.map(r => `
      <div class="file-intel-title">🧠 ${escapeHtml(r.name)}</div>
      <div>${escapeHtml(r.summary || '')}</div>
      <div class="file-intel-grid"><div class="file-intel-stat"><b>${r.word_count||0}</b>words</div><div class="file-intel-stat"><b>${r.line_count||0}</b>lines</div><div class="file-intel-stat"><b>${(r.risks||[]).length}</b>risks</div></div>
      <div><b>Keywords:</b> ${escapeHtml((r.keywords||[]).slice(0,10).join(', ') || '—')}</div>
      ${(r.risks||[]).length ? `<div style="margin-top:6px"><b>Warnings:</b> ${escapeHtml(r.risks.join(', '))}</div>` : ''}
    `).join('<hr style="border:none;border-top:1px solid var(--border-subtle);margin:10px 0">');
  }

  function openLearningModal(){
    learningModalOverlay?.classList.add('visible');
    loadLearningCenter(true);
  }
  function closeLearningModal(){ learningModalOverlay?.classList.remove('visible'); }
  if (teachVigzoneBtn) teachVigzoneBtn.addEventListener('click', openLearningModal);
  if (learningModalCloseBtn) learningModalCloseBtn.addEventListener('click', closeLearningModal);
  if (learningModalOverlay) learningModalOverlay.addEventListener('click', (e) => {
    if (e.target === learningModalOverlay) closeLearningModal();
  });

  // ---------- My usage today (Groq default plan or own key) ----------
  function formatDuration(totalSeconds){
    totalSeconds = Math.max(0, totalSeconds | 0);
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  let latestUsageData = null;
  let usageCyclePollTimer = null;
  let usageCycleRefreshTimer = null;

  async function fetchUsageTodayData(){
    const res = await fetch('/api/me/usage', { credentials: 'include' });
    if (!res.ok) throw new Error('request failed');
    return await res.json();
  }

  function usageStatsFromData(data){
    const limit = Number(data?.daily_limit || 0);
    const used = Number(data?.used_today || 0);
    const remaining = data?.remaining_today ?? Math.max(limit - used, 0);
    const pctRaw = limit > 0 ? (used / limit) * 100 : 0;
    const pct = Math.max(0, Math.min(100, pctRaw));
    const pctLabel = limit > 0 ? `${Math.round(pct)}%` : '—';
    const resetIn = data?.seconds_until_reset ? `Resets in ${formatDuration(data.seconds_until_reset)}` : '';
    return { limit, used, remaining, pct, pctLabel, resetIn };
  }

  function providerRateSummary(data){
    const rate = data?.provider_rate_limit || {};
    const requestRemaining = rate['x-ratelimit-remaining-requests'];
    const tokenRemaining = rate['x-ratelimit-remaining-tokens'];
    const requestReset = rate['x-ratelimit-reset-requests'];
    const tokenReset = rate['x-ratelimit-reset-tokens'];
    const parts = [];
    if (requestRemaining !== undefined) parts.push(`${requestRemaining} provider requests left${requestReset ? ` · reset ${requestReset}` : ''}`);
    if (tokenRemaining !== undefined) parts.push(`${tokenRemaining} provider tokens left${tokenReset ? ` · reset ${tokenReset}` : ''}`);
    return parts;
  }

  function renderUsageCyclePopover(data){
    if (!usageCyclePercent || !usageCycleNote) return;
    if (!data || data.mode === 'testing') {
      usageCyclePercent.textContent = '—';
      usageCycleNote.textContent = data?.mode === 'testing' ? 'Usage tracking is off in testing mode.' : 'Usage data not loaded yet.';
      return;
    }
    const st = usageStatsFromData(data);
    const ownKey = data.mode === 'own_key' || data.using_own_key;
    const planName = data.plan_label || (ownKey ? 'Vigzone app cap • Personal Groq key' : 'Vigzone app cap • Default Groq key');
    const estimated = Number(data.estimated_request_count_today || 0);
    const exact = Math.max(0, Number(data.request_count_today || 0) - estimated);
    const providerParts = providerRateSummary(data);
    usageCyclePercent.textContent = `${st.pctLabel} used`;
    usageCycleNote.innerHTML = `
      <strong>${escapeHtml(planName)}</strong>
      <div class="usage-cycle-pop-note">${exact.toLocaleString()} exact usage record${exact === 1 ? '' : 's'}${estimated ? ` · ${estimated.toLocaleString()} estimated` : ''}</div>
      <div class="usage-cycle-pop-meta"><span>${st.used.toLocaleString()} used</span><span>${st.limit ? st.limit.toLocaleString() : 'No'} limit</span></div>
      <div class="usage-cycle-pop-meta"><span>${Number(st.remaining || 0).toLocaleString()} left</span><span>${escapeHtml(st.resetIn || '')}</span></div>
      ${providerParts.length ? `<div class="usage-cycle-pop-note">${providerParts.map(escapeHtml).join('<br>')}</div>` : '<div class="usage-cycle-pop-note">Provider quota headers will appear after Groq returns them.</div>'}
    `;
    if (usageCyclePopover?.classList.contains('visible')) positionUsageCyclePopover();
  }

  function updateUsageCycle(data){
    latestUsageData = data || latestUsageData;
    if (!usageCycleBtn || !usageCycleFill || !usageCycleCenter) return;
    const current = data || latestUsageData;
    usageCycleBtn.classList.remove('warn', 'danger', 'limit-hit');

    if (!current || current.mode === 'testing') {
      usageCycleFill.style.strokeDashoffset = '100';
      usageCycleCenter.textContent = '—';
      usageCycleBtn.title = current?.mode === 'testing' ? 'Usage tracking off' : 'Usage today';
      renderUsageCyclePopover(current);
      return;
    }

    const st = usageStatsFromData(current);
    usageCycleFill.style.strokeDashoffset = String(100 - st.pct);
    usageCycleCenter.textContent = st.limit > 0 ? String(Math.round(st.pct)) : '∞';
    usageCycleBtn.setAttribute('aria-label', `Usage today: ${st.pctLabel} used`);
    usageCycleBtn.title = `Usage today: ${st.pctLabel} used`;
    if (st.pct >= 90) usageCycleBtn.classList.add('danger');
    else if (st.pct >= 65) usageCycleBtn.classList.add('warn');
    if (current.is_limited) usageCycleBtn.classList.add('limit-hit');
    renderUsageCyclePopover(current);
  }

  async function refreshUsageCycle(){
    if (!usageCycleBtn) return;
    try {
      const data = await fetchUsageTodayData();
      updateUsageCycle(data);
    } catch (e) {
      // Keep the last known ring instead of flashing an error in the header.
      renderUsageCyclePopover(latestUsageData);
    }
  }

  function startUsageCycleLiveUpdates(){
    if (!usageCycleBtn) return;
    usageCycleBtn.classList.add('loading');
    refreshUsageCycle();
    clearInterval(usageCyclePollTimer);
    usageCyclePollTimer = setInterval(refreshUsageCycle, 5000);
  }

  function stopUsageCycleLiveUpdates(){
    if (!usageCycleBtn) return;
    usageCycleBtn.classList.remove('loading');
    clearInterval(usageCyclePollTimer);
    usageCyclePollTimer = null;
    refreshUsageCycle();
  }

  function closeUsageCyclePopover(){
    hideFloatingMenu(usageCyclePopover);
    syncFloatingMenuBackdrop();
  }

  function closeFloatingMenus(except){
    if (except !== 'usage') closeUsageCyclePopover();
    if (except !== 'export') closeExportMenu();
  }

  function toggleUsageCyclePopover(e){
    e?.stopPropagation();
    if (!usageCyclePopover) return;
    const wasOpen = usageCyclePopover.classList.contains('visible');
    closeFloatingMenus('usage');
    if (wasOpen) {
      closeUsageCyclePopover();
    } else {
      showFloatingMenu(usageCyclePopover);
      syncFloatingMenuBackdrop();
      renderUsageCyclePopover(latestUsageData);
      positionUsageCyclePopover();
      refreshUsageCycle();
    }
  }

  if (usageCycleBtn) usageCycleBtn.addEventListener('click', toggleUsageCyclePopover);
  usageCycleCloseBtn?.addEventListener('click', (e)=>{ e.stopPropagation(); closeUsageCyclePopover(); });

  function isInsideFloatingMenuTarget(target){
    // Keep clicks/taps inside an open floating menu alive, so buttons such as
    // Export TXT / Export HTML can receive their normal click event. Outside
    // taps are still caught by handleOutsideFloatingMenuTap() and the backdrop.
    return !!(
      (usageCycleBtn && usageCycleBtn.contains(target)) ||
      (usageCyclePopover && usageCyclePopover.contains(target)) ||
      (exportChatBtn && exportChatBtn.contains(target)) ||
      (exportMenu && exportMenu.contains(target))
    );
  }

  function handleOutsideFloatingMenuTap(e){
    if (!usageCyclePopover?.classList.contains('visible') && !exportMenu?.classList.contains('visible')) return;
    if (isInsideFloatingMenuTarget(e.target)) return;
    closeFloatingMenus();
  }

  // Close floating menus when tapping/clicking anywhere outside.
  // Multiple event names are intentional: this makes it reliable on desktop,
  // mobile touch screens, and elements that stop normal click bubbling.
  ['pointerdown', 'mousedown', 'touchstart', 'click'].forEach((eventName) => {
    document.addEventListener(eventName, handleOutsideFloatingMenuTap, true);
    window.addEventListener(eventName, handleOutsideFloatingMenuTap, true);
  });

  // Strong fallback: when a menu is open, this invisible full-screen layer
  // sits behind the menu and catches any outside tap/click.
  ['pointerdown', 'mousedown', 'touchstart', 'click'].forEach((eventName) => {
    floatingMenuBackdrop.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeFloatingMenus();
    }, true);
  });

  // Keyboard accessibility: Escape closes all floating menus too.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeFloatingMenus();
  });
  window.addEventListener('resize', () => {
    if (usageCyclePopover?.classList.contains('visible')) positionUsageCyclePopover();
    if (exportMenu?.classList.contains('visible')) positionExportMenu();
  });
  main?.addEventListener('scroll', () => {
    if (usageCyclePopover?.classList.contains('visible')) positionUsageCyclePopover();
  }, { passive:true });

  async function loadUsageToday(){
    usageModalBody.innerHTML = '<div class="usage-modal-loading">Loading usage…</div>';
    try {
      const data = await fetchUsageTodayData();
      updateUsageCycle(data);

      if (data.mode === 'testing') {
        usageModalBody.innerHTML = '<div class="usage-modal-empty">Usage tracking is off in testing mode.</div>';
        return;
      }

      // mode === 'default_groq' or 'own_key'
      const limit = data.daily_limit || 0;
      const used = data.used_today || 0;
      const remaining = data.remaining_today ?? Math.max(limit - used, 0);
      const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
      const barClass = pct >= 90 ? 'danger' : (pct >= 65 ? 'warn' : '');
      const resetIn = data.seconds_until_reset ? `Resets in ${formatDuration(data.seconds_until_reset)}` : '';
      const ownKey = data.mode === 'own_key' || data.using_own_key;
      const planName = data.plan_label || (ownKey ? 'Vigzone app cap • Personal Groq key' : 'Vigzone app cap • Default Groq key');
      const locked = !!data.is_limited;
      const estimated = Number(data.estimated_request_count_today || 0);
      const exact = Math.max(0, Number(data.request_count_today || 0) - estimated);
      const providerParts = providerRateSummary(data);
      const enforcedText = data.limit_enforced ? 'Limit enforced by Vigzone.' : 'Tracking only — no Vigzone block.';
      const planText = locked
        ? `${planName} is out of tokens for today. ${resetIn}`
        : ownKey
          ? `${planName} ⚡ — using your personal Groq quota. ${enforcedText} ${resetIn}`
          : `${planName} ⚡ — using Vigzone's default Groq key with an individual daily cap. ${resetIn}`;

      usageModalBody.innerHTML = `
        <div class="usage-modal-note">
          ${escapeHtml(planText)}
        </div>
        <div class="usage-modal-bar-track">
          <div class="usage-modal-bar-fill ${barClass}" style="width:${pct}%"></div>
        </div>
        <div class="usage-modal-total-row">
          <span>${used.toLocaleString()} used today</span>
          <span>${limit ? limit.toLocaleString() + ' daily limit' : ''}</span>
        </div>
        <div class="usage-modal-total-row">
          <span>${remaining.toLocaleString()} remaining today</span>
          <span>${resetIn}</span>
        </div>
        <div class="usage-modal-total-row">
          <span>${(data.request_count_today || 0).toLocaleString()} requests today</span>
          <span>${exact.toLocaleString()} exact${estimated ? ` · ${estimated.toLocaleString()} estimated` : ''}</span>
        </div>
        ${providerParts.map((part, index) => `<div class="usage-modal-total-row"><span>${index === 0 ? 'Live provider signal' : ''}</span><span>${escapeHtml(part)}</span></div>`).join('')}
        <div class="usage-modal-total-row">
          <span>Daily window</span>
          <span>${escapeHtml(data.timezone_label || '')}</span>
        </div>
        <div class="usage-modal-disclaimer">${escapeHtml(data.disclaimer || '')}</div>
      `;
    } catch (e) {
      usageModalBody.innerHTML = '<div class="usage-modal-empty">Couldn\'t load usage right now.</div>';
    }
  }

  function openUsageModal(){
    usageModalOverlay.classList.add('visible');
    loadUsageToday();
  }
  function closeUsageModal(){
    usageModalOverlay.classList.remove('visible');
  }

  if (usageTodayBtn) usageTodayBtn.addEventListener('click', openUsageModal);
  if (usageModalCloseBtn) usageModalCloseBtn.addEventListener('click', closeUsageModal);
  if (usageModalOverlay) usageModalOverlay.addEventListener('click', (e) => {
    if (e.target === usageModalOverlay) closeUsageModal();
  });


  // ---------- Admin-only professional dashboard JS ----------
  const adminProRoot = $('#adminProRoot');
  const adminProKpis = $('#adminProKpis');
  const adminProHealth = $('#adminProHealth');
  const adminProSubtitle = $('#adminProSubtitle');
  const adminTopUsersTable = $('#adminTopUsersTable');
  const adminProviderUsageTable = $('#adminProviderUsageTable');
  const adminRoutingUsageTable = $('#adminRoutingUsageTable');
  const adminContextTokenTable = $('#adminContextTokenTable');
  const adminSystemNotes = $('#adminSystemNotes');
  const adminBadFeedbackList = $('#adminBadFeedbackList');
  const adminProRefreshBtn = $('#adminProRefreshBtn');
  const adminProSignOutBtn = $('#adminProSignOutBtn');
  let adminLastDailyRows = [];
  let adminLastFeedbackMix = [];

  function adminFmt(n){ return Number(n || 0).toLocaleString(); }
  function adminShortDate(value){
    if (!value) return '—';
    const d = typeof value === 'number' ? new Date(value * 1000) : new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
  }
  function adminCanvasPrep(canvas){
    if (!canvas) return null;
    const wrap = canvas.closest('.admin-chart-wrap') || canvas.parentElement;
    if (!wrap) return null;

    // Lock the CSS size first. Without this, mobile browsers can briefly
    // measure the canvas at its internal bitmap size during refresh, causing
    // the huge clipped charts shown on phones.
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.display = 'block';

    const wrapRect = wrap.getBoundingClientRect();
    let cssW = Math.floor(wrap.clientWidth || wrapRect.width || 0);
    let cssH = Math.floor(wrap.clientHeight || wrapRect.height || 0);

    // If the card is still animating/layouting, skip this frame instead of
    // drawing into a bad 0px/giant canvas. A queued redraw handles the next frame.
    if (cssW < 40 || cssH < 80) return null;

    // Keep bitmap dimensions sane on mobile/high-DPI displays.
    cssW = Math.max(220, Math.min(cssW, 900));
    cssH = Math.max(150, Math.min(cssH, 260));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const pixelW = Math.floor(cssW * dpr);
    const pixelH = Math.floor(cssH * dpr);
    if (canvas.width !== pixelW) canvas.width = pixelW;
    if (canvas.height !== pixelH) canvas.height = pixelH;

    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.clearRect(0,0,cssW,cssH);
    return {ctx, w:cssW, h:cssH};
  }
  function cssVar(name, fallback){ return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback; }
  function drawUsageChart(rows){
    adminLastDailyRows = Array.isArray(rows) ? rows : [];
    const canvas = $('#adminUsageChart');
    const prep = adminCanvasPrep(canvas);
    if (!prep) return queueAdminChartRedraw();
    const {ctx,w,h} = prep;
    const compact = w < 420;
    const pad = compact ? {l:30,r:8,t:16,b:24} : {l:42,r:16,t:18,b:34};
    const plotW = Math.max(1, w-pad.l-pad.r);
    const plotH = Math.max(1, h-pad.t-pad.b);
    const max = Math.max(1, ...adminLastDailyRows.map(r => Number(r.tokens || 0)));
    const accent = cssVar('--accent','#ff6b4a');
    const accent2 = cssVar('--accent-2','#1aab94');
    const muted = cssVar('--text-muted','#8f96a8');
    const border = cssVar('--border','#ffffff22');

    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    for(let i=0;i<4;i++){
      const y=pad.t+plotH*(i/3);
      ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    }

    const rowCount = Math.max(adminLastDailyRows.length,1);
    const slot = plotW / rowCount;
    const barGap = compact ? Math.max(3, Math.min(7, slot * .18)) : 8;

    adminLastDailyRows.forEach((r,i)=>{
      const x = pad.l + i*slot + barGap;
      const bw = Math.max(compact ? 7 : 8, Math.min(54, slot - barGap*2));
      const bh = (Number(r.tokens || 0)/max)*plotH;
      const y = pad.t + plotH - bh;
      const grad = ctx.createLinearGradient(0,y,0,pad.t+plotH);
      grad.addColorStop(0, accent);
      grad.addColorStop(1, accent2);
      ctx.fillStyle = grad;
      const rr = Math.min(7, bw/2, Math.max(0,bh));
      ctx.beginPath();
      const x2=x+bw, y2=pad.t+plotH;
      ctx.moveTo(x+rr,y);
      ctx.lineTo(x2-rr,y);
      ctx.quadraticCurveTo(x2,y,x2,y+rr);
      ctx.lineTo(x2,y2);
      ctx.lineTo(x,y2);
      ctx.lineTo(x,y+rr);
      ctx.quadraticCurveTo(x,y,x+rr,y);
      ctx.fill();

      if (!compact || i % 2 === 0 || adminLastDailyRows.length <= 4) {
        ctx.fillStyle = muted;
        ctx.font = compact ? '9px Inter, sans-serif' : '10px Inter, sans-serif';
        ctx.textAlign='center';
        ctx.fillText(String(r.label || '').replace(/^Jul /,'J'), x+bw/2, h-8);
      }
    });

    ctx.fillStyle = muted;
    ctx.font = compact ? '10px Inter, sans-serif' : '11px Inter, sans-serif';
    ctx.textAlign='left';
    ctx.fillText('Tokens', 4, 13);
  }
  function drawFeedbackChart(mix){
    adminLastFeedbackMix = Array.isArray(mix) ? mix : [];
    const canvas = $('#adminFeedbackChart');
    const prep = adminCanvasPrep(canvas);
    if (!prep) return queueAdminChartRedraw();
    const {ctx,w,h} = prep;
    const good = Number((adminLastFeedbackMix.find(x=>/positive/i.test(x.name))||{}).value || 0);
    const bad = Number((adminLastFeedbackMix.find(x=>/negative|bad/i.test(x.name))||{}).value || 0);
    const shownTotal = good + bad;
    const total = Math.max(1, shownTotal);
    const compact = w < 420;

    const legendH = compact ? 22 : 30;
    const chartH = Math.max(1, h - legendH);
    const cx = w / 2;
    const cy = Math.max(54, Math.min(chartH / 2 + 4, h - legendH - 54));
    const r = Math.min(w * (compact ? 0.22 : 0.25), chartH * 0.38, compact ? 48 : 64);
    const colors = [cssVar('--accent-2','#1aab94'), cssVar('--danger','#e84a5a')];

    let start = -Math.PI/2;
    [good,bad].forEach((v,i)=>{
      const ang = (v/total)*Math.PI*2;
      ctx.beginPath();
      ctx.moveTo(cx,cy);
      ctx.arc(cx,cy,r,start,start+ang);
      ctx.closePath();
      ctx.fillStyle=colors[i];
      ctx.fill();
      start += ang;
    });

    ctx.globalCompositeOperation='destination-out';
    ctx.beginPath();
    ctx.arc(cx,cy,r*0.58,0,Math.PI*2);
    ctx.fill();
    ctx.globalCompositeOperation='source-over';

    ctx.fillStyle = cssVar('--text','#fff');
    ctx.font = compact ? '800 20px Sora, sans-serif' : '800 24px Sora, sans-serif';
    ctx.textAlign='center';
    ctx.fillText(String(shownTotal), cx, cy+3);
    ctx.fillStyle = cssVar('--text-muted','#999');
    ctx.font = compact ? '10px Inter, sans-serif' : '12px Inter, sans-serif';
    ctx.fillText(compact ? 'feedback' : 'feedbacks', cx, cy+(compact ? 21 : 24));

    const legendY = h - (compact ? 16 : 21);
    const leftX = compact ? 12 : 18;
    const rightX = Math.max(w/2 + (compact ? 4 : 14), leftX + 110);
    ctx.textAlign='left';
    ctx.font = compact ? '10px Inter, sans-serif' : '12px Inter, sans-serif';
    ctx.fillStyle=colors[0];
    ctx.fillRect(leftX,legendY-9,9,9);
    ctx.fillStyle=cssVar('--text-muted','#999');
    ctx.fillText(`Positive ${good}`,leftX+15,legendY);

    ctx.fillStyle=colors[1];
    ctx.fillRect(rightX,legendY-9,9,9);
    ctx.fillStyle=cssVar('--text-muted','#999');
    ctx.fillText(`Bad ${bad}`,rightX+15,legendY);
  }

  let adminChartRedrawQueued = false;
  function queueAdminChartRedraw(){
    if (adminChartRedrawQueued) return;
    adminChartRedrawQueued = true;
    requestAnimationFrame(() => {
      adminChartRedrawQueued = false;
      if (!document.body.classList.contains('admin-only')) return;
      drawUsageChart(adminLastDailyRows || []);
      drawFeedbackChart(adminLastFeedbackMix || []);
    });
  }
  function renderAdminProDashboard(data){
    const s = data.summary || {};
    if (adminProSubtitle) adminProSubtitle.textContent = `${data.admin?.email || 'Admin'} · ${data.version || ''}`;
    if (adminProHealth) adminProHealth.textContent = `Live · ${adminFmt(s.today_requests)} requests today`;
    const cards = [
      ['Total users', s.total_users, `${adminFmt(s.active_today)} active today`],
      ['Tokens today', s.today_tokens, `${adminFmt(s.today_requests)} requests`],
      ['Brain users', s.brain_users, `${adminFmt(s.share_count)} shared chats`],
      ['Bad feedback 👎', s.negative_feedback, `${adminFmt(s.positive_feedback)} positive`],
      ['Weekly tokens', s.week_tokens, `${adminFmt(s.week_active_users)} active users`],
      ['Own Groq keys', s.own_key_users, `${adminFmt(s.default_plan_users)} default plan users`],
      ['Feedback total', s.feedback_total, 'feedback records saved'],
      ['Fallbacks today', s.today_fallbacks, `${adminFmt(s.today_cached_tokens)} cached tokens`],
      ['Average latency', s.average_latency_ms, `${adminFmt(s.average_ttft_ms)} ms to first token`],
      ['Build', data.version || 'unknown', data.app_name || 'Vigzone AI'],
    ];
    if (adminProKpis) adminProKpis.innerHTML = cards.map(c => `<div class="admin-pro-card admin-pro-kpi"><div class="admin-pro-kpi-label">${escapeHtml(c[0])}</div><div class="admin-pro-kpi-value">${typeof c[1] === 'number' ? adminFmt(c[1]) : escapeHtml(c[1])}</div><div class="admin-pro-kpi-note">${escapeHtml(c[2] || '')}</div></div>`).join('');
    if (adminTopUsersTable) {
      const rows = (data.top_users || []).map(u => `<tr><td><strong>${escapeHtml(u.name || u.email || ('User '+u.id))}</strong><div class="admin-user-sub">${escapeHtml(u.email || '')}</div></td><td>${adminFmt(u.total_tokens)}</td><td>${adminFmt(u.requests)}</td><td><span class="admin-pill">${u.using_own_key ? 'Own key' : 'Default'}</span></td></tr>`).join('');
      adminTopUsersTable.innerHTML = `<thead><tr><th>User</th><th>Tokens</th><th>Req</th><th>Plan</th></tr></thead><tbody>${rows || '<tr><td colspan="4">No usage yet.</td></tr>'}</tbody>`;
    }
    if (adminProviderUsageTable) {
      const providerRows = (data.provider_usage || []).map(p => `<tr><td><strong>${escapeHtml(p.label || p.provider || 'Provider')}</strong><div class="admin-user-sub">${escapeHtml(p.provider || '')}</div></td><td>${adminFmt(p.tokens)}</td><td>${adminFmt(p.requests)}</td></tr>`).join('');
      adminProviderUsageTable.innerHTML = `<thead><tr><th>Provider</th><th>Tokens</th><th>Req</th></tr></thead><tbody>${providerRows || '<tr><td colspan="3">No provider usage yet.</td></tr>'}</tbody>`;
    }
    if (adminRoutingUsageTable) {
      const quality = new Map((data.quality_by_route || []).map(item => [`${item.model || 'unknown'}|${item.route_reason || 'unknown'}`, item]));
      const routeRows = (data.routing_usage || []).map(item => {
        const q = quality.get(`${item.model || 'unknown'}|${item.route_reason || 'unknown'}`);
        const qualityText = q ? `${q.positive_rate}% (${q.total})` : '—';
        return `<tr><td><strong>${escapeHtml(item.model || 'unknown')}</strong><div class="admin-user-sub">${escapeHtml(item.route_reason || 'legacy')} · ${escapeHtml(item.routing_mode || 'general')}</div></td><td>${adminFmt(item.requests)}</td><td>${adminFmt(item.tokens)}</td><td>${adminFmt(item.fallbacks)}</td><td>${adminFmt(item.average_latency_ms)} ms</td><td>${escapeHtml(qualityText)}</td></tr>`;
      }).join('');
      adminRoutingUsageTable.innerHTML = `<thead><tr><th>Model / route</th><th>Req</th><th>Tokens</th><th>Fallback</th><th>Latency</th><th>👍 rate</th></tr></thead><tbody>${routeRows || '<tr><td colspan="6">No routed usage yet.</td></tr>'}</tbody>`;
    }
    if (adminContextTokenTable) {
      const contextRows = (data.context_token_mix || []).map(item => `<tr><td><strong>${escapeHtml(String(item.name || 'context').replace(/_tokens$/,'').replaceAll('_',' '))}</strong></td><td>${adminFmt(item.tokens)}</td></tr>`).join('');
      adminContextTokenTable.innerHTML = `<thead><tr><th>Component</th><th>Estimated tokens</th></tr></thead><tbody>${contextRows || '<tr><td colspan="2">No context telemetry yet.</td></tr>'}</tbody>`;
    }
    if (adminSystemNotes) {
      const notes = data.system_notes || [];
      adminSystemNotes.innerHTML = notes.map(n => `<div class="admin-feedback-item"><div class="admin-feedback-top"><span>${escapeHtml(n.title || 'System')}</span><span>${escapeHtml(n.status || '')}</span></div><div class="admin-feedback-reason">${escapeHtml(n.value || '')}</div><div class="admin-feedback-text">${escapeHtml(n.note || '')}</div></div>`).join('') || '<div class="brain-empty">No system notes.</div>';
    }
    if (adminBadFeedbackList) {
      adminBadFeedbackList.innerHTML = (data.bad_feedback || []).map(f => `<div class="admin-feedback-item"><div class="admin-feedback-top"><span>${escapeHtml(f.email || 'Unknown user')}</span><span>${escapeHtml(adminShortDate(f.created_at))}</span></div><div class="admin-feedback-reason">${escapeHtml(f.reason || 'No reason provided')}</div><div class="admin-user-sub">${escapeHtml(f.context?.model || 'unknown model')} · ${escapeHtml(f.context?.route_reason || 'unknown route')}</div><div class="admin-feedback-text">${escapeHtml(f.assistant_text || '')}</div></div>`).join('') || '<div class="brain-empty">No bad feedback yet. Great bro 😁</div>';
    }
    adminLastDailyRows = data.daily || [];
    adminLastFeedbackMix = data.feedback_mix || [];
    requestAnimationFrame(() => requestAnimationFrame(queueAdminChartRedraw));
  }
  async function loadAdminProDashboard(){
    if (adminProHealth) adminProHealth.textContent = 'Loading system…';
    try{
      const res = await fetch('/api/admin/full-dashboard', {credentials:'same-origin'});
      const data = await res.json();
      if(!res.ok) throw new Error(data.detail || 'Could not load admin dashboard.');
      renderAdminProDashboard(data);
    }catch(e){
      if (adminProHealth) adminProHealth.textContent = 'Dashboard error';
      if (adminProKpis) adminProKpis.innerHTML = `<div class="brain-empty">${escapeHtml(e.message || 'Could not load admin dashboard.')}</div>`;
    }
  }
  function clearAccountScopedClientState(){
    try {
      sessionStorage.clear();
    } catch {}
    accountStorageScope = 'guest';
    CONV_STORE_KEY = scopedLocalKey(CONV_STORE_KEY_BASE);
    LEGACY_KEY = scopedLocalKey(LEGACY_KEY_BASE);
    BRAIN_META_KEY = scopedLocalKey(BRAIN_META_KEY_BASE);
    try { localStorage.setItem(LAST_SCOPE_KEY, 'guest'); } catch {}
    store = loadStore();
    messages = [];
  }
  async function adminProSignOut(){
    try { await fetch('/api/auth/logout', { method:'POST', credentials:'same-origin' }); } catch {}
    clearAccountScopedClientState();
    window.location.href = '/';
  }
  function enterAdminOnlyDashboard(user){
    document.body.classList.add('admin-only');
    document.body.style.display = 'block';
    userName = (user && (user.name || user.email)) || 'Admin';
    clearAccountScopedClientState();
    loadAdminProDashboard();
  }
  adminProRefreshBtn?.addEventListener('click', loadAdminProDashboard);
  adminProSignOutBtn?.addEventListener('click', adminProSignOut);
  try {
    const adminChartObserver = new ResizeObserver(() => {
      if (document.body.classList.contains('admin-only')) queueAdminChartRedraw();
    });
    document.querySelectorAll('.admin-chart-wrap').forEach(el => adminChartObserver.observe(el));
  } catch {}
  let adminResizeTimer = null;
  window.addEventListener('resize', () => {
    if (!document.body.classList.contains('admin-only')) return;
    clearTimeout(adminResizeTimer);
    adminResizeTimer = setTimeout(queueAdminChartRedraw, 120);
  });

  // ---------- Admin dashboard ----------
  async function loadAdminDashboard(){
    if (!adminModalBody) return;
    adminModalBody.innerHTML = '<div class="usage-modal-loading">Loading admin data…</div>';
    try {
      const res = await fetch('/api/admin/overview', { credentials: 'include' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not load admin data.');
      let productAnalytics = null;
      try {
        const ar = await fetch('/api/admin/analytics', { credentials:'include' });
        if (ar.ok) productAnalytics = await ar.json();
      } catch {}
      const topRows = (data.top_users || []).map(u => `
        <tr>
          <td>${escapeHtml(u.name || u.email || ('User ' + u.id))}<br><span style="color:var(--text-muted);font-size:10px;">${escapeHtml(u.using_own_key ? 'own key' : 'default Groq')}</span></td>
          <td>${(u.total_tokens || 0).toLocaleString()}</td>
          <td>${(u.requests || 0).toLocaleString()}</td>
          <td><button class="admin-reset-btn" data-reset-user="${u.id}">Reset</button></td>
        </tr>
      `).join('');
      adminModalBody.innerHTML = `
        <div class="admin-grid">
          <div class="admin-card"><div class="admin-card-label">Total users</div><div class="admin-card-value">${(data.total_users || 0).toLocaleString()}</div></div>
          <div class="admin-card"><div class="admin-card-label">Active today</div><div class="admin-card-value">${(data.active_today || 0).toLocaleString()}</div></div>
          <div class="admin-card"><div class="admin-card-label">Tokens today</div><div class="admin-card-value">${((data.today && data.today.total_tokens) || 0).toLocaleString()}</div></div>
          <div class="admin-card"><div class="admin-card-label">Requests today</div><div class="admin-card-value">${((data.today && data.today.requests) || 0).toLocaleString()}</div></div>
          <div class="admin-card"><div class="admin-card-label">Brain users</div><div class="admin-card-value">${((productAnalytics && productAnalytics.brain_users) || 0).toLocaleString()}</div></div>
          <div class="admin-card"><div class="admin-card-label">Feedback</div><div class="admin-card-value">${((productAnalytics && productAnalytics.feedback_count) || 0).toLocaleString()}</div></div>
          <div class="admin-card"><div class="admin-card-label">Shares</div><div class="admin-card-value">${((productAnalytics && productAnalytics.share_count) || 0).toLocaleString()}</div></div>
        </div>
        <div class="usage-modal-note">Default-plan users: ${(data.default_plan_users || 0).toLocaleString()} · Own-key users: ${(data.own_key_users || 0).toLocaleString()} · Build: ${escapeHtml((productAnalytics && productAnalytics.version) || 'unknown')}</div>
        <table class="admin-table">
          <thead><tr><th>User</th><th>Tokens</th><th>Req</th><th>Action</th></tr></thead>
          <tbody>${topRows || '<tr><td colspan="4">No usage yet today.</td></tr>'}</tbody>
        </table>
      `;
      adminModalBody.querySelectorAll('[data-reset-user]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const id = btn.getAttribute('data-reset-user');
          btn.disabled = true;
          btn.textContent = 'Resetting…';
          try {
            await fetch(`/api/admin/users/${id}/usage/reset`, { method: 'POST', credentials: 'include' });
            await loadAdminDashboard();
          } catch (e) {
            btn.textContent = 'Failed';
            btn.disabled = false;
          }
        });
      });
    } catch (e) {
      adminModalBody.innerHTML = `<div class="usage-modal-empty">${escapeHtml(e.message || 'Could not load admin data.')}</div>`;
    }
  }
  function openAdminModal(){ adminModalOverlay?.classList.add('visible'); loadAdminDashboard(); }
  function closeAdminModal(){ adminModalOverlay?.classList.remove('visible'); }
  if (adminPanelBtn) adminPanelBtn.addEventListener('click', openAdminModal);
  if (adminModalCloseBtn) adminModalCloseBtn.addEventListener('click', closeAdminModal);
  if (adminModalOverlay) adminModalOverlay.addEventListener('click', (e) => {
    if (e.target === adminModalOverlay) closeAdminModal();
  });

  // ---------- Bring-your-own Groq API key box ----------
  let groqKeyValidatedValue = null; // tracks which exact key string last passed validation

  function setApiKeyBoxMode(usingOwnKey){
    if (apiKeyModeBadge) {
      apiKeyModeBadge.textContent = usingOwnKey ? (liveConfig.labels?.api_own || 'Groq (your key)') : (liveConfig.labels?.api_default || 'Groq (default)');
      apiKeyModeBadge.classList.toggle('own-key', !!usingOwnKey);
    }
    if (apiKeyInputSection) apiKeyInputSection.style.display = usingOwnKey ? 'none' : '';
    if (apiKeyActiveSection) apiKeyActiveSection.style.display = usingOwnKey ? 'flex' : 'none';
  }

  async function refreshApiKeyBox(){
    try {
      const res = await fetch('/api/me/usage', { credentials: 'include' });
      if (!res.ok) return;
      const data = await res.json();
      if (data.mode === 'testing') return; // no key management shown differently in testing
      setApiKeyBoxMode(!!data.using_own_key);
    } catch (e) { /* silent — sidebar cosmetic only */ }
  }

  function resetGroqCheckButton(){
    groqKeyValidatedValue = null;
    if (groqKeyCheckBtn) {
      groqKeyCheckBtn.textContent = 'Check';
      groqKeyCheckBtn.classList.remove('ready-to-use');
    }
  }

  if (groqKeyInput) {
    groqKeyInput.addEventListener('input', () => {
      if (groqKeyValidatedValue !== null && groqKeyInput.value !== groqKeyValidatedValue) {
        resetGroqCheckButton();
        if (groqKeyStatus) { groqKeyStatus.textContent = ''; groqKeyStatus.className = 'api-key-status'; }
      }
    });
  }

  if (groqKeyCheckBtn) {
    groqKeyCheckBtn.addEventListener('click', async () => {
      const value = (groqKeyInput.value || '').trim();
      if (!value) return;

      // Second click after a successful check → actually activate it.
      if (groqKeyValidatedValue === value) {
        groqKeyCheckBtn.disabled = true;
        groqKeyCheckBtn.textContent = 'Activating…';
        try {
          const res = await fetch('/api/me/groq-key/activate', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: value }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Could not activate this key.');
          groqKeyInput.value = '';
          resetGroqCheckButton();
          if (groqKeyStatus) { groqKeyStatus.textContent = ''; groqKeyStatus.className = 'api-key-status'; }
          setApiKeyBoxMode(true);
          refreshUsageCycle();
        } catch (e) {
          if (groqKeyStatus) {
            groqKeyStatus.textContent = e.message || "Couldn't activate this key.";
            groqKeyStatus.className = 'api-key-status err';
          }
          groqKeyCheckBtn.textContent = 'Use this key';
        } finally {
          groqKeyCheckBtn.disabled = false;
        }
        return;
      }

      // First click → just validate, don't save anything yet.
      groqKeyCheckBtn.disabled = true;
      groqKeyCheckBtn.textContent = 'Checking…';
      if (groqKeyStatus) { groqKeyStatus.textContent = ''; groqKeyStatus.className = 'api-key-status'; }
      try {
        const res = await fetch('/api/me/groq-key/validate', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: value }),
        });
        const data = await res.json();
        if (data.valid) {
          groqKeyValidatedValue = value;
          groqKeyCheckBtn.textContent = 'Use this key';
          groqKeyCheckBtn.classList.add('ready-to-use');
          if (groqKeyStatus) {
            groqKeyStatus.textContent = data.message || 'This key works.';
            groqKeyStatus.className = 'api-key-status ok';
          }
        } else {
          resetGroqCheckButton();
          if (groqKeyStatus) {
            groqKeyStatus.textContent = data.message || "This key doesn't seem to work.";
            groqKeyStatus.className = 'api-key-status err';
          }
        }
      } catch (e) {
        resetGroqCheckButton();
        if (groqKeyStatus) {
          groqKeyStatus.textContent = "Couldn't check that key right now.";
          groqKeyStatus.className = 'api-key-status err';
        }
      } finally {
        groqKeyCheckBtn.disabled = false;
      }
    });
  }

  if (groqKeyDeactivateBtn) {
    groqKeyDeactivateBtn.addEventListener('click', async () => {
      groqKeyDeactivateBtn.disabled = true;
      try {
        await fetch('/api/me/groq-key/deactivate', { method: 'POST', credentials: 'include' });
      } catch (e) { /* best-effort */ }
      groqKeyDeactivateBtn.disabled = false;
      setApiKeyBoxMode(false);
      refreshUsageCycle();
    });
  }

  // ---------- Personalized greeting (name comes from the signed-in account) ----------
  function greetingOptions(){ return (liveConfig && Array.isArray(liveConfig.greetings) && liveConfig.greetings.length) ? liveConfig.greetings : ['Welcome back,']; }

  function accountInitial(name){
    const safe = (name || '').trim();
    return (Array.from(_graphemeSegmenter ? _graphemeSegmenter.segment(safe) : safe, s => s.segment ?? s)[0] || '?').toUpperCase();
  }

  function updateGreeting(){
    const displayName = userName || 'Signed in';
    if (userName) {
      const gs = greetingOptions();
      const g = gs[Math.floor(Math.random() * gs.length)];
      greetingText.textContent = `${g} ${userName}`;
    } else {
      greetingText.textContent = `Welcome to ${liveConfig.app_name || 'Vigzone AI'}`;
    }

    if (sidebarUserName) sidebarUserName.textContent = displayName;
    if (sidebarUserDot) sidebarUserDot.textContent = userName ? accountInitial(userName) : '?';
    if (settingsUserName) settingsUserName.textContent = displayName;
    if (settingsUserDot) settingsUserDot.textContent = userName ? accountInitial(userName) : '?';
  }

  async function loadAccount(){
    try {
      const res = await fetch('/api/auth/me', { credentials: 'same-origin' });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        userName = (data.user && data.user.name) || (data.user && data.user.email) || '';
        if (data.user) switchAccountStorageScope(data.user);
        if (data.user && data.user.is_admin) {
          enterAdminOnlyDashboard(data.user);
          return;
        }
        document.body.classList.remove('admin-only');
        if (adminPanelRow) adminPanelRow.style.display = 'none';
        updateGreeting();
        refreshApiKeyBox();
        refreshUsageCycle();
      } else if (window.location.pathname === '/chat' || window.location.pathname.startsWith('/chat/')) {
        window.location.href = '/';
        return;
      }
    } catch(e) {
      console.error("Auth check failed, likely offline.", e);
    }
  }

  // ---------- Settings + curated doodle chat themes ----------

  function openSettingsModal(){
    updateGreeting();
    settingsModalOverlay?.classList.add('visible');
    loadSharedLinks();
  }

  function closeSettingsModal(){
    settingsModalOverlay?.classList.remove('visible');
  }

  function openChatThemePicker(){
    openSettingsModal();
    window.setTimeout(() => {
      chatThemeSettingsSection?.scrollIntoView({ behavior:'smooth', block:'nearest' });
      chatThemeGrid?.querySelector('[aria-checked="true"]')?.focus({ preventScroll:true });
    }, 40);
  }

  settingsBtn?.addEventListener('click', openSettingsModal);
  chatThemeBtnSidebar?.addEventListener('click', openChatThemePicker);
  settingsModalCloseBtn?.addEventListener('click', closeSettingsModal);
  settingsModalOverlay?.addEventListener('click', e => { if (e.target === settingsModalOverlay) closeSettingsModal(); });

  chatThemeGrid?.addEventListener('click', (event) => {
    const option = event.target.closest('[data-chat-theme-option]');
    if (!option || !chatThemeGrid.contains(option)) return;
    selectChatTheme(option.dataset.chatThemeOption);
  });

  chatThemeGrid?.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    const options = Array.from(chatThemeGrid.querySelectorAll('[data-chat-theme-option]'));
    const currentIndex = options.indexOf(event.target.closest('[data-chat-theme-option]'));
    if (currentIndex < 0 || !options.length) return;
    event.preventDefault();
    const direction = ['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1;
    const next = options[(currentIndex + direction + options.length) % options.length];
    next.focus();
    selectChatTheme(next.dataset.chatThemeOption);
  });

  async function signOut(){
    try {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
    } catch {}
    clearAccountScopedClientState?.();
    window.location.href = '/';
  }

  signOutBtn?.addEventListener('click', signOut);

  function shareExpiryLabel(value){
    const parsed = new Date(value || '');
    if (Number.isNaN(parsed.getTime())) return 'Expiry unavailable';
    return `Expires ${parsed.toLocaleString()}`;
  }

  async function loadSharedLinks(){
    if (!sharedLinksList) return;
    sharedLinksList.innerHTML = '<div class="shared-links-empty">Loading shared links…</div>';
    if (refreshSharedLinksBtn) refreshSharedLinksBtn.disabled = true;
    try {
      const response = await fetch('/api/share/chats', {credentials:'same-origin'});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Could not load shared links.');
      const shares = Array.isArray(data.shares) ? data.shares : [];
      if (!shares.length) {
        sharedLinksList.innerHTML = '<div class="shared-links-empty">No shared chat links yet.</div>';
        return;
      }
      const now = Date.now();
      sharedLinksList.innerHTML = shares.map((share) => {
        const expired = Number.isFinite(Date.parse(share.expires_at)) && Date.parse(share.expires_at) <= now;
        const inactive = !!share.revoked || expired;
        const status = share.revoked ? 'Revoked' : (expired ? 'Expired' : shareExpiryLabel(share.expires_at));
        const safeId = String(share.id || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 32);
        return `<div class="shared-link-row">
          <div class="shared-link-main">
            <div class="shared-link-title">${escapeHtml(String(share.title || 'Vigzone chat'))}</div>
            <div class="shared-link-meta">${escapeHtml(status)}</div>
          </div>
          <div class="shared-link-actions">
            ${inactive ? '' : `<button class="edit-name-btn" type="button" data-share-copy="${safeId}">Copy</button><button class="edit-name-btn" type="button" data-share-open="${safeId}">Open</button><button class="edit-name-btn shared-link-revoke" type="button" data-share-revoke="${safeId}">Revoke</button>`}
          </div>
        </div>`;
      }).join('');
    } catch (error) {
      sharedLinksList.innerHTML = `<div class="shared-links-empty">${escapeHtml(error.message || 'Could not load shared links.')}</div>`;
    } finally {
      if (refreshSharedLinksBtn) refreshSharedLinksBtn.disabled = false;
    }
  }

  refreshSharedLinksBtn?.addEventListener('click', loadSharedLinks);
  sharedLinksList?.addEventListener('click', async (event) => {
    const copyButton = event.target.closest('[data-share-copy]');
    if (copyButton) {
      const url = new URL(`/share/${copyButton.dataset.shareCopy}`, location.origin).href;
      try {
        await navigator.clipboard.writeText(url);
        suiteToast?.('Share link copied.');
      } catch {
        window.prompt('Copy this share link:', url);
      }
      return;
    }
    const openButton = event.target.closest('[data-share-open]');
    if (openButton) {
      window.open(`/share/${openButton.dataset.shareOpen}`, '_blank', 'noopener,noreferrer');
      return;
    }
    const revokeButton = event.target.closest('[data-share-revoke]');
    if (!revokeButton) return;
    if (!window.confirm('Revoke this public share link now?')) return;
    revokeButton.disabled = true;
    try {
      const response = await fetch(`/api/share/chat/${revokeButton.dataset.shareRevoke}`, {
        method:'DELETE',
        credentials:'same-origin'
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Could not revoke this link.');
      suiteToast?.('Share link revoked.');
      await loadSharedLinks();
    } catch (error) {
      suiteToast?.(error.message || 'Could not revoke this link.');
      revokeButton.disabled = false;
    }
  });

  exportAccountBtn?.addEventListener('click', async () => {
    const previous = exportAccountBtn.textContent;
    exportAccountBtn.disabled = true;
    exportAccountBtn.textContent = 'Exporting…';
    try {
      const response = await fetch('/api/account/export', {credentials:'same-origin'});
      const data = await response.blob();
      if (!response.ok) {
        const errorBody = await data.text().catch(() => '');
        let detail = '';
        try { detail = JSON.parse(errorBody).detail || ''; } catch {}
        throw new Error(detail || 'Account export failed.');
      }
      const url = URL.createObjectURL(data);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'vigzone-account-export.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      suiteToast?.('Your account export is ready.');
    } catch (error) {
      suiteToast?.(error.message || 'Could not export account data.');
    } finally {
      exportAccountBtn.disabled = false;
      exportAccountBtn.textContent = previous;
    }
  });

  changePasswordBtn?.addEventListener('click', async () => {
    const currentPassword = window.prompt('Current password (leave blank if you only use Google sign-in):');
    if (currentPassword === null) return;
    const newPassword = window.prompt('New password (at least 10 characters):');
    if (newPassword === null) return;
    if (newPassword.length < 10) {
      suiteToast?.('The new password must be at least 10 characters.');
      return;
    }
    changePasswordBtn.disabled = true;
    try {
      const response = await fetch('/api/account/password', {
        method:'POST',
        credentials:'same-origin',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({current_password:currentPassword, new_password:newPassword})
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Password change failed.');
      alert('Password changed. Please sign in again.');
      window.location.href = '/';
    } catch (error) {
      suiteToast?.(error.message || 'Could not change password.');
    } finally {
      changePasswordBtn.disabled = false;
    }
  });

  function clearDeletedAccountClientData(){
    [
      CONV_STORE_KEY,
      LEGACY_KEY,
      BRAIN_META_KEY,
      scopedLocalKey('vigzone_uploaded_files_v1'),
      scopedLocalKey('vigzone_mode_memory_v1')
    ].forEach((key) => {
      try { localStorage.removeItem(key); } catch {}
    });
    try { sessionStorage.clear(); } catch {}
    clearAccountScopedClientState();
  }

  deleteAccountBtn?.addEventListener('click', async () => {
    const confirmation = window.prompt('This permanently deletes your Vigzone account and cloud data. Type DELETE to continue:');
    if (confirmation !== 'DELETE') {
      if (confirmation !== null) suiteToast?.('Account deletion cancelled.');
      return;
    }
    const password = window.prompt('Confirm your password (leave blank if you only use Google sign-in):');
    if (password === null) return;
    deleteAccountBtn.disabled = true;
    try {
      const response = await fetch('/api/account', {
        method:'DELETE',
        credentials:'same-origin',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({confirmation:'DELETE', password})
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Account deletion failed.');
      clearDeletedAccountClientData();
      window.location.href = '/';
    } catch (error) {
      suiteToast?.(error.message || 'Could not delete account.');
      deleteAccountBtn.disabled = false;
    }
  });

  function autoResize(){
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  }
  input.addEventListener('input', autoResize);

  let followLatestMessage = true;
  let programmaticScrollUntil = 0;
  let touchScrollY = null;

  function chatDistanceFromBottom(){
    return Math.max(0, main.scrollHeight - main.clientHeight - main.scrollTop);
  }

  function scrollToBottom(smooth, force = true){
    if (!force && !followLatestMessage) {
      updateScrollBtnVisibility();
      return;
    }
    if (force) followLatestMessage = true;
    const bottom = Math.max(0, main.scrollHeight - main.clientHeight);
    if (smooth) {
      programmaticScrollUntil = Date.now() + 520;
      main.scrollTo({ top: bottom, behavior: 'smooth' });
      setTimeout(() => {
        main.scrollTop = Math.max(0, main.scrollHeight - main.clientHeight);
        followLatestMessage = true;
        updateScrollBtnVisibility();
      }, 420);
      return;
    }
    // Force an instant jump regardless of the CSS scroll-behavior:smooth rule.
    // Without this, rapid auto-scroll calls during streaming fight the smooth
    // animation and can land short of the true bottom, leaving the button
    // stuck visible even though the user is effectively at the latest message.
    const prevBehavior = main.style.scrollBehavior;
    main.style.scrollBehavior = 'auto';
    main.scrollTop = Math.max(0, main.scrollHeight - main.clientHeight);
    main.style.scrollBehavior = prevBehavior || '';
  }

  function scrollLatestIfFollowing(){
    scrollToBottom(false, false);
  }

  let scrollBtnRaf = null;

  function positionScrollToBottomBtn(){
    if (!scrollToBottomBtn) return;
    const mainRect = main.getBoundingClientRect();
    const composerWrap = document.querySelector('.composer-wrap');
    const composerRect = composerWrap ? composerWrap.getBoundingClientRect() : null;

    // Center the arrow in the chat column, not the whole browser window.
    const x = mainRect.left + (mainRect.width / 2);

    // Place it exactly above the composer/message box, like ChatGPT.
    // This automatically adapts when attachments/quote preview increase composer height.
    const composerTop = composerRect ? composerRect.top : (window.innerHeight - 96);
    const bottom = Math.max(72, Math.round(window.innerHeight - composerTop + 12));

    scrollToBottomBtn.style.left = `${Math.round(x)}px`;
    scrollToBottomBtn.style.bottom = `${bottom}px`;
  }

  function updateScrollBtnVisibility(){
    if (scrollBtnRaf) return;
    scrollBtnRaf = requestAnimationFrame(() => {
      scrollBtnRaf = null;
      positionScrollToBottomBtn();

      const distanceFromBottom = chatDistanceFromBottom();
      const hasScrollableChat = main.scrollHeight > main.clientHeight + 40;

      // Streaming follows the newest text only while the reader remains near
      // the bottom. Scrolling upward immediately hands control to the reader;
      // returning to the bottom resumes follow mode automatically.
      if (Date.now() >= programmaticScrollUntil) {
        followLatestMessage = distanceFromBottom <= 72;
      }

      // Show only when the user has scrolled up away from the latest message.
      scrollToBottomBtn?.classList.toggle('visible', hasScrollableChat && distanceFromBottom > 72);
    });
  }

  main.addEventListener('scroll', updateScrollBtnVisibility, { passive:true });
  main.addEventListener('wheel', event => {
    if (event.deltaY < 0) followLatestMessage = false;
  }, { passive:true });
  main.addEventListener('touchstart', event => {
    touchScrollY = event.touches?.[0]?.clientY ?? null;
  }, { passive:true });
  main.addEventListener('touchmove', event => {
    const nextY = event.touches?.[0]?.clientY;
    if (touchScrollY !== null && Number.isFinite(nextY) && nextY - touchScrollY > 6) {
      followLatestMessage = false;
    }
    if (Number.isFinite(nextY)) touchScrollY = nextY;
  }, { passive:true });
  main.addEventListener('touchend', () => { touchScrollY = null; }, { passive:true });
  window.addEventListener('resize', updateScrollBtnVisibility, { passive:true });
  window.addEventListener('orientationchange', updateScrollBtnVisibility, { passive:true });

  try {
    const composerWrap = document.querySelector('.composer-wrap');
    if (window.ResizeObserver && composerWrap) {
      new ResizeObserver(updateScrollBtnVisibility).observe(composerWrap);
    }
  } catch {}

  updateScrollBtnVisibility();

  scrollToBottomBtn?.addEventListener('click', () => {
    scrollToBottom(true);
    setTimeout(updateScrollBtnVisibility, 280);
  });
  goToBottomBtn?.addEventListener('click', () => {
    scrollToBottom(true);
    setTimeout(updateScrollBtnVisibility, 280);
  });

  // ---------- Quote / reply-to ----------
  function setQuote(role, fullText, index){
    if (!fullText) return;
    quotedMessage = { role, fullText, index };
    renderQuotePreview();
    input.focus();
  }

  function clearQuote(){
    quotedMessage = null;
    renderQuotePreview();
  }

  function renderQuotePreview(){
    const bar = document.getElementById('quotePreviewBar');
    if (!quotedMessage) { bar.style.display = 'none'; bar.innerHTML = ''; return; }
    const label = quotedMessage.role === 'user' ? 'You' : 'Vigzone AI';
    const snippet = truncateText(quotedMessage.fullText, 160);
    bar.style.display = 'block';
    bar.innerHTML = `
      <div class="quote-chip">
        <svg class="quote-chip-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 17H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2"></path><path d="M9 7V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2h-6l-4 4v-4z"></path></svg>
        <div class="quote-chip-body">
          <span class="quote-chip-label">Replying to ${escapeHtml(label)}</span>
          <span class="quote-chip-text">${escapeHtml(snippet)}</span>
        </div>
        <button class="quote-chip-remove" data-action="clear-quote" aria-label="Remove quote" title="Remove quote">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>`;
  }

  // Delegated listener — reliable on both mobile touch and desktop click
  (function(){
    const _qbar = document.getElementById('quotePreviewBar');
    _qbar.addEventListener('click', function(e){
      if (e.target.closest('[data-action="clear-quote"]')) clearQuote();
    });
    _qbar.addEventListener('touchend', function(e){
      if (e.target.closest('[data-action="clear-quote"]')) { e.preventDefault(); clearQuote(); }
    });
  })();


  // ===== VIGZONE VOICE — "Vigi" (read-aloud) =====
  // Gives Vigzone AI a single, consistent spoken voice using the browser's
  // built-in speech synthesis. We pick one male-sounding voice the first
  // time it's needed and stick with it for the whole session — we call this
  // persona "Vigi" — so every message is read consistently rather than
  // whatever the OS happens to default to. Voices are cached per detected
  // language (see detectSpeechLang below) so a Sinhala reply gets a Sinhala
  // voice instead of being forced through an English one.
  let vigzoneSpeakingBtn = null;
  let vigzoneUtterance = null;
  const vigzoneVoiceCache = new Map(); // langHint (or '' for default/English) -> voice

  // Roughly ordered by how convincingly male + natural they sound across
  // common platforms (Chrome/Edge on Windows, Chrome on Android, Safari/macOS).
  // Only used for the English/default case — non-English replies get matched
  // by language instead (see pickVigzoneVoice).
  const VIGZONE_VOICE_PREFERENCES = [
    'Microsoft Guy Online (Natural) - English (United States)',
    'Microsoft Ryan Online (Natural) - English (United Kingdom)',
    'Microsoft Guy',
    'Microsoft David - English (United States)',
    'Microsoft David',
    'Google UK English Male',
    'Daniel',
    'Alex',
    'Fred',
    'Arthur',
    'Oliver',
  ];

  // Best-effort script-based language detection for picking a read-aloud
  // voice. Counts characters per Unicode script block and returns the
  // script with the most hits as a BCP-47 tag; returns null for Latin/
  // ambiguous text, since script alone can't tell English from Spanish from
  // French — callers fall back to the "Vigi" English voice in that case.
  const SPEECH_SCRIPT_RANGES = [
    ['si-LK', /[\u0D80-\u0DFF]/g],          // Sinhala
    ['ta-IN', /[\u0B80-\u0BFF]/g],          // Tamil
    ['hi-IN', /[\u0900-\u097F]/g],          // Devanagari (Hindi, Marathi, Nepali…)
    ['ar-SA', /[\u0600-\u06FF\u0750-\u077F]/g], // Arabic
    ['he-IL', /[\u0590-\u05FF]/g],          // Hebrew
    ['th-TH', /[\u0E00-\u0E7F]/g],          // Thai
    ['ko-KR', /[\uAC00-\uD7A3]/g],          // Hangul
    ['ja-JP', /[\u3040-\u30FF]/g],          // Hiragana / Katakana
    ['zh-CN', /[\u4E00-\u9FFF]/g],          // CJK Unified Ideographs
    ['ru-RU', /[\u0400-\u04FF]/g],          // Cyrillic
    ['el-GR', /[\u0370-\u03FF]/g],          // Greek
  ];

  function detectSpeechLang(text) {
    if (!text) return null;
    let best = null, bestCount = 0;
    for (const [lang, re] of SPEECH_SCRIPT_RANGES) {
      const count = (text.match(re) || []).length;
      if (count > bestCount) { bestCount = count; best = lang; }
    }
    // Require a few script characters before trusting it, so one stray
    // symbol in an otherwise-English reply doesn't switch the voice.
    return bestCount >= 2 ? best : null;
  }

  function pickVigzoneVoice(langHint) {
    const cacheKey = langHint || '';
    if (vigzoneVoiceCache.has(cacheKey)) return vigzoneVoiceCache.get(cacheKey);
    if (!('speechSynthesis' in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    if (!voices.length) return null; // not loaded yet — caller will retry

    let picked = null;

    if (langHint) {
      // Non-English script detected — find a voice for that language so
      // e.g. Sinhala text isn't read aloud in an English accent.
      const prefix = langHint.split('-')[0].toLowerCase();
      picked = voices.find(v => v.lang.toLowerCase() === langHint.toLowerCase())
            || voices.find(v => v.lang.toLowerCase().startsWith(prefix));
    }

    if (!picked) {
      for (const name of VIGZONE_VOICE_PREFERENCES) {
        const match = voices.find(v => v.name === name);
        if (match) { picked = match; break; }
      }
    }
    if (!picked) {
      // No exact known-name match — guess by name containing "male" but not "female".
      picked = voices.find(v => /male/i.test(v.name) && !/female/i.test(v.name) && v.lang.startsWith('en'));
    }
    if (!picked) {
      // Last resort: any English voice, so Vigzone still has a consistent voice.
      picked = voices.find(v => v.lang.startsWith('en')) || voices[0] || null;
    }

    vigzoneVoiceCache.set(cacheKey, picked);
    return picked;
  }

  if ('speechSynthesis' in window) {
    window.speechSynthesis.onvoiceschanged = () => {
      vigzoneVoiceCache.clear(); // re-pick now that the full voice list is in
      pickVigzoneVoice();
    };
  }

  // Strips common Markdown and emoji so the speaker doesn't read out
  // asterisks, hashes, backticks, or emoji descriptions.
  const EMOJI_REGEX = /[\u{1F1E6}-\u{1F1FF}\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}\u{1F000}-\u{1F0FF}\u{FE0F}\u{200D}]/gu;

  function stripForSpeech(text) {
    if (!text) return '';
    return text
      .replace(/```[\s\S]*?```/g, ' Code block omitted. ')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
      .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/\*([^*]+)\*/g, '$1')
      .replace(/__([^_]+)__/g, '$1')
      .replace(/_([^_]+)_/g, '$1')
      .replace(/^>\s?/gm, '')
      .replace(/^[-*+]\s+/gm, '')
      .replace(/^\d+\.\s+/gm, '')
      .replace(/[-=]{3,}/g, ' ')
      .replace(EMOJI_REGEX, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function resetSpeakerButton(btn) {
    if (!btn) return;
    btn.classList.remove('speaking');
    btn.innerHTML = ICON_SPEAKER;
    btn.setAttribute('aria-label', 'Read aloud in Vigi');
  }

  function vigzoneStopSpeaking() {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (vigzoneSpeakingBtn) resetSpeakerButton(vigzoneSpeakingBtn);
    vigzoneSpeakingBtn = null;
    vigzoneUtterance = null;
  }

  function vigzoneSpeak(rawText, btn) {
    if (!('speechSynthesis' in window)) {
      console.warn('Vigzone AI: speech synthesis is not supported in this browser.');
      return;
    }

    // Clicking the button that's already speaking just stops it.
    if (vigzoneSpeakingBtn === btn) {
      vigzoneStopSpeaking();
      return;
    }

    // Switching to a different message — stop whatever was playing first.
    vigzoneStopSpeaking();

    const clean = stripForSpeech(rawText);
    if (!clean) return;

    const langHint = detectSpeechLang(clean);
    const utter = new SpeechSynthesisUtterance(clean);
    const voice = pickVigzoneVoice(langHint);
    if (voice) utter.voice = voice;
    utter.lang = (voice && voice.lang) || langHint || 'en-US';
    utter.rate = 0.97;
    utter.pitch = 0.85; // smooth, grounded tone — Vigzone's "Vigi" persona
    utter.volume = 1;

    utter.onstart = () => {
      vigzoneSpeakingBtn = btn;
      btn.classList.add('speaking');
      btn.innerHTML = ICON_SPEAKER_STOP;
      btn.setAttribute('aria-label', 'Stop Vigi');
    };
    utter.onend = () => { resetSpeakerButton(btn); vigzoneSpeakingBtn = null; vigzoneUtterance = null; };
    utter.onerror = () => { resetSpeakerButton(btn); vigzoneSpeakingBtn = null; vigzoneUtterance = null; };

    vigzoneUtterance = utter;
    window.speechSynthesis.speak(utter);
  }

  // Builds the action row (feedback + speaker) shared by every assistant
  // message. `getText` is called lazily when the speaker button is clicked,
  // so it always reads the final text even if it changed after the row
  // was created (e.g. a streaming reply still arriving).
  function buildMessageActions(getText, getMeta = null) {
    const row = document.createElement('div');
    row.className = 'msg-feedback';

    const copyBtn = document.createElement('button');
    copyBtn.className = 'message-action-btn copy-response-btn';
    copyBtn.setAttribute('aria-label', 'Copy response');
    copyBtn.title = 'Copy response';
    copyBtn.innerHTML = ICON_COPY;
    copyBtn.addEventListener('click', async (event) => {
      event.preventDefault();
      const text = typeof getText === 'function' ? getText() : String(getText || '');
      if (await copyMessageText(text)) {
        copyBtn.innerHTML = ICON_CHECK;
        window.setTimeout(() => { copyBtn.innerHTML = ICON_COPY; }, 1200);
      }
    });
    row.appendChild(copyBtn);

    const speakerBtn = document.createElement('button');
    speakerBtn.className = 'speaker-btn';
    speakerBtn.setAttribute('aria-label', `Read aloud in ${liveConfig.short_name || liveConfig.app_name || 'Vigzone'}`);
    speakerBtn.innerHTML = ICON_SPEAKER;
    speakerBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const text = typeof getText === 'function' ? getText() : String(getText || '');
      vigzoneSpeak(text, speakerBtn);
    });
    row.appendChild(speakerBtn);

    const upBtn = document.createElement('button');
    upBtn.className = 'message-action-btn feedback-btn feedback-up';
    upBtn.setAttribute('aria-label', 'Like this response');
    upBtn.setAttribute('aria-pressed', 'false');
    upBtn.title = 'Like response';
    upBtn.innerHTML = ICON_THUMBS_UP;
    row.appendChild(upBtn);

    const downBtn = document.createElement('button');
    downBtn.className = 'message-action-btn feedback-btn feedback-down';
    downBtn.setAttribute('aria-label', 'Dislike this response');
    downBtn.setAttribute('aria-pressed', 'false');
    downBtn.title = 'Dislike response';
    downBtn.innerHTML = ICON_THUMBS_DOWN;
    row.appendChild(downBtn);

    async function sendFeedback(rating, reason=''){
      const text = typeof getText === 'function' ? getText() : String(getText || '');
      const rawMeta = typeof getMeta === 'function' ? getMeta() : (getMeta || {});
      const responseMeta = {};
      ['usage_id','model','routed_model','route_reason','routing_mode','fallback_used','retry_count','prompt_tokens','completion_tokens','total_tokens','cached_tokens','latency_ms','time_to_first_token_ms'].forEach(key => {
        if (rawMeta && rawMeta[key] !== undefined && rawMeta[key] !== null) responseMeta[key] = rawMeta[key];
      });
      const liked = rating === 'up';
      upBtn.classList.toggle('done', liked);
      downBtn.classList.toggle('done', !liked);
      upBtn.setAttribute('aria-pressed', String(liked));
      downBtn.setAttribute('aria-pressed', String(!liked));
      try {
        const response = await fetch('/api/feedback', {
          method:'POST',
          credentials:'same-origin',
          headers:suiteAuthHeaders ? suiteAuthHeaders(true) : {'Content-Type':'application/json'},
          body:JSON.stringify({
            rating,
            reason,
            assistant_text:text,
            conversation_id:store?.activeId || null,
            context:{mode:currentMode?.() || 'general', ...responseMeta}
          })
        });
        if (!response.ok) throw new Error('Feedback could not be saved.');
        suiteToast?.(rating === 'up' ? 'Thanks — feedback saved.' : 'Thanks — feedback saved.');
      } catch {
        upBtn.classList.remove('done');
        downBtn.classList.remove('done');
        upBtn.setAttribute('aria-pressed', 'false');
        downBtn.setAttribute('aria-pressed', 'false');
        suiteToast?.('Feedback could not be saved. Please try again.');
      }
    }
    upBtn.addEventListener('click', () => sendFeedback('up'));
    downBtn.addEventListener('click', () => {
      const reason = prompt('What was wrong? (optional)') || '';
      sendFeedback('down', reason);
    });

    return row;
  }

  const SPECIAL_ASSISTANT_OUTPUT_SELECTOR = [
    'pre',
    '.code-block-wrap',
    '.gen-image-wrap',
    '.file-bundle',
    '.voice-msg',
    '[data-file-output]',
    'a[download$=".pdf"]',
    'object[type="application/pdf"]',
    'iframe[src$=".pdf"]'
  ].join(',');

  function syncAssistantOutputPresentation(bubbleEl, forceSpecial = false){
    if (!bubbleEl?.classList?.contains('bubble')) return;
    const isAssistant = bubbleEl.closest('.msg')?.classList.contains('assistant');
    if (!isAssistant) return;
    const hasSpecialOutput = forceSpecial || Boolean(bubbleEl.querySelector(SPECIAL_ASSISTANT_OUTPUT_SELECTOR));
    bubbleEl.classList.toggle('has-special-output', hasSpecialOutput);
  }

  function nextPacedRevealEnd(text, start, targetSize){
    let end = Math.min(text.length, start + Math.max(1, targetSize));
    if (end < text.length) {
      // Prefer ending a frame on a nearby word/punctuation boundary. This
      // feels token-like while avoiding the slow one-character typewriter look.
      const lookAhead = text.slice(end, Math.min(text.length, end + 12));
      const boundary = lookAhead.search(/[\s.,!?;:\)\]\}]/);
      if (boundary >= 0) end += boundary + 1;
    }
    // Never split a UTF-16 surrogate pair (emoji and some multilingual text).
    const finalCode = text.charCodeAt(end - 1);
    if (end < text.length && finalCode >= 0xD800 && finalCode <= 0xDBFF) end += 1;
    return Math.min(text.length, end);
  }

  function createPacedAssistantRenderer(bubbleEl){
    const reduceMotion = Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches);
    let receivedText = '';
    let visibleLength = 0;
    let timer = null;
    let finishing = false;
    let paused = false;
    let cancelled = false;
    let finishResolvers = [];

    function settleFinish(){
      if (!finishing || visibleLength < receivedText.length) return;
      const resolvers = finishResolvers;
      finishResolvers = [];
      resolvers.forEach(resolve => resolve());
    }

    function schedule(delay = 28){
      if (timer || paused || cancelled) return;
      timer = window.setTimeout(renderFrame, document.hidden ? 0 : delay);
    }

    function renderFrame(){
      timer = null;
      if (cancelled || paused) return;
      const backlog = receivedText.length - visibleLength;
      if (backlog <= 0) {
        settleFinish();
        return;
      }

      // While data is arriving, reveal small phrase-sized pieces. Once the
      // network finishes, adaptively catch up so the UI never adds a long wait.
      const targetSize = reduceMotion
        ? backlog
        : finishing
          ? Math.min(72, Math.max(6, Math.ceil(backlog / 24)))
          : Math.min(24, Math.max(3, Math.ceil(backlog / 16)));
      visibleLength = nextPacedRevealEnd(receivedText, visibleLength, targetSize);
      const visibleText = receivedText.slice(0, visibleLength);
      const showCursor = !finishing || visibleLength < receivedText.length;
      bubbleEl.innerHTML = renderContent(visibleText) + (showCursor ? '<span class="stream-cursor"></span>' : '');
      syncAssistantOutputPresentation(bubbleEl);
      scrollLatestIfFollowing();

      if (visibleLength < receivedText.length) schedule(finishing ? 22 : 28);
      else settleFinish();
    }

    return {
      append(chunk){
        if (cancelled || finishing || !chunk) return;
        receivedText += chunk;
        schedule(visibleLength === 0 ? 8 : 28);
      },
      finish(){
        if (cancelled) return Promise.resolve();
        finishing = true;
        paused = false;
        if (visibleLength >= receivedText.length) return Promise.resolve();
        return new Promise(resolve => {
          finishResolvers.push(resolve);
          schedule(0);
        });
      },
      setPaused(value){
        paused = Boolean(value);
        if (paused && timer) {
          window.clearTimeout(timer);
          timer = null;
        } else if (!paused && visibleLength < receivedText.length) {
          schedule(0);
        }
      },
      cancel(){
        cancelled = true;
        if (timer) window.clearTimeout(timer);
        timer = null;
        finishResolvers.splice(0).forEach(resolve => resolve());
      }
    };
  }

  function renderMessage(role, content, opts = {}){
    if (emptyState && emptyState.isConnected) emptyState.remove();
    const msg = document.createElement('div');
    msg.className = `msg ${role}`;
    let avatar = null;
    if (role !== 'user') {
      avatar = document.createElement('div');
      avatar.className = 'avatar';
      avatar.innerHTML = `<img src="${VIGZONE_ICON}" alt="${liveConfig.app_name || 'Vigzone AI'}" width="30" height="30" />`;
    }
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    if (opts.error) bubble.classList.add('error-bubble');

    if (opts.quote) {
      const qRef = document.createElement('div');
      qRef.className = 'quoted-ref';
      const qLabel = opts.quote.role === 'user' ? 'You' : (liveConfig.labels?.assistant || liveConfig.app_name || 'Vigzone AI');
      const qLabelEl = document.createElement('span');
      qLabelEl.className = 'quoted-ref-label';
      qLabelEl.textContent = qLabel;
      const qTextEl = document.createElement('span');
      qTextEl.className = 'quoted-ref-text';
      qTextEl.textContent = opts.quote.text;
      qRef.appendChild(qLabelEl);
      qRef.appendChild(qTextEl);
      bubble.appendChild(qRef);
    }

    if (opts.attachments && opts.attachments.length){
      const row = document.createElement('div');
      row.className = 'bubble-attachments';
      row.innerHTML = opts.attachments.map(a => `
      <div class="pill">${a.kind === 'image' ? ICON_IMAGE : ICON_DOC}<span>${escapeHtml(a.name)}</span></div>
    `).join('');
      bubble.appendChild(row);
    }

    if (opts.typing) {
      const typing = document.createElement('div');
      typing.className = 'typing';
      typing.innerHTML = '<span></span><span></span><span></span>';
      bubble.appendChild(typing);
    } else if (opts.imageLoading) {
      const wrap = document.createElement('div');
      wrap.className = 'gen-image-wrap';
      wrap.innerHTML = `<div class="gen-image-skeleton">Generating image…</div>`;
      if (content) {
        const cap = document.createElement('div');
        cap.className = 'gen-image-caption';
        cap.textContent = content;
        wrap.appendChild(cap);
      }
      bubble.appendChild(wrap);
    } else if (opts.imageSrc) {
      bubble.appendChild(buildImageResultEl(opts.imageSrc, content));
    } else if (content) {
      const textEl = document.createElement('div');
      textEl.innerHTML = renderContent(content);
      enhanceCodeBlocks(textEl);
      bubble.appendChild(textEl);
    }

    // Add feedback + speaker actions (skip placeholders still streaming/loading —
    // those get the row appended once their final text is known)
    if (role === 'assistant' && !opts.typing && !opts.imageLoading && content) {
      bubble.appendChild(buildMessageActions(() => content, () => opts.responseMeta || {}));
    }

    if (typeof opts.index === 'number') {
      msg.dataset.index = opts.index;
    }

    if (avatar) msg.appendChild(avatar);
    msg.appendChild(bubble);
    syncAssistantOutputPresentation(
      bubble,
      Boolean(opts.imageLoading || opts.imageSrc || opts.specialOutput || opts.error)
    );
    chatInner.appendChild(msg);
    scrollToBottom();
    return bubble;
  }

  function renderAll(){
    chatInner.innerHTML = '';
    if (messages.length === 0) {
      restoreEmptyState();
      return;
    }

    // Determine which messages to render based on display limit
    let messagesToRender = messages;
    let startIndex = 0;

    if (!showAllMessages && messages.length > messageDisplayLimit) {
      // Show only the most recent messages
      startIndex = messages.length - messageDisplayLimit;
      messagesToRender = messages.slice(startIndex);

      // Add a placeholder for older messages
      const olderMessagesPlaceholder = document.createElement('div');
      olderMessagesPlaceholder.className = 'msg system';
      olderMessagesPlaceholder.innerHTML = `
        <div class="bubble" style="text-align: center; padding: 20px; opacity: 0.7; font-style: italic;">
          Showing the most recent ${messageDisplayLimit} messages.
          <button id="loadMoreBtn" style="background: var(--surface-2); border: 1px solid var(--border);
                         color: var(--text); border-radius: 8px; padding: 5px 10px;
                         margin-left: 10px; cursor: pointer;">Load older messages</button>
        </div>
      `;
      chatInner.appendChild(olderMessagesPlaceholder);

      // Add event listener to the load more button
      olderMessagesPlaceholder.querySelector('#loadMoreBtn').addEventListener('click', () => {
        showAllMessages = true;
        renderAll();
        // Scroll to bottom after showing more messages
        requestAnimationFrame(() => {
          scrollToBottom();
        });
      });
    }

    messagesToRender.forEach((m, idx) => {
      const text = m.displayText !== undefined ? m.displayText : (typeof m.content === 'string' ? m.content : '');
      if (m.imageSrc) {
        renderMessage(m.role, text, { imageSrc: m.imageSrc, quote: m.quote, responseMeta: m.responseMeta, index: startIndex + idx });
      } else {
        renderMessage(m.role, text, { attachments: m.attachments, quote: m.quote, responseMeta: m.responseMeta, index: startIndex + idx });
      }
    });
  }


  // ---------- Message context menu ----------
  // Desktop: right-click a user/assistant message.
  // Mobile: press and hold without moving. Horizontal swipes are deliberately
  // not treated as replies, which leaves scrolling and touch navigation alone.
  let messageContextMenu = null;
  let messageContextTarget = null;
  let messageContextLongPressTimer = null;
  let messageContextTouchStart = null;
  let suppressNativeMessageMenuUntil = 0;

  function messageContentToPlainText(content){
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) {
      return content.map(part => {
        if (!part) return '';
        if (typeof part === 'string') return part;
        if (part.type === 'text') return part.text || '';
        if (part.text) return part.text;
        return '';
      }).filter(Boolean).join('\n');
    }
    if (content == null) return '';
    try { return JSON.stringify(content, null, 2); } catch { return String(content); }
  }

  function getMessageRecord(msgEl){
    const idx = Number(msgEl?.dataset?.index);
    const m = Number.isFinite(idx) ? messages[idx] : null;
    return {idx, message:m};
  }

  function getMessageBodyText(msgEl){
    const {message:m} = getMessageRecord(msgEl);
    if (m) {
      let text = '';
      if (m.displayText !== undefined && m.displayText !== null && String(m.displayText).trim()) {
        text = String(m.displayText);
      } else {
        text = messageContentToPlainText(m.content);
      }
      if (!text.trim() && m.imageSrc) text = m.content ? String(m.content) : 'Generated image';
      if (!text.trim() && Array.isArray(m.attachments) && m.attachments.length) {
        text = `[Attachment: ${m.attachments.map(a => a.name || a.kind || 'file').join(', ')}]`;
      }
      return text.trim();
    }

    // Fallback for any rendered bubble without stored message data.
    const bubble = msgEl?.querySelector?.('.bubble');
    if (!bubble) return '';
    const clone = bubble.cloneNode(true);
    clone.querySelectorAll('.msg-feedback,.speaker-btn,.feedback-btn,.quoted-ref,.stream-cursor,.typing').forEach(el => el.remove());
    return (clone.innerText || clone.textContent || '').trim();
  }

  function getMessageCopyText(msgEl){
    const {message:m} = getMessageRecord(msgEl);
    const text = getMessageBodyText(msgEl);
    const attach = m && Array.isArray(m.attachments) && m.attachments.length
      ? `\n\n[Attachments: ${m.attachments.map(a => a.name || a.kind || 'file').join(', ')}]`
      : '';
    return (text + attach).trim();
  }

  function getMessageReplyData(msgEl){
    const {idx, message:m} = getMessageRecord(msgEl);
    const fullText = getMessageBodyText(msgEl);
    if (!fullText) return null;
    return {
      role: m?.role === 'user' || msgEl?.classList?.contains('user') ? 'user' : 'assistant',
      fullText,
      index:Number.isFinite(idx) ? idx : null,
    };
  }

  async function copyMessageText(text){
    const value = String(text || '').trim();
    if (!value) {
      suiteToast?.('Nothing to copy in this message.');
      return false;
    }
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
      } else {
        const ta = document.createElement('textarea');
        ta.value = value;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        ta.style.top = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
      }
      suiteToast?.('Message copied.');
      return true;
    } catch {
      suiteToast?.('Could not copy this message.');
      return false;
    }
  }

  function ensureMessageContextMenu(){
    if (messageContextMenu) return messageContextMenu;
    messageContextMenu = document.createElement('div');
    messageContextMenu.className = 'message-context-menu';
    messageContextMenu.setAttribute('role', 'menu');
    messageContextMenu.setAttribute('aria-label', 'Message actions');
    messageContextMenu.innerHTML = `
      <button type="button" role="menuitem" data-message-action="reply">
        ${ICON_REPLY}<span>Reply</span>
      </button>
      <button type="button" role="menuitem" data-message-action="copy">
        ${ICON_COPY}<span>Copy message</span>
      </button>`;
    document.body.appendChild(messageContextMenu);

    messageContextMenu.querySelector('[data-message-action="reply"]').addEventListener('click', () => {
      const reply = getMessageReplyData(messageContextTarget);
      hideMessageContextMenu();
      if (reply) setQuote(reply.role, reply.fullText, reply.index);
    });
    messageContextMenu.querySelector('[data-message-action="copy"]').addEventListener('click', async () => {
      const text = getMessageCopyText(messageContextTarget);
      hideMessageContextMenu();
      await copyMessageText(text);
    });
    messageContextMenu.addEventListener('keydown', (event) => {
      const items = [...messageContextMenu.querySelectorAll('[role="menuitem"]')];
      const current = items.indexOf(document.activeElement);
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const step = event.key === 'ArrowDown' ? 1 : -1;
        items[(current + step + items.length) % items.length]?.focus();
      } else if (event.key === 'Home' || event.key === 'End') {
        event.preventDefault();
        items[event.key === 'Home' ? 0 : items.length - 1]?.focus();
      } else if (event.key === 'Escape' || event.key === 'Tab') {
        hideMessageContextMenu();
      }
    });
    return messageContextMenu;
  }

  function hideMessageContextMenu(){
    if (messageContextMenu) messageContextMenu.classList.remove('visible');
    if (messageContextTarget) messageContextTarget.classList.remove('context-menu-open');
    messageContextTarget = null;
  }

  function showMessageContextMenu(msgEl, clientX, clientY){
    if (!getMessageReplyData(msgEl) && !getMessageCopyText(msgEl)) return;
    const menu = ensureMessageContextMenu();
    messageContextTarget?.classList.remove('context-menu-open');
    messageContextTarget = msgEl;
    messageContextTarget.classList.add('context-menu-open');

    menu.style.left = '0px';
    menu.style.top = '0px';
    menu.classList.add('visible');

    const targetRect = msgEl.querySelector('.bubble')?.getBoundingClientRect() || msgEl.getBoundingClientRect();
    const requestedX = Number.isFinite(clientX) && clientX > 0 ? clientX : targetRect.left + 28;
    const requestedY = Number.isFinite(clientY) && clientY > 0 ? clientY : targetRect.top + 28;
    const rect = menu.getBoundingClientRect();
    const margin = 10;
    const viewport = window.visualViewport;
    const viewportLeft = viewport?.offsetLeft || 0;
    const viewportTop = viewport?.offsetTop || 0;
    const viewportWidth = viewport?.width || window.innerWidth;
    const viewportHeight = viewport?.height || window.innerHeight;
    const maxX = Math.max(viewportLeft + margin, viewportLeft + viewportWidth - rect.width - margin);
    const maxY = Math.max(viewportTop + margin, viewportTop + viewportHeight - rect.height - margin);
    const x = Math.min(Math.max(requestedX, viewportLeft + margin), maxX);
    const y = Math.min(Math.max(requestedY, viewportTop + margin), maxY);
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    requestAnimationFrame(() => menu.querySelector('[role="menuitem"]')?.focus({preventScroll:true}));
  }

  function messageContextTargetFromEvent(e){
    const msg = e.target.closest?.('.msg.user,.msg.assistant');
    if (!msg || !chatInner.contains(msg)) return null;
    if (e.target.closest?.('button,a,input,textarea,select,.code-copy-btn,.msg-feedback')) return null;
    return msg;
  }

  function cancelMessageContextLongPress(){
    clearTimeout(messageContextLongPressTimer);
    messageContextLongPressTimer = null;
    messageContextTouchStart = null;
  }

  chatInner.addEventListener('contextmenu', (e) => {
    const msg = messageContextTargetFromEvent(e);
    if (!msg) return;
    e.preventDefault();
    if (Date.now() < suppressNativeMessageMenuUntil) return;
    showMessageContextMenu(msg, e.clientX, e.clientY);
  });

  chatInner.addEventListener('touchstart', (e) => {
    const msg = messageContextTargetFromEvent(e);
    if (!msg || !e.touches || e.touches.length !== 1) return;
    cancelMessageContextLongPress();
    const t = e.touches[0];
    messageContextTouchStart = {x:t.clientX, y:t.clientY, msg, opened:false};
    messageContextLongPressTimer = window.setTimeout(() => {
      if (!messageContextTouchStart) return;
      messageContextTouchStart.opened = true;
      suppressNativeMessageMenuUntil = Date.now() + 900;
      navigator.vibrate?.(18);
      showMessageContextMenu(
        messageContextTouchStart.msg,
        messageContextTouchStart.x,
        messageContextTouchStart.y
      );
      messageContextLongPressTimer = null;
    }, 520);
  }, {passive:true});

  chatInner.addEventListener('touchmove', (e) => {
    if (!messageContextTouchStart || !e.touches || !e.touches.length) return;
    const t = e.touches[0];
    if (Math.abs(t.clientX - messageContextTouchStart.x) > 12 || Math.abs(t.clientY - messageContextTouchStart.y) > 12) {
      cancelMessageContextLongPress();
    }
  }, {passive:true});

  chatInner.addEventListener('touchend', (e) => {
    if (messageContextTouchStart?.opened) {
      // Prevent the synthetic click that some mobile browsers emit after a
      // long press; otherwise it would immediately close the new menu.
      e.preventDefault();
      e.stopPropagation();
    }
    cancelMessageContextLongPress();
  }, {passive:false});
  chatInner.addEventListener('touchcancel', cancelMessageContextLongPress, {passive:true});

  document.addEventListener('click', (e) => {
    if (messageContextMenu?.classList.contains('visible') && !messageContextMenu.contains(e.target)) {
      hideMessageContextMenu();
    }
  });
  document.addEventListener('scroll', () => {
    cancelMessageContextLongPress();
    hideMessageContextMenu();
  }, true);
  window.addEventListener('resize', hideMessageContextMenu);
  window.visualViewport?.addEventListener('resize', hideMessageContextMenu);
  window.addEventListener('blur', hideMessageContextMenu);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideMessageContextMenu();
  });


  async function checkHealth(){
    try{
      const res = await fetch('/health');
      const data = await res.json();
      if (data.backend_configured) {
        statusDot.className = 'dot online';
        statusText.textContent = 'Online';
        $('#setupBannerSlot').innerHTML = '';
      } else {
        statusDot.className = 'dot offline';
        statusText.textContent = 'Setup needed';
        const msg = data.setup_message || 'AI backend is not configured. Check your deployment environment variables, then redeploy/restart this app.';
        $('#setupBannerSlot').innerHTML = `<div class="setup-banner">⚠ ${escapeHtml(msg)}</div>`;
      }
    }catch(e){
      statusDot.className = 'dot offline';
      statusText.textContent = 'Offline';
    }
  }


  // ---------- Offline Local Knowledge Engine ----------
  // Runs fully in the browser when there is no internet. This is intentionally
  // lightweight: it uses saved conversations, attached document text, simple
  // reasoning/templates, and a built-in mini knowledge base. It does not call
  // Groq or any server endpoint while offline.
  const OFFLINE_KB = [
    {
      keys:['vigzone','app','features','what can you do','help'],
      title:'Vigzone offline capabilities',
      body:`In offline mode I can work from local browser knowledge only:
- read and search your saved chats
- answer from cached/saved conversation memory
- summarize text from files that were already processed before sending
- create simple plans, checklists, study notes, and code/website templates
- do basic arithmetic and explain common programming/study concepts

I cannot use Groq, web search, cloud Brain sync, live admin data, image generation, voice transcription, or new file extraction while offline.`
    },
    {
      keys:['stack','queue','circular queue','linked list','tree','binary search tree','bst','data structure'],
      title:'Data structures quick revision',
      body:`Stack: LIFO structure. Main operations: push, pop, peek. Used in undo, recursion, browser back, expression parsing.
Queue: FIFO structure. Main operations: enqueue, dequeue, front. Used in scheduling, buffers, printer queues.
Circular queue: queue where last position connects back to first. It reuses empty slots efficiently. Full condition is often (rear + 1) % size == front.
Linked list: nodes connected using pointers. Good for dynamic size and insert/delete, but slower random access.
Tree: hierarchical structure with root, parent, child, leaf and depth.
Binary Search Tree: left subtree values are smaller, right subtree values are larger. Average search/insert/delete is O(log n), worst case O(n).`
    },
    {
      keys:['website','html','css','javascript','landing page','hotel','hospital'],
      title:'Offline website starter',
      body:`I can create a clean static website starter offline. Use this structure:
- index.html for content
- style.css for layout and responsive design
- script.js for interactions

A strong website should include: hero section, clear navigation, services/features, gallery or cards, CTA buttons, contact section, responsive CSS, accessibility labels, and SEO-friendly headings.`
    },
    {
      keys:['java','servlet','maven','jsp','login','logout'],
      title:'Java web app checklist',
      body:`For Java/Maven web apps, check:
- pom.xml uses compatible Java and servlet versions
- servlet classes are in the correct package
- web.xml or annotations map URLs correctly
- forms use the correct method/action
- session is created on login and invalidated on logout
- database credentials are not hardcoded
- errors are logged instead of silently swallowed.`
    },
    {
      keys:['admin','dashboard','feedback','users','analytics'],
      title:'Admin dashboard notes',
      body:`A professional admin dashboard should separate admin from normal chat. It should show users, active users, token usage, requests, feedback, bad feedback reasons, shared chats, Brain usage, system status, and graphs. Admin should not be given the normal AI composer if the product requires admin-only management.`
    },
    {
      keys:['black hole','space','gravity'],
      title:'Black hole basics',
      body:`A black hole is a region where gravity is so strong that nothing, not even light, can escape after crossing the event horizon. It forms when a lot of mass is compressed into a very small region. Outside the event horizon, gravity behaves like any other object with the same mass.`
    },
    {
      keys:['sinhala','tamil','label','food label','nutrition','traffic light'],
      title:'Food label design checklist',
      body:`For food labels, keep product name, ingredients, nutrition table, net weight, MRP/MFD/EXP, batch number, manufacturer details, and traffic-light indicators readable. Always verify Sinhala/Tamil text manually because font rendering and spelling can break during image/PDF generation.`
    }
  ];

  const OFFLINE_STOPWORDS = new Set('a an the and or but if then than this that those these is are was were be been being to of in on for from with without by as at it its into about can could should would will just please broo bro me my you your i we our they their do does did done have has had give make create write fix update app ai vigzone'.split(' '));

  function offlineNormalize(text){
    return String(text || '').toLowerCase().replace(/[^\p{L}\p{N}\s.+#-]/gu, ' ').replace(/\s+/g, ' ').trim();
  }
  function offlineTokens(text){
    return offlineNormalize(text).split(' ').filter(w => w.length > 2 && !OFFLINE_STOPWORDS.has(w)).slice(0, 80);
  }
  function offlineEscapeFence(text){
    return String(text || '').replace(/```/g, '`‌``');
  }
  function offlineTextFromContent(content){
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) return content.map(x => x?.text || '').join('\n');
    return '';
  }
  function offlineCalc(query){
    const q = String(query || '').trim();
    if (!/^[\d\s+\-*/().%^]+$/.test(q)) return null;
    if (!/[+\-*/%^]/.test(q)) return null;
    try {
      const tokens = q.match(/\d+(?:\.\d+)?|[()+\-*/%^]/g) || [];
      let cursor = 0;
      const peek = () => tokens[cursor];
      const take = () => tokens[cursor++];
      const primary = () => {
        if (peek() === '(') {
          take();
          const value = expression();
          if (take() !== ')') throw new Error('Mismatched parentheses');
          return value;
        }
        const token = take();
        if (token === '+' || token === '-') {
          const value = primary();
          return token === '-' ? -value : value;
        }
        const value = Number(token);
        if (!Number.isFinite(value)) throw new Error('Invalid number');
        return value;
      };
      const power = () => {
        const left = primary();
        return peek() === '^' ? (take(), Math.pow(left, power())) : left;
      };
      const term = () => {
        let value = power();
        while (['*','/','%'].includes(peek())) {
          const op = take();
          const right = power();
          value = op === '*' ? value * right : op === '/' ? value / right : value % right;
        }
        return value;
      };
      const expression = () => {
        let value = term();
        while (peek() === '+' || peek() === '-') {
          const op = take();
          const right = term();
          value = op === '+' ? value + right : value - right;
        }
        return value;
      };
      const val = expression();
      if (cursor !== tokens.length) throw new Error('Unexpected token');
      if (Number.isFinite(val)) return `Answer: **${val}**`;
    } catch {}
    return null;
  }
  function offlineSummarizeText(text, maxBullets=5){
    const clean = String(text || '').replace(/\s+/g, ' ').trim();
    if (!clean) return '';
    const sentences = clean.match(/[^.!?\n]+[.!?]?/g) || [clean];
    return sentences.slice(0, maxBullets).map(s => `- ${s.trim().slice(0, 220)}`).join('\n');
  }
  function offlineFindLocalMemories(query){
    const qTokens = offlineTokens(query);
    if (!qTokens.length) return [];
    const rows = [];
    Object.values(store?.conversations || {}).forEach(conv => {
      (conv.messages || []).forEach((m, idx) => {
        const text = offlineTextFromContent(m.displayText || m.content);
        if (!text || text.length < 8) return;
        const n = offlineNormalize(text);
        let score = 0;
        qTokens.forEach(t => { if (n.includes(t)) score += 1; });
        if (score > 0) rows.push({score, convTitle: conv.title || 'Saved chat', idx, role: m.role, text: text.slice(0, 420)});
      });
    });
    return rows.sort((a,b) => b.score - a.score).slice(0, 5);
  }
  function offlineMatchKB(query){
    const q = offlineNormalize(query);
    let best = null;
    for (const item of OFFLINE_KB) {
      const score = item.keys.reduce((sum, k) => sum + (q.includes(k) ? Math.max(2, k.split(' ').length) : 0), 0);
      if (score && (!best || score > best.score)) best = {...item, score};
    }
    return best;
  }
  function offlineWebsiteTemplate(query){
    const title = (String(query || '').match(/(?:for|about)\s+([a-zA-Z0-9\s]{3,40})/)?.[1] || 'Your Brand').trim();
    return `Here is an offline static website starter for **${title}**:

\`\`\`html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${offlineEscapeFence(title)}</title>
  <style>
    :root{--bg:#0b1020;--card:#151b2e;--text:#f6f7fb;--muted:#aab1c5;--accent:#ff6b4a}
    *{box-sizing:border-box} body{margin:0;font-family:Inter,system-ui,sans-serif;background:var(--bg);color:var(--text)}
    header{padding:22px 8%;display:flex;justify-content:space-between;align-items:center}
    nav a{color:var(--muted);margin-left:18px;text-decoration:none}
    .hero{padding:80px 8%;display:grid;gap:22px;min-height:72vh;align-content:center;background:radial-gradient(circle at top right,#ff6b4a44,transparent 35%)}
    h1{font-size:clamp(38px,7vw,76px);line-height:.95;margin:0}.hero p{max-width:620px;color:var(--muted);font-size:18px}
    .btn{display:inline-block;background:var(--accent);color:white;padding:13px 18px;border-radius:14px;text-decoration:none;font-weight:800}
    .grid{padding:40px 8%;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
    .card{background:var(--card);border:1px solid #ffffff18;border-radius:18px;padding:22px}
    footer{padding:28px 8%;color:var(--muted);border-top:1px solid #ffffff18}
  </style>
</head>
<body>
  <header><strong>${offlineEscapeFence(title)}</strong><nav><a href="#services">Services</a><a href="#contact">Contact</a></nav></header>
  <section class="hero"><h1>Build something beautiful.</h1><p>A clean responsive landing page generated by Vigzone offline local mode.</p><a class="btn" href="#contact">Get started</a></section>
  <section class="grid" id="services">
    <div class="card"><h2>Fast</h2><p>Simple, lightweight, and responsive.</p></div>
    <div class="card"><h2>Modern</h2><p>Polished spacing, contrast, and mobile layout.</p></div>
    <div class="card"><h2>Ready</h2><p>Edit the text and deploy anywhere.</p></div>
  </section>
  <footer id="contact">Contact: hello@example.com</footer>
</body>
</html>
\`\`\``;
  }
  function buildOfflineLocalReply(query, ctx={}){
    const typed = String(query || '').trim();
    const docs = ctx.docs || [];
    const images = ctx.images || [];
    const shortQ = offlineNormalize(typed);


    const isExplicitDateTimeReq = /^(what|tell|give|show|whats|what's)?.*?\b(date|time|today'?s date|current time)\b/i.test(typed) && typed.split(/\s+/).length <= 10;
    if (isExplicitDateTimeReq) {
      const now = new Date();
      const fmtDate = now.toLocaleDateString(undefined, {weekday:'long', year:'numeric', month:'long', day:'numeric'});
      const fmtTime = now.toLocaleTimeString(undefined, {hour:'2-digit', minute:'2-digit'});
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'local timezone';
      const wantsTime = /\b(time|now)\b|වේලාව|වෙලාව|நேரம்|மணி/i.test(typed);
      const wantsDate = /\b(date|today|calendar)\b|දිනය|අද|தேதி|இன்று/i.test(typed);
      const wantsDay = /\b(day|weekday)\b|දවස|நாள்/i.test(typed);
      if (wantsTime && wantsDate) return `📅 Today is **${fmtDate}**.\n🕒 The current time is **${fmtTime}** (${tz}).`;
      if (wantsTime && !wantsDate) return `🕒 The current time is **${fmtTime}** (${tz}).`;
      if (wantsDay && !wantsDate) return `📅 Today is **${now.toLocaleDateString(undefined, {weekday:'long'})}**. The date is **${fmtDate}**.`;
      return `📅 Today is **${fmtDate}**.`;
    }

    if (images.length && !docs.length) {
      return `**Offline local mode**\n\nI can reply offline, but I cannot analyze new images without the online vision model. I can still help with image-label text, layout suggestions, or continue from saved chat memory.`;
    }

    if (docs.length) {
      const combinedDoc = docs.map(d => `[${d.name}]\n${d.text || ''}`).join('\n\n').slice(0, 12000);
      if (/summari[sz]e|summary|main points|explain|what is/i.test(typed) || !typed) {
        return `**Offline local summary from attached text**\n\n${offlineSummarizeText(combinedDoc, 7)}\n\n_This was generated locally from the text already available in the browser._`;
      }
      const hits = offlineFindLocalMemories(typed);
      return `**Offline local answer**\n\nI can use the attached text that is already available locally. Closest extracted points:\n\n${offlineSummarizeText(combinedDoc, 5)}${hits.length ? `\n\nRelated saved memory:\n${hits.map(h => `- ${h.convTitle}: ${h.text.slice(0, 160)}...`).join('\n')}` : ''}`;
    }

    const calc = offlineCalc(typed);
    if (calc) return `**Offline calculator**\n\n${calc}`;

    if (/website|html|css|landing page|web page|site/i.test(typed) && /create|make|build|write|design/i.test(typed)) {
      return offlineWebsiteTemplate(typed);
    }

    if (/continue|last|where.*stopped|unfinished|task/i.test(typed)) {
      const data = brainBuildData ? brainBuildData() : {tasks:[], summaries:[]};
      const task = data.tasks?.[0];
      if (task) return `**Continue where you stopped**\n\nLast likely unfinished task: **${task.title || task.convTitle || 'Untitled task'}**\n\nSuggested next steps:\n- Open the related saved chat from Vigzone Brain or Recent chats.\n- Review the last generated file or instruction.\n- Tell me the exact next change, and I can help locally if it is text/code/planning.\n\n_Source: local browser Brain memory._`;
    }

    const kb = offlineMatchKB(typed);
    const memories = offlineFindLocalMemories(typed);

    if (kb && memories.length) {
      return `**Offline local answer — ${kb.title}**\n\n${kb.body}\n\n**Relevant saved memories found on this device:**\n${memories.map(h => `- **${escapeHtml(h.convTitle)}**: ${h.text.replace(/\s+/g, ' ').slice(0, 180)}...`).join('\n')}`;
    }
    if (kb) {
      return `**Offline local answer — ${kb.title}**\n\n${kb.body}`;
    }
    if (memories.length) {
      return `**Offline local answer from saved chats**\n\nI found these matching memories stored on this device:\n\n${memories.map(h => `- **${h.convTitle}** (${h.role}): ${h.text.replace(/\s+/g, ' ').slice(0, 220)}...`).join('\n')}\n\nAsk me to summarize or continue one of these, and I’ll use the local saved context.`;
    }

    if (/hi|hello|hey|bro|broo|thanks|thank/i.test(shortQ)) {
      return `Hey bro ✌️ I’m in **offline local mode** now.\n\nI can still help using saved chats, local Brain memory, simple calculations, study notes, code/website templates, and text already available in the browser. For Groq-level AI, web search, image generation, uploads, and cloud sync, reconnect to the internet.`;
    }

    return `**Offline local mode**\n\nI can answer without internet, but only from local browser knowledge. I did not find a strong saved memory for this question.\n\nTry asking about:\n- saved chats or unfinished tasks\n- summaries of text already attached/processed\n- data structures, simple code, website templates, checklists, plans\n- basic calculations\n\nWhen internet returns, I can switch back to full Vigzone AI.`;
  }

  function apiMessages(){
    return messages.map(m => ({ role: m.role, content: m.content }));
  }

  async function sendMessage(text, opts = {}){
    const offlineNow = !navigator.onLine;
    if (imageMode) {
      if (offlineNow) {
        suiteToast?.('Image generation/editing needs internet. Offline local text mode is still available.');
        setOfflineUiState?.();
        return;
      }
      if (quotedMessage) clearQuote();
      return sendImageGenRequest(text);
    }

    const readyFiles = pendingFiles.filter(f => f.status === 'ready');
    const stillUploading = pendingFiles.some(f => f.status === 'uploading');
    if (stillUploading) return; // wait for uploads to finish
    if (!text.trim() && readyFiles.length === 0) return;
    if (streaming) return;

    const images = readyFiles.filter(f => f.kind === 'image');
    const docs = readyFiles.filter(f => f.kind === 'document' || f.kind === 'archive' || f.kind === 'audio_video');
    const typedText = text.trim();

    // Snapshot whatever is currently staged as a quoted reply, then clear the
    // composer's quote bar right away so it can't be sent twice.
    const quoteAtSend = quotedMessage;
    clearQuote();

    let combinedText = typedText;
    if (docs.length) {
      const intro = typedText || (docs.length > 1
              ? "Here are some files — please take a look."
              : "Here's a file — please take a look.");
      const docBlocks = docs.map(d => {
        const note = d.truncated ? '\n(Note: this file was long, so this is a truncated excerpt.)' : '';
        let kindLabel = 'Attached file';
        if (d.kind === 'archive') kindLabel = 'Archive contents';
        else if (d.kind === 'audio_video') kindLabel = 'Audio/Video file info';
        return `\n\n[${kindLabel}: ${d.name}]\n"""\n${d.text}\n"""${note}`;
      }).join('');
      combinedText = intro + docBlocks;
    } else if (!combinedText && images.length) {
      combinedText = images.length > 1 ? "What's in these images?" : "What's in this image?";
    }
    const imageLimitations = images
      .filter(image => image.limitation)
      .map(image => `[Attachment limitation for ${image.name}: ${image.limitation}]`);
    if (imageLimitations.length) {
      combinedText = `${combinedText}\n\n${imageLimitations.join('\n')}`.trim();
    }

    // If the user is replying to a quoted message, give the model that
    // context explicitly so it understands what "this"/"it" refers to.
    if (quoteAtSend) {
      const quoteLabel = quoteAtSend.role === 'user' ? 'their own earlier message' : "your (the assistant's) earlier reply";
      combinedText = `[The user is replying to ${quoteLabel} below — use it as context for what they say next.]\nQuoted message: "${quoteAtSend.fullText}"\n\n${combinedText}`;
    }

    const apiContent = images.length
            ? [
              { type: 'text', text: combinedText },
              ...images.map(img => ({ type: 'image_url', image_url: { url: img.dataUri } })),
            ]
            : combinedText;

    const attachmentsMeta = readyFiles.map(f => ({ kind: f.kind, name: f.name }));
    const quoteMeta = quoteAtSend ? { role: quoteAtSend.role, text: quoteAtSend.fullText } : undefined;

    messages.push({
      role: 'user',
      content: apiContent,
      displayText: typedText,
      attachments: attachmentsMeta.length ? attachmentsMeta : undefined,
      quote: quoteMeta,
    });
    renderMessage('user', typedText, { attachments: attachmentsMeta, quote: quoteMeta, index: messages.length - 1 });
    saveConversation();

    input.value = '';
    autoResize();
    pendingFiles = [];
    renderAttachmentsBar();

    if (offlineNow) {
      const offlineReply = buildOfflineLocalReply(combinedText, { typedText, docs, images, quoteAtSend });
      renderMessage('assistant', offlineReply, { index: messages.length });
      messages.push({ role: 'assistant', content: offlineReply, displayText: offlineReply, offlineLocal: true });
      saveConversation();
      setOfflineUiState?.();
      suiteToast?.('Offline local knowledge response generated on this device.');
      return;
    }

    const assistantBubble = renderMessage('assistant', '', { typing: true, index: messages.length });
    const avatarEl = assistantBubble.parentElement.querySelector('.avatar');
    const priorAssistantText = messages.length >= 2 ? (messages[messages.length - 2].displayText || messages[messages.length - 2].content) : '';
    const requestIsComplex = isComplexRequest(combinedText, typeof priorAssistantText === 'string' ? priorAssistantText : '');
    avatarEl.classList.add(requestIsComplex ? 'thinking-glitch' : 'pulsing');
    const thinkingTagEl = requestIsComplex ? showThinkingTag(avatarEl) : null;
    streaming = true;
    updateSendButtonState();
    startUsageCycleLiveUpdates();

    const pacedReply = createPacedAssistantRenderer(assistantBubble);
    activeStreamRenderer = pacedReply;

    let fullReply = '';
    let responseMeta = {};

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: apiMessages(), ai_mode: currentMode(), workspace_id: activeWorkspaceId || null, conversation_id: store?.activeId || null, client_timezone: (Intl.DateTimeFormat().resolvedOptions().timeZone || null), client_now_iso: new Date().toISOString() })
      });

      if (!res.ok || !res.body) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || errData.error || `Request failed (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6);
          if (raw === '[DONE]') continue;
          if (raw === '[CANCELLED]') {
            console.log('Stream was cancelled by user');
            continue;
          }
          let parsed;
          try { parsed = JSON.parse(raw); } catch { continue; }
          if (parsed.error) throw new Error(parsed.error);
          if (parsed.stream_id) {
            currentStreamId = parsed.stream_id;
            console.log('Stream ID:', currentStreamId);
          }
          if (parsed.meta && typeof parsed.meta === 'object') {
            responseMeta = { ...responseMeta, ...parsed.meta };
          }
          if (parsed.content) {
            fullReply += parsed.content;
            pacedReply.append(parsed.content);
          }
        }
      }

      if (!fullReply) throw new Error('No response received.');
      await pacedReply.finish();
      assistantBubble.innerHTML = renderContent(fullReply); // drop the cursor, final text only
      enhanceCodeBlocks(assistantBubble);
      attachFileBundleIfHeavy(assistantBubble, fullReply, combinedText);
      syncAssistantOutputPresentation(assistantBubble);
      assistantBubble.appendChild(buildMessageActions(() => fullReply, () => responseMeta));
      messages.push({ role: 'assistant', content: fullReply, displayText: fullReply, responseMeta });
      saveConversation();

    } catch (err) {
      pacedReply.cancel();
      if (!navigator.onLine || err?.name === 'TypeError') {
        const offlineReply = buildOfflineLocalReply(combinedText, { typedText, docs, images, quoteAtSend });
        assistantBubble.classList.remove('error-bubble');
        assistantBubble.innerHTML = renderContent(offlineReply);
        enhanceCodeBlocks(assistantBubble);
        syncAssistantOutputPresentation(assistantBubble);
        assistantBubble.appendChild(buildMessageActions(() => offlineReply));
        messages.push({ role: 'assistant', content: offlineReply, displayText: offlineReply, offlineLocal: true });
        saveConversation();
        setOfflineUiState?.();
        suiteToast?.('Connection failed — answered with local offline knowledge.');
      } else {
        assistantBubble.classList.add('error-bubble');
        assistantBubble.innerHTML = `⚠ ${escapeHtml(err.message || 'Something went wrong.')}`;
        syncAssistantOutputPresentation(assistantBubble, true);
      }
    } finally {
      clearAvatarThinkingState(avatarEl, thinkingTagEl);
      streaming = false;
      currentStreamId = null;
      isPaused = false;
      activeStreamRenderer = null;
      updateSendButtonState();
      stopUsageCycleLiveUpdates();
    }
  }

  // ---------- Image generation & editing ----------

  function updateImageModeHint(){
    const slot = $('#imageModeHintSlot');
    if (!imageMode) { slot.innerHTML = ''; return; }
    const hasPhoto = pendingFiles.some(f => f.kind === 'image' && f.status !== 'error');
    slot.innerHTML = hasPhoto
            ? `<div class="mode-hint-banner">✏️ Editing the attached photo — describe the change you want, then send.</div>`
            : `<div class="mode-hint-banner">🎨 High-quality image mode — describe subject, style, colors, layout and exact text. Vigzone will enhance the prompt before generating.</div>`;
  }

  function setImageMode(on){
    imageMode = on;
    imageModeBtn?.classList.toggle('active', imageMode);
    imageModeBtn?.setAttribute('aria-pressed', imageMode ? 'true' : 'false');
    input.placeholder = imageMode
            ? 'Describe the image to generate or edit…'
            : 'Ask anything';
    updateImageModeHint();
  }

  function buildImageResultEl(src, caption){
    const wrap = document.createElement('div');
    wrap.className = 'gen-image-wrap';
    const img = document.createElement('img');
    img.src = src;
    img.alt = caption || 'Generated image';
    img.referrerPolicy = 'no-referrer';
    wrap.appendChild(img);

    const row = document.createElement('div');
    row.className = 'gen-image-actions';

    const dl = document.createElement('a');
    dl.className = 'gen-image-download';
    dl.href = src;
    dl.download = `vigzone-ai-${Date.now()}.png`;
    dl.textContent = '⬇ Download';
    // data: URLs download fine via the `download` attribute; remote URLs
    // (e.g. an OpenAI-hosted url result) will open in a new tab instead,
    // since cross-origin downloads can't be forced from the browser.
    if (!src.startsWith('data:')) {
      dl.target = '_blank';
      dl.rel = 'noopener noreferrer';
      dl.referrerPolicy = 'no-referrer';
    }
    row.appendChild(dl);
    wrap.appendChild(row);

    if (caption) {
      const cap = document.createElement('div');
      cap.className = 'gen-image-caption';
      cap.textContent = caption;
      wrap.appendChild(cap);
    }
    return wrap;
  }

  async function sendImageGenRequest(text){
    const prompt = (text || '').trim();
    if (!prompt) return;
    if (streaming) return;

    const readyImages = pendingFiles.filter(f => f.status === 'ready' && f.kind === 'image');
    const stillUploading = pendingFiles.some(f => f.status === 'uploading');
    if (stillUploading) return; // wait for the photo to finish uploading
    const sourceImage = readyImages[0]; // editing takes one source photo

    const userAttachments = sourceImage ? [{ kind: 'image', name: sourceImage.name }] : undefined;
    messages.push({ role: 'user', content: prompt, displayText: prompt, attachments: userAttachments });
    renderMessage('user', prompt, { attachments: userAttachments });
    saveConversation();

    input.value = '';
    autoResize();
    pendingFiles = [];
    renderAttachmentsBar();

    streaming = true;
    updateSendButtonState();

    const loadingCaption = sourceImage ? `Editing photo accurately: "${prompt}"…` : `Enhancing prompt and generating a high-quality image: "${prompt}"…`;
    const assistantBubble = renderMessage('assistant', loadingCaption, { imageLoading: true });
    const avatarEl = assistantBubble.parentElement.querySelector('.avatar');
    avatarEl.classList.add('pulsing');

    try {
      let res, body;
      if (sourceImage) {
        body = { image_data_uri: sourceImage.dataUri, prompt };
        res = await fetch('/api/edit-image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
      } else {
        res = await fetch('/api/generate-image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt }),
        });
      }

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.error || `Request failed (${res.status})`);

      const src = data.data_uri || data.url;
      if (!src) throw new Error('No image was returned.');

      assistantBubble.innerHTML = '';
      const resultEl = buildImageResultEl(src, prompt);
      if (data.provider || data.model || data.quality_note) {
        const note = document.createElement('div');
        note.className = 'gen-image-caption';
        note.textContent = data.quality_note || `Generated with ${data.provider || 'image provider'}${data.model ? ` · ${data.model}` : ''}`;
        resultEl.appendChild(note);
      }
      assistantBubble.appendChild(resultEl);

      const label = sourceImage ? `[Edited photo: ${prompt}]` : `[Generated image: ${prompt}]`;
      messages.push({ role: 'assistant', content: label, displayText: prompt, imageSrc: src });
      saveConversation();
      syncAssistantOutputPresentation(assistantBubble, true);
      scrollLatestIfFollowing();
    } catch (err) {
      assistantBubble.classList.add('error-bubble');
      assistantBubble.innerHTML = `⚠ ${escapeHtml(err.message || 'Image generation failed.')}`;
    } finally {
      avatarEl.classList.remove('pulsing');
      streaming = false;
      setImageMode(false);
      updateSendButtonState();
    }
  }

  imageModeBtn?.addEventListener('click', () => { setImageMode(!imageMode); modeMenu?.classList.remove('visible'); input?.focus(); });


  async function pauseStream(){
    if (!currentStreamId) return;
    isPaused = !isPaused;
    const endpoint = isPaused ? '/api/pause-stream' : '/api/resume-stream';
    try {
      await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stream_id: currentStreamId })
      });
      updatePauseButtonState();
      activeStreamRenderer?.setPaused(isPaused);
      if (!isPaused) scrollLatestIfFollowing();
    } catch (err) {
      console.error(`Failed to ${isPaused ? 'pause' : 'resume'} stream:`, err);
    }
  }

  pauseBtn.addEventListener('click', pauseStream);


  function updateSendButtonState(){
    const stillUploading = pendingFiles.some(f => f.status === 'uploading');
    sendBtn.disabled = streaming || stillUploading;
    pauseBtn.classList.toggle('active', streaming);
    updatePauseButtonState();
  }

  function updatePauseButtonState() {
    const pauseIcon = pauseBtn.querySelector('.pause-icon');
    const playIcon = pauseBtn.querySelector('.play-icon');
    if (isPaused) {
      pauseIcon.style.display = 'none';
      playIcon.style.display = 'block';
    } else {
      pauseIcon.style.display = 'block';
      playIcon.style.display = 'none';
    }
  }


  function loadUploadedFileHistory(){
    try {
      const rows = JSON.parse(localStorage.getItem(scopedLocalKey('vigzone_uploaded_files_v1')) || '[]');
      return Array.isArray(rows) ? rows : [];
    } catch { return []; }
  }
  function saveUploadedFileHistory(rows){
    try { localStorage.setItem(scopedLocalKey('vigzone_uploaded_files_v1'), JSON.stringify((rows || []).slice(0, 250))); } catch {}
  }
  function rememberUploadedFile(entry){
    if (!entry || entry.status !== 'ready') return;
    const rows = loadUploadedFileHistory();
    const item = {
      id: entry.id || genId(),
      name: entry.name || entry.file?.name || 'file',
      kind: entry.kind || 'document',
      subKind: entry.subKind || '',
      text: entry.text ? String(entry.text).slice(0, 12000) : '',
      mime: entry.mime || entry.file?.type || '',
      limitation: entry.limitation || '',
      scanClean: !!entry.scanClean,
      scannerAvailable: !!entry.scannerAvailable,
      updatedAt: Date.now()
    };
    const next = [item, ...rows.filter(r => r.name !== item.name || r.kind !== item.kind)].slice(0, 250);
    saveUploadedFileHistory(next);
  }

  function renderAttachmentsBar(){
    attachmentsBar.innerHTML = pendingFiles.map(f => {
      let iconHtml;
      if (f.status === 'uploading') {
        iconHtml = '<div class="chip-spinner"></div>';
      } else if (f.kind === 'image' && f.dataUri) {
        iconHtml = `<div class="chip-icon"><img src="${f.dataUri}" alt=""></div>`;
      } else if (f.subKind === 'archive') {
        iconHtml = `<div class="chip-icon">${ICON_ARCHIVE}</div>`;
      } else if (f.subKind === 'av') {
        iconHtml = `<div class="chip-icon">${ICON_AV}</div>`;
      } else {
        iconHtml = `<div class="chip-icon">${ICON_DOC}</div>`;
      }

      // Scan badge
      let scanBadge = '';
      if (f.status === 'ready') {
        if (f.scannerAvailable && f.scanClean) {
          scanBadge = '<span class="scan-badge scan-ok" title="Virus scan passed ✓">🛡️</span>';
        } else if (!f.scannerAvailable) {
          scanBadge = '<span class="scan-badge scan-warn" title="Virus scanner unavailable">⚠️</span>';
        }
      }

      const errorClass = f.status === 'error' ? ' error' : '';
      const title = f.status === 'error'
        ? ` title="${escapeHtml(f.error || 'Upload failed')}"`
        : (f.limitation ? ` title="${escapeHtml(f.limitation)}"` : '');
      return `
      <div class="chip${errorClass}" data-id="${f.id}"${title}>
        ${iconHtml}
        <span class="chip-name">${escapeHtml(f.name)}</span>
        ${scanBadge}
        <button class="chip-remove" data-remove="${f.id}" aria-label="Remove">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
    `;
    }).join('');
    if (pendingFiles.some(f => f.status === 'ready' && f.text)) {
      attachmentsBar.insertAdjacentHTML('beforeend', '<button class="deep-action-btn" id="analyzeFilesBtn" type="button">🧠 Analyze files</button>');
      $('#analyzeFilesBtn')?.addEventListener('click', analyzeReadyFiles);
    }
    updateSendButtonState();
    updateImageModeHint();
  }

  function removeAttachment(id){
    pendingFiles = pendingFiles.filter(f => f.id !== id);
    renderAttachmentsBar();
  }


  // ---------- Google Drive attachment/import ----------
  let drivePickerTokenClient = null;
  let drivePickerAccessToken = '';

  function setDriveStatus(text='', type=''){
    if (!driveImportStatus) return;
    driveImportStatus.textContent = text;
    driveImportStatus.className = 'api-key-status' + (type ? ` ${type}` : '');
  }

  function openDriveImportModal(){
    modeMenu?.classList.remove('visible');
    setDriveStatus('', '');
    if (drivePickerOpenBtn) {
      const enabled = !!(liveConfig.google_drive_api_key && liveConfig.google_drive_client_id);
      drivePickerOpenBtn.disabled = false;
      drivePickerOpenBtn.title = enabled
        ? 'Choose a private Google Drive file'
        : 'Picker needs GOOGLE_DRIVE_CLIENT_ID and GOOGLE_DRIVE_API_KEY. You can still paste a shared Drive link.';
      drivePickerOpenBtn.classList.toggle('disabled', !enabled);
    }
    driveImportModalOverlay?.classList.add('visible');
    setTimeout(() => driveLinkInput?.focus(), 90);
  }

  function closeDriveImportModal(){
    driveImportModalOverlay?.classList.remove('visible');
  }

  function loadExternalScriptOnce(src){
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[src="${src}"]`);
      if (existing) {
        existing.addEventListener('load', resolve, {once:true});
        if (existing.dataset.loaded === 'true') resolve();
        return;
      }
      const s = document.createElement('script');
      s.src = src;
      s.async = true;
      s.defer = true;
      s.onload = () => { s.dataset.loaded = 'true'; resolve(); };
      s.onerror = () => reject(new Error(`Could not load ${src}`));
      document.head.appendChild(s);
    });
  }

  function addDrivePendingEntry(seed={}){
    if (pendingFiles.length >= MAX_ATTACHMENTS) {
      alert(`You can attach up to ${MAX_ATTACHMENTS} files at a time.`);
      return null;
    }
    const entry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      name: seed.name || 'Google Drive file',
      kind: seed.kind || 'document',
      subKind: 'document',
      status: 'uploading',
      drive: true,
    };
    pendingFiles.push(entry);
    renderAttachmentsBar();
    return entry;
  }

  function applyDriveImportResult(entry, data){
    entry.status = 'ready';
    entry.drive = true;
    entry.driveFileId = data.drive_file_id || entry.driveFileId;
    entry.name = data.name || entry.name || 'Google Drive file';
    entry.kind = data.kind || 'document';
    entry.limitation = data.limitation || '';
    entry.scanClean = data.scan_clean !== false;
    entry.scannerAvailable = !!data.scanner_available;

    if (data.kind === 'image' && data.data_uri) {
      entry.dataUri = data.data_uri;
      entry.mime = data.mime;
    } else {
      entry.text = data.text || '';
      entry.truncated = !!data.truncated;
      if (data.kind === 'archive') entry.subKind = 'archive';
      else if (data.kind === 'audio_video') entry.subKind = 'av';
      else entry.subKind = 'document';
    }
    rememberUploadedFile(entry);
    renderAttachmentsBar();
  }

  async function importDriveFileToAttachments(payload, entry=null){
    entry = entry || addDrivePendingEntry({name:payload.name || 'Google Drive file'});
    if (!entry) return;
    try {
      setDriveStatus('Importing Drive file…', '');
      const res = await fetch('/api/drive/import', {
        method:'POST',
        headers:suiteAuthHeaders(true),
        body:JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.error || `Drive import failed (${res.status})`);
      applyDriveImportResult(entry, data);
      setDriveStatus(`Attached: ${data.name || entry.name}`, 'ok');
      suiteToast?.('Google Drive file attached.');
      closeDriveImportModal();
    } catch (err) {
      entry.status = 'error';
      entry.error = err.message || 'Drive import failed';
      setDriveStatus(entry.error, 'error');
      renderAttachmentsBar();
    }
  }

  async function importDriveLink(){
    const url = (driveLinkInput?.value || '').trim();
    if (!url) {
      setDriveStatus('Paste a Google Drive link or file ID first.', 'error');
      return;
    }
    await importDriveFileToAttachments({url});
  }

  async function openGoogleDrivePicker(){
    if (!(liveConfig.google_drive_api_key && liveConfig.google_drive_client_id)) {
      setDriveStatus('Private Drive Picker needs GOOGLE_CLIENT_ID and GOOGLE_API_KEY in Render. Shared Drive links work now without those.', 'error');
      return;
    }
    try {
      setDriveStatus('Opening Google Drive…', '');
      await loadExternalScriptOnce('https://apis.google.com/js/api.js');
      await loadExternalScriptOnce('https://accounts.google.com/gsi/client');

      await new Promise((resolve, reject) => {
        if (!window.gapi) return reject(new Error('Google API script did not load.'));
        window.gapi.load('picker', {callback:resolve, onerror:reject, timeout:8000, ontimeout:() => reject(new Error('Google Picker timed out.'))});
      });

      const openPickerWithToken = (token) => {
        drivePickerAccessToken = token;
        const view = new google.picker.DocsView()
          .setIncludeFolders(false)
          .setSelectFolderEnabled(false);
        const picker = new google.picker.PickerBuilder()
          .setDeveloperKey(liveConfig.google_drive_api_key)
          .setOAuthToken(token)
          .addView(view)
          .enableFeature(google.picker.Feature.NAV_HIDDEN)
          .setCallback((data) => {
            if (data.action !== google.picker.Action.PICKED) return;
            const doc = data.docs && data.docs[0];
            if (!doc) return;
            const entry = addDrivePendingEntry({name:doc.name || 'Google Drive file'});
            importDriveFileToAttachments({
              file_id: doc.id,
              name: doc.name || '',
              mime_type: doc.mimeType || '',
              access_token: drivePickerAccessToken
            }, entry);
          })
          .build();
        picker.setVisible(true);
        setDriveStatus('Choose a file from Google Drive.', 'ok');
      };

      if (!drivePickerTokenClient) {
        drivePickerTokenClient = google.accounts.oauth2.initTokenClient({
          client_id: liveConfig.google_drive_client_id,
          scope: 'https://www.googleapis.com/auth/drive.readonly',
          callback: (tokenResponse) => {
            if (tokenResponse.error) {
              setDriveStatus(tokenResponse.error, 'error');
              return;
            }
            openPickerWithToken(tokenResponse.access_token);
          },
        });
      }
      drivePickerTokenClient.requestAccessToken({prompt: drivePickerAccessToken ? '' : 'consent'});
    } catch (err) {
      setDriveStatus(err.message || 'Could not open Google Drive Picker.', 'error');
    }
  }

  driveImportBtn?.addEventListener('click', openDriveImportModal);
  driveImportCloseBtn?.addEventListener('click', closeDriveImportModal);
  driveImportModalOverlay?.addEventListener('click', (e) => { if (e.target === driveImportModalOverlay) closeDriveImportModal(); });
  driveLinkImportBtn?.addEventListener('click', importDriveLink);
  driveLinkInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') importDriveLink(); });
  drivePickerOpenBtn?.addEventListener('click', openGoogleDrivePicker);


  async function uploadOneFile(entry){
    const formData = new FormData();
    formData.append('file', entry.file);
    try {
      const res = await fetch('/api/upload', { method: 'POST', body: formData });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        // Show the virus scan error clearly
        const detail = data.detail || data.error || `Upload failed (${res.status})`;
        throw new Error(detail);
      }

      entry.status = 'ready';
      entry.kind = data.kind;
      entry.limitation = data.limitation || '';
      entry.scanClean = data.scan_clean !== false;       // true unless explicitly false
      entry.scannerAvailable = !!data.scanner_available;

      if (data.kind === 'image') {
        entry.dataUri = data.data_uri;
        entry.mime = data.mime;
      } else {
        // document / archive / audio_video all carry .text
        entry.text = data.text || '';
        entry.truncated = !!data.truncated;
        // Sub-kind icons
        if (data.kind === 'archive') entry.subKind = 'archive';
        else if (data.kind === 'audio_video') entry.subKind = 'av';
        else entry.subKind = 'document';
      }
    } catch (err) {
      entry.status = 'error';
      entry.error = err.message || 'Upload failed';
    }
    if (entry.status === 'ready') rememberUploadedFile(entry);
    renderAttachmentsBar();
  }

  function handleFiles(fileList){
    const files = Array.from(fileList || []);
    if (!files.length) return;

    const room = MAX_ATTACHMENTS - pendingFiles.length;
    if (room <= 0) {
      alert(`You can attach up to ${MAX_ATTACHMENTS} files at a time.`);
      return;
    }

    files.slice(0, room).forEach(file => {
      if (file.size > MAX_UPLOAD_SIZE_BYTES) {
        pendingFiles.push({
          id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          file, name: file.name, kind: 'document',
          status: 'error', error: `File is larger than ${MAX_UPLOAD_SIZE_MB} MB.`,
        });
        return;
      }
      const entry = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        file,
        name: file.name,
        kind: file.type.startsWith('image/') ? 'image' : (/\.pdf$/i.test(file.name) ? 'document' : 'document'),
        status: 'uploading',
      };
      pendingFiles.push(entry);
      uploadOneFile(entry);
    });

    renderAttachmentsBar();
  }

  attachBtn?.addEventListener('click', () => { modeMenu?.classList.remove('visible'); fileInput.click(); });
  fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
    fileInput.value = '';
  });

  attachmentsBar.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-remove]');
    if (btn) removeAttachment(btn.dataset.remove);
  });

  // Paste a screenshot/image directly into the composer.
  input.addEventListener('paste', (e) => {
    const items = Array.from(e.clipboardData?.items || []);
    const imageItems = items.filter(it => it.type.startsWith('image/'));
    if (!imageItems.length) return;
    e.preventDefault();
    handleFiles(imageItems.map(it => it.getAsFile()).filter(Boolean));
  });

  // Drag and drop files onto the composer.
  ['dragover', 'drop'].forEach(evt => {
    document.querySelector('.composer').addEventListener(evt, (e) => e.preventDefault());
  });
  document.querySelector('.composer').addEventListener('drop', (e) => {
    handleFiles(e.dataTransfer?.files);
  });

  // ===== VOICE / MIC FEATURE =====
  const micBtn = $('#micBtn');
  const micWrapper = $('#micWrapper');
  const micTooltip = $('#micTooltip');
  const liveVoiceBtn = $('#liveVoiceBtn');
  const voiceLangSelect = $('#voiceLangSelect');

  // Speech recognition needs an explicit BCP-47 language up front (it can't
  // detect the spoken language on the fly), and previously this was hardcoded
  // to 'en-US' — meaning voice input silently failed to understand anything
  // else, including Sinhala. Default to the browser/device language instead,
  // and let the small selector next to the mic button override it (saved so
  // the choice sticks across sessions).
  const VOICE_LANG_KEY = 'vigzone_voice_lang';

  function getVoiceInputLang() {
    return navigator.language || 'en-US';
  }

  function getExplicitVoiceInputLang() {
    // No manual selector anymore: Groq Whisper can auto-detect language when
    // no language is sent. Browser SpeechRecognition still uses the device
    // language for the quick local pass, then Groq fallback handles auto-detect.
    return '';
  }

  function detectTextScript(text) {
    const t = text || '';
    if (/[\u0D80-\u0DFF]/.test(t)) return 'si';
    if (/[\u0B80-\u0BFF]/.test(t)) return 'ta';
    if (/[\u0900-\u097F]/.test(t)) return 'hi';
    if (/[A-Za-z]/.test(t)) return 'latin';
    return '';
  }

  function firstWords(text, count = 2) {
    return String(text || '').trim().split(/\s+/).filter(Boolean).slice(0, count).join(' ');
  }

  async function transcribeVoiceBlob(blob, browserHint = '') {
    const form = new FormData();
    const ext = (blob.type || '').includes('ogg') ? 'ogg' : 'webm';
    form.append('file', blob, `voice-message.${ext}`);
    const selectedLang = getExplicitVoiceInputLang();
    if (selectedLang) form.append('language', selectedLang);
    try {
      form.append('browser_language', navigator.language || '');
      form.append('browser_languages', (navigator.languages || []).join(','));
      form.append('browser_hint', browserHint || '');
    } catch {}

    const res = await fetch('/api/transcribe', {
      method: 'POST',
      credentials: 'same-origin',
      body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.detail || data.error || `Voice transcription failed (${res.status})`;
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return (data.text || '').trim();
  }

  if (voiceLangSelect) {
    try {
      voiceLangSelect.value = localStorage.getItem(VOICE_LANG_KEY) || '';
    } catch {}
    voiceLangSelect.addEventListener('change', () => {
      try {
        if (voiceLangSelect.value) localStorage.setItem(VOICE_LANG_KEY, voiceLangSelect.value);
        else localStorage.removeItem(VOICE_LANG_KEY);
      } catch {}
    });
  }

  // Tiny Promise-with-resolve/reject — used to await the next isFinal result
  // from the Web Speech recognizer.
  function createDeferred() {
    let resolve, reject;
    const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
  }

  // Show a small inline error under a voice bubble when transcription fails,
  // so the user knows exactly what went wrong (instead of seeing the misleading
  // "trouble processing your voice message" reply from the chat backend).
  function showVoiceTranscriptionError(voiceMsgEl, message) {
    if (!voiceMsgEl) return;
    const bubble = voiceMsgEl.closest('.bubble');
    if (!bubble) return;
    const note = document.createElement('div');
    note.className = 'voice-error-note';
    note.style.cssText = 'font-size:11px;color:var(--danger);margin-top:6px;font-style:italic;max-width:280px;word-wrap:break-word;';
    note.textContent = message;
    bubble.appendChild(note);
  }

  let micMediaRecorder = null;
  let micAudioChunks = [];
  let micStream = null;
  let micRecordingStart = null;
  let micTooltipTimer = null;
  let micSpeechRecognition = null;
  let micSpeechTranscript = '';
  let micSpeechInterimTranscript = '';
  // Resolves with the next final/interim transcript, or rejects with the
  // recognizer's error code. It is created BEFORE speech recognition starts;
  // creating it after mic release caused false "no-speech" errors because the
  // recognizer often ended before handleRecordingStop() began waiting.
  let micSpeechFinalPromise = null;
  let micSpeechSupported = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  let micSpeechWarned = false;

  function showMicTooltip() {
    micTooltip.classList.add('show');
    clearTimeout(micTooltipTimer);
    micTooltipTimer = setTimeout(() => micTooltip.classList.remove('show'), 2500);
  }

  function hideMicTooltip() {
    clearTimeout(micTooltipTimer);
    micTooltip.classList.remove('show');
  }

  async function startRecording() {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      alert('Microphone permission denied. Please allow microphone access and try again.');
      return;
    }
    if (!micSpeechSupported && !micSpeechWarned) {
      micSpeechWarned = true;
      console.warn('Vigzone AI: this browser has no SpeechRecognition support, so voice messages will be sent without a transcript. Try Chrome or Edge for live transcription.');
    }
    hideMicTooltip();
    micAudioChunks = [];
    micSpeechTranscript = '';
    micSpeechInterimTranscript = '';
    micSpeechFinalPromise = null;
    const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
    micMediaRecorder = new MediaRecorder(micStream, { mimeType });
    micMediaRecorder.ondataavailable = e => { if (e.data.size > 0) micAudioChunks.push(e.data); };
    micMediaRecorder.onstop = handleRecordingStop;
    micMediaRecorder.start();
    micRecordingStart = Date.now();
    micBtn.classList.add('recording');
    micBtn.querySelector('.mic-icon-idle').style.display = 'none';
    micBtn.querySelector('.mic-icon-recording').style.display = '';

    // Live transcription via the browser's built-in speech recognition.
    // (The local chat backend is text-only, so transcription has to
    // happen client-side while the mic is live.)
    if (micSpeechSupported) {
      const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
      micSpeechFinalPromise = createDeferred();
      micSpeechRecognition = new SpeechRecognitionImpl();
      micSpeechRecognition.continuous = true;
      micSpeechRecognition.interimResults = true;
      micSpeechRecognition.lang = getVoiceInputLang();
      micSpeechRecognition.onresult = (event) => {
        let finalText = '';
        let interimText = '';
        let hasFinal = false;
        for (let i = 0; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalText += event.results[i][0].transcript;
            hasFinal = true;
          } else {
            interimText += event.results[i][0].transcript;
          }
        }
        if (interimText.trim()) micSpeechInterimTranscript = interimText.trim();
        if (hasFinal) {
          micSpeechTranscript = finalText.trim();
          if (micSpeechTranscript && micSpeechFinalPromise) {
            micSpeechFinalPromise.resolve(micSpeechTranscript);
            micSpeechFinalPromise = null;
          }
        }
      };
      micSpeechRecognition.onerror = (event) => {
        // Common reasons: 'no-speech' (silence), 'audio-capture' (mic busy),
        // 'not-allowed' (permission), 'network' (Chrome's online recognizer).
        const code = (event && event.error) || 'unknown';
        console.warn('Vigzone AI: speech recognition error:', code);
        // 'aborted' fires in virtually every browser whenever
        // recognition.stop() is called manually -- and stopRecording() does
        // exactly that on every mic release. It does NOT mean transcription
        // failed, it just means we ended the session ourselves. Don't reject
        // here; let onend run its fallback logic (final or interim
        // transcript) instead of surfacing a false "couldn't transcribe"
        // error for perfectly good recordings.
        if (code === 'aborted') return;
        if (micSpeechFinalPromise) {
          micSpeechFinalPromise.reject(new Error(code));
          micSpeechFinalPromise = null;
        }
      };
      micSpeechRecognition.onend = () => {
        // If we stopped without ever firing a final result (e.g. the mic
        // was released before recognition finished finalizing, which is the
        // common case with 'aborted'), fall back to the last interim
        // transcript we captured rather than discarding it.
        if (micSpeechFinalPromise) {
          const fallback = (micSpeechTranscript || micSpeechInterimTranscript || '').trim();
          if (fallback) {
            micSpeechFinalPromise.resolve(fallback);
          } else {
            micSpeechFinalPromise.reject(new Error('no-speech'));
          }
          micSpeechFinalPromise = null;
        }
      };
      try { micSpeechRecognition.start(); } catch (e) {
        console.warn('Vigzone AI: failed to start speech recognition:', e);
        if (micSpeechFinalPromise) {
          micSpeechFinalPromise.reject(e);
          micSpeechFinalPromise = null;
        }
      }
    }
  }

  function stopRecording() {
    if (micMediaRecorder && micMediaRecorder.state !== 'inactive') {
      micMediaRecorder.stop();
    }
    if (micSpeechRecognition) {
      try { micSpeechRecognition.stop(); } catch (e) {}
    }
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
    micBtn.classList.remove('recording');
    micBtn.querySelector('.mic-icon-idle').style.display = '';
    micBtn.querySelector('.mic-icon-recording').style.display = 'none';
  }

  async function handleRecordingStop() {
    const duration = ((Date.now() - micRecordingStart) / 1000).toFixed(1);
    if (micAudioChunks.length === 0 || parseFloat(duration) < 0.5) return;

    const mimeType = micAudioChunks[0].type || 'audio/webm';
    const blob = new Blob(micAudioChunks, { type: mimeType });
    const audioUrl = URL.createObjectURL(blob);

    // Render the voice bubble up front so the user can see the recording
    // was captured even if transcription fails.
    const voiceMsgEl = renderVoiceMessage('user', audioUrl, parseFloat(duration));

    // Speech recognition runs while the mic is live (see startRecording).
    // First try the browser's instant recognizer, then fall back to Groq
    // Whisper on the backend. This fixes the common false "no-speech" issue
    // where the audio bubble is clearly audible but Chrome's recognizer returns
    // nothing.
    let transcription = '';
    let speechErrorCode = null;
    if (micSpeechSupported && micSpeechFinalPromise) {
      try {
        transcription = await Promise.race([
          micSpeechFinalPromise.promise,
          new Promise(resolve => setTimeout(() => resolve('__TIMEOUT__'), 2500))
        ]);
        if (transcription === '__TIMEOUT__') {
          transcription = (micSpeechTranscript || micSpeechInterimTranscript || '').trim();
        }
      } catch (e) {
        speechErrorCode = (e && e.message) || 'unknown';
        transcription = '';
      }
    } else {
      transcription = (micSpeechTranscript || micSpeechInterimTranscript || '').trim();
    }

    // Always ask Groq Whisper too. Browser speech recognition is fast but can
    // mishear Sinhala as Hindi/English. The backend now tries auto-detect first,
    // then only a few language hints, to avoid burning rate limit.
    const browserTranscript = (transcription || '').trim();
    try {
      const groqTranscript = await transcribeVoiceBlob(blob, firstWords(browserTranscript, 2));
      if (groqTranscript) {
        const browserScript = detectTextScript(browserTranscript);
        const groqScript = detectTextScript(groqTranscript);
        if (!browserTranscript || browserScript === 'hi' || groqScript === 'si' || groqScript === 'ta') {
          transcription = groqTranscript;
        } else {
          transcription = groqTranscript || browserTranscript;
        }
        speechErrorCode = null;
      } else {
        transcription = browserTranscript;
      }
    } catch (e) {
      speechErrorCode = (e && e.message) || speechErrorCode || 'unknown';
      // Important fallback: never fail the voice bubble if the browser already
      // heard usable text. This makes very short messages like "hi" work.
      transcription = browserTranscript;
    }

    if (!transcription) {
      const why = speechErrorCode === 'not-allowed'
        ? "Microphone permission was denied. Allow access and try again."
        : speechErrorCode === 'audio-capture'
          ? "Couldn't access the microphone. Check that no other app is using it."
        : (speechErrorCode || '').includes('rate-limit') || (speechErrorCode || '').includes('429')
          ? "Voice transcription is rate-limited right now. Please try again soon."
        : (speechErrorCode || '').includes('Groq') || (speechErrorCode || '').includes('transcrib')
          ? speechErrorCode
        : "I couldn't transcribe that voice message. Please try again, or type your message instead.";
      showVoiceTranscriptionError(voiceMsgEl, why);
      return;
    }

    // We have a real transcript. Push it into the conversation and let the
    // normal chat flow take over from here.
    const userText = transcription;
    messages.push({ role: 'user', content: userText, displayText: userText, isVoice: true });
    saveConversation();

    // Show the transcript under the voice bubble.
    if (voiceMsgEl) {
      const transcriptLabel = document.createElement('div');
      transcriptLabel.className = 'voice-transcript';
      transcriptLabel.textContent = '"' + transcription + '"';
      voiceMsgEl.closest('.bubble').appendChild(transcriptLabel);
    }

    // Show typing indicator
    const assistantBubble = renderMessage('assistant', '', { typing: true, index: messages.length });
    const avatarEl = assistantBubble.parentElement.querySelector('.avatar');
    const requestIsComplex = isComplexRequest(userText);
    avatarEl.classList.add(requestIsComplex ? 'thinking-glitch' : 'pulsing');
    const thinkingTagEl = requestIsComplex ? showThinkingTag(avatarEl) : null;
    let fullReply = '';
    let responseMeta = {};
    const pacedReply = createPacedAssistantRenderer(assistantBubble);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: apiMessages(), ai_mode: currentMode(), workspace_id: activeWorkspaceId || null, conversation_id: store?.activeId || null, client_timezone: (Intl.DateTimeFormat().resolvedOptions().timeZone || null), client_now_iso: new Date().toISOString() })
      });

      if (!response.ok || !response.body) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || errData.error || `Request failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      streaming = true;
      updateSendButtonState();
      startUsageCycleLiveUpdates();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();

        for (const line of parts) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6);
          if (raw === '[DONE]' || raw === '[CANCELLED]') continue;
          let parsed;
          try { parsed = JSON.parse(raw); } catch { continue; }
          if (parsed.error) throw new Error(parsed.error);
          if (parsed.meta && typeof parsed.meta === 'object') responseMeta = { ...responseMeta, ...parsed.meta };
          if (parsed.content) {
            fullReply += parsed.content;
            pacedReply.append(parsed.content);
          }
        }
      }

      if (!fullReply) throw new Error('No response received.');

      await pacedReply.finish();
      assistantBubble.innerHTML = renderContent(fullReply);
      enhanceCodeBlocks(assistantBubble);
      attachFileBundleIfHeavy(assistantBubble, fullReply, userText);
      syncAssistantOutputPresentation(assistantBubble);
      assistantBubble.appendChild(buildMessageActions(() => fullReply, () => responseMeta));
      messages.push({ role: 'assistant', content: fullReply, displayText: fullReply, responseMeta });
      saveConversation();
    } catch (err) {
      pacedReply.cancel();
      assistantBubble.classList.add('error-bubble');
      assistantBubble.innerHTML = `⚠ ${escapeHtml(err.message || 'Something went wrong getting a reply.')}`;
      syncAssistantOutputPresentation(assistantBubble, true);
    }

    clearAvatarThinkingState(avatarEl, thinkingTagEl);
    streaming = false;
    updateSendButtonState();
    stopUsageCycleLiveUpdates();
  }

  // ===== LIVE VOICE MODE (hands-free conversation, like Gemini Live) =====
  let liveVoiceActive = false;
  let liveRecognition = null;
  let liveOverlayEl = null;
  let liveOrbEl = null;
  let liveStatusEl = null;
  let liveCaptionEl = null;
  let liveRecorder = null;
  let liveMicStream = null;
  let liveRecordChunks = [];
  let liveAudioContext = null;
  let liveSilenceTimer = null;
  let liveBrowserRecognition = null;
  let liveBrowserTranscript = '';

  function buildLiveVoiceOverlay() {
    const overlay = document.createElement('div');
    overlay.className = 'live-voice-overlay';
    overlay.innerHTML = `
      <div class="live-voice-orb" id="liveVoiceOrb"></div>
      <div class="live-voice-status" id="liveVoiceStatus">Vigi is listening…</div>
      <div class="live-voice-caption" id="liveVoiceCaption"></div>
      <button class="live-voice-end" id="liveVoiceEndBtn" aria-label="End conversation">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#liveVoiceEndBtn').addEventListener('click', stopLiveVoiceMode);
    return overlay;
  }

  function setLiveVoiceState(state, statusText) {
    if (!liveOrbEl) return;
    liveOrbEl.classList.remove('listening', 'speaking', 'thinking');
    if (state) liveOrbEl.classList.add(state);
    if (statusText !== undefined) liveStatusEl.textContent = statusText;
  }

  function startLiveVoiceMode() {
    if (!micSpeechSupported) {
      alert("Live voice needs speech recognition, which this browser doesn't support. Try Chrome or Edge.");
      return;
    }
    if (liveVoiceActive) return;
    liveVoiceActive = true;
    liveVoiceBtn.classList.add('active');
    vigzoneStopSpeaking(); // don't let a message-bubble read-aloud overlap
    liveOverlayEl = buildLiveVoiceOverlay();
    liveOrbEl = liveOverlayEl.querySelector('#liveVoiceOrb');
    liveStatusEl = liveOverlayEl.querySelector('#liveVoiceStatus');
    liveCaptionEl = liveOverlayEl.querySelector('#liveVoiceCaption');
    requestAnimationFrame(() => liveOverlayEl.classList.add('show'));
    liveListenLoop();
  }

  function stopLiveVoiceMode() {
    liveVoiceActive = false;
    liveVoiceBtn.classList.remove('active');
    if (liveRecognition) {
      try { liveRecognition.onend = null; liveRecognition.onresult = null; liveRecognition.onerror = null; liveRecognition.stop(); } catch (e) {}
      liveRecognition = null;
    }
    if (liveRecorder && liveRecorder.state !== 'inactive') {
      try { liveRecorder.stop(); } catch (e) {}
    }
    liveRecorder = null;
    if (liveBrowserRecognition) {
      try { liveBrowserRecognition.onresult = null; liveBrowserRecognition.onerror = null; liveBrowserRecognition.onend = null; liveBrowserRecognition.stop(); } catch (e) {}
      liveBrowserRecognition = null;
    }
    clearTimeout(liveSilenceTimer);
    liveSilenceTimer = null;
    if (liveMicStream) {
      try { liveMicStream.getTracks().forEach(t => t.stop()); } catch (e) {}
      liveMicStream = null;
    }
    if (liveAudioContext) {
      try { liveAudioContext.close(); } catch (e) {}
      liveAudioContext = null;
    }
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (liveOverlayEl) {
      const el = liveOverlayEl;
      el.classList.remove('show');
      setTimeout(() => el.remove(), 250);
      liveOverlayEl = null;
    }
  }

  // Each "turn" gets its own recognizer instance in non-continuous mode —
  // it auto-stops as soon as the user pauses, which is what naturally
  // segments a hands-free conversation into back-and-forth turns.
  function liveListenLoop() {
    if (!liveVoiceActive) return;

    // Prefer server-side Groq transcription for live voice too. Browser Web
    // Speech needs one fixed language and often hears Sinhala as Hindi. This
    // recorder path captures one turn, sends the audio to /api/transcribe,
    // and the backend tries the first-words/language candidates.
    if (navigator.mediaDevices?.getUserMedia && window.MediaRecorder) {
      liveRecordAndTranscribeTurn();
      return;
    }

    // Fallback for very old browsers.
    liveListenLoopWithBrowserSpeech();
  }

  function startLiveBrowserHint(){
    liveBrowserTranscript = '';
    if (!micSpeechSupported) return;
    try {
      const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recog = new SpeechRecognitionImpl();
      liveBrowserRecognition = recog;
      recog.continuous = true;
      recog.interimResults = true;
      recog.lang = getVoiceInputLang();
      recog.onresult = (event) => {
        let text = '';
        for (let i = 0; i < event.results.length; i++) {
          text += event.results[i][0].transcript + ' ';
        }
        liveBrowserTranscript = text.trim();
        if (liveBrowserTranscript) liveCaptionEl.textContent = liveBrowserTranscript;
      };
      recog.onerror = () => {};
      recog.onend = () => {};
      recog.start();
    } catch (e) {
      liveBrowserRecognition = null;
    }
  }

  async function liveRecordAndTranscribeTurn() {
    if (!liveVoiceActive) return;
    setLiveVoiceState('listening', 'Vigi is listening…');
    liveCaptionEl.textContent = 'Speak now…';

    try {
      liveMicStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      if (!liveVoiceActive) return;
      setLiveVoiceState(null, 'Mic permission needed — tap × and allow microphone');
      return;
    }

    liveRecordChunks = [];
    startLiveBrowserHint();
    const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg';
    try {
      liveRecorder = new MediaRecorder(liveMicStream, { mimeType });
    } catch (e) {
      liveListenLoopWithBrowserSpeech();
      return;
    }

    liveRecorder.ondataavailable = e => { if (e.data && e.data.size > 0) liveRecordChunks.push(e.data); };
    liveRecorder.onstop = async () => {
      const chunks = liveRecordChunks.slice();
      liveRecordChunks = [];
      if (liveMicStream) {
        try { liveMicStream.getTracks().forEach(t => t.stop()); } catch (e) {}
        liveMicStream = null;
      }
      if (liveAudioContext) {
        try { liveAudioContext.close(); } catch (e) {}
        liveAudioContext = null;
      }
      if (liveBrowserRecognition) {
        try { liveBrowserRecognition.stop(); } catch (e) {}
        liveBrowserRecognition = null;
      }
      const browserFallbackText = (liveBrowserTranscript || '').trim();

      if (!liveVoiceActive) return;
      if (!chunks.length) {
        if (browserFallbackText) sendLiveVoiceTurn(browserFallbackText);
        else liveListenLoop();
        return;
      }

      const blob = new Blob(chunks, { type: mimeType });
      if (blob.size < 900) {
        liveListenLoop();
        return;
      }

      setLiveVoiceState('thinking', 'Detecting language…');
      try {
        const text = await transcribeVoiceBlob(blob, firstWords(browserFallbackText, 2));
        const finalText = text || browserFallbackText;
        if (finalText) {
          liveCaptionEl.textContent = finalText;
          sendLiveVoiceTurn(finalText);
        } else {
          liveListenLoop();
        }
      } catch (e) {
        console.warn('Vigzone live voice transcription failed:', e);
        if (browserFallbackText) {
          liveCaptionEl.textContent = browserFallbackText;
          sendLiveVoiceTurn(browserFallbackText);
          return;
        }
        setLiveVoiceState(null, 'Could not transcribe — listening again');
        setTimeout(() => { if (liveVoiceActive) liveListenLoop(); }, 900);
      }
    };

    liveRecorder.start();
    let started = false;
    let lastSpeechAt = Date.now();
    const startedAt = Date.now();
    const maxMs = 12000;
    const minMs = 900;
    const silenceAfterSpeechMs = 1500;
    const noSpeechTimeoutMs = 6000;

    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      liveAudioContext = new AudioCtx();
      const source = liveAudioContext.createMediaStreamSource(liveMicStream);
      const analyser = liveAudioContext.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      const data = new Uint8Array(analyser.fftSize);

      const checkLevel = () => {
        if (!liveVoiceActive || !liveRecorder || liveRecorder.state === 'inactive') return;
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / data.length);
        const now = Date.now();
        if (rms > 0.016) {
          started = true;
          lastSpeechAt = now;
          liveCaptionEl.textContent = 'Listening…';
        }
        const elapsed = now - startedAt;
        const silenceMs = now - lastSpeechAt;
        if ((started && elapsed > minMs && silenceMs > silenceAfterSpeechMs) || elapsed > maxMs || (!started && elapsed > noSpeechTimeoutMs)) {
          try { liveRecorder.stop(); } catch (e) {}
          return;
        }
        liveSilenceTimer = setTimeout(checkLevel, 110);
      };
      checkLevel();
    } catch (e) {
      // If audio-level analysis fails, record a short fixed turn.
      liveSilenceTimer = setTimeout(() => {
        if (liveRecorder && liveRecorder.state !== 'inactive') {
          try { liveRecorder.stop(); } catch (err) {}
        }
      }, 5200);
    }
  }

  function liveListenLoopWithBrowserSpeech() {
    if (!liveVoiceActive) return;
    if (!micSpeechSupported) {
      setLiveVoiceState(null, 'Speech recognition unavailable');
      return;
    }
    const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recog = new SpeechRecognitionImpl();
    liveRecognition = recog;
    recog.continuous = false;
    recog.interimResults = true;
    recog.lang = getVoiceInputLang();
    let finalTranscript = '';

    setLiveVoiceState('listening', 'Vigi is listening…');
    liveCaptionEl.textContent = '';

    recog.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalTranscript += t;
        else interim += t;
      }
      liveCaptionEl.textContent = (finalTranscript + ' ' + interim).trim();
    };

    recog.onerror = (e) => {
      if (!liveVoiceActive) return;
      if (e.error === 'no-speech' || e.error === 'aborted') liveListenLoop();
      else setLiveVoiceState(null, 'Mic error — tap × to exit and try again');
    };

    recog.onend = () => {
      if (!liveVoiceActive) return;
      const text = finalTranscript.trim();
      if (text) sendLiveVoiceTurn(text);
      else liveListenLoop();
    };

    try { recog.start(); } catch (e) {}
  }

  async function sendLiveVoiceTurn(text) {
    setLiveVoiceState('thinking', 'Vigi is thinking…');
    liveCaptionEl.textContent = text;
    startUsageCycleLiveUpdates();

    renderMessage('user', text, { index: messages.length });
    messages.push({ role: 'user', content: text });
    saveConversation();

    const assistantBubble = renderMessage('assistant', '', { typing: true, index: messages.length });
    const avatarEl = assistantBubble.parentElement.querySelector('.avatar');
    const requestIsComplex = isComplexRequest(text);
    avatarEl.classList.add(requestIsComplex ? 'thinking-glitch' : 'pulsing');
    const thinkingTagEl = requestIsComplex ? showThinkingTag(avatarEl) : null;
    let fullReply = '';
    let responseMeta = {};
    const pacedReply = createPacedAssistantRenderer(assistantBubble);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: apiMessages(), ai_mode: currentMode(), workspace_id: activeWorkspaceId || null, conversation_id: store?.activeId || null, client_timezone: (Intl.DateTimeFormat().resolvedOptions().timeZone || null), client_now_iso: new Date().toISOString() })
      });
      if (!response.ok || !response.body) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || errData.error || `Request failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const line of parts) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6);
          if (raw === '[DONE]' || raw === '[CANCELLED]') continue;
          let parsed;
          try { parsed = JSON.parse(raw); } catch { continue; }
          if (parsed.error) throw new Error(parsed.error);
          if (parsed.meta && typeof parsed.meta === 'object') responseMeta = { ...responseMeta, ...parsed.meta };
          if (parsed.content) {
            fullReply += parsed.content;
            pacedReply.append(parsed.content);
          }
        }
      }

      if (!fullReply) throw new Error('No response received.');
      await pacedReply.finish();
      assistantBubble.innerHTML = renderContent(fullReply);
      enhanceCodeBlocks(assistantBubble);
      attachFileBundleIfHeavy(assistantBubble, fullReply, text);
      syncAssistantOutputPresentation(assistantBubble);
      assistantBubble.appendChild(buildMessageActions(() => fullReply, () => responseMeta));
      messages.push({ role: 'assistant', content: fullReply, displayText: fullReply, responseMeta });
      saveConversation();
      clearAvatarThinkingState(avatarEl, thinkingTagEl);
      stopUsageCycleLiveUpdates();

      if (!liveVoiceActive) return; // overlay was closed while waiting
      liveCaptionEl.textContent = truncateText(fullReply, 220);
      speakLiveReply(fullReply);
    } catch (err) {
      pacedReply.cancel();
      clearAvatarThinkingState(avatarEl, thinkingTagEl);
      stopUsageCycleLiveUpdates();
      assistantBubble.classList.add('error-bubble');
      assistantBubble.innerHTML = `⚠ ${escapeHtml(err.message || 'Something went wrong.')}`;
      syncAssistantOutputPresentation(assistantBubble, true);
      if (!liveVoiceActive) return;
      setLiveVoiceState(null, "Couldn't get a reply — listening again");
      setTimeout(() => { if (liveVoiceActive) liveListenLoop(); }, 1200);
    }
  }

  function speakLiveReply(text) {
    if (!('speechSynthesis' in window)) { liveListenLoop(); return; }
    const clean = stripForSpeech(text);
    if (!clean) { liveListenLoop(); return; }

    setLiveVoiceState('speaking', 'Vigi is speaking…');
    const langHint = detectSpeechLang(clean);
    const utter = new SpeechSynthesisUtterance(clean);
    const voice = pickVigzoneVoice(langHint);
    if (voice) utter.voice = voice;
    utter.lang = (voice && voice.lang) || langHint || 'en-US';
    utter.rate = 0.97;
    utter.pitch = 0.85;
    utter.onend = () => { if (liveVoiceActive) liveListenLoop(); };
    utter.onerror = () => { if (liveVoiceActive) liveListenLoop(); };

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }

  liveVoiceBtn.addEventListener('click', () => {
    liveVoiceActive ? stopLiveVoiceMode() : startLiveVoiceMode();
  });

  function renderVoiceMessage(role, audioUrl, durationSec) {
    if (emptyState && emptyState.isConnected) emptyState.remove();
    const msg = document.createElement('div');
    msg.className = `msg ${role}`;
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? 'You' : 'Vigzone AI';
    const bubble = document.createElement('div');
    bubble.className = 'bubble voice-bubble';

    const bars = Array.from({ length: 28 }, () => {
      const h = Math.floor(Math.random() * 18) + 6;
      return `<span style="height:${h}px"></span>`;
    }).join('');

    const fmt = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
    bubble.innerHTML = `
      <div class="voice-msg">
        <button class="voice-play-btn" data-audio="${audioUrl}" data-duration="${durationSec}" aria-label="Play voice message">
          <svg class="play-svg" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          <svg class="pause-svg" viewBox="0 0 24 24" fill="currentColor" style="display:none"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
        </button>
        <div class="voice-waveform">${bars}</div>
        <span class="voice-duration">${fmt(durationSec)}</span>
      </div>`;

    // Attach audio player logic
    const playBtn = bubble.querySelector('.voice-play-btn');
    let audio = null;
    playBtn.addEventListener('click', () => {
      if (!audio) {
        audio = new Audio(audioUrl);
        audio.onended = () => {
          playBtn.querySelector('.play-svg').style.display = '';
          playBtn.querySelector('.pause-svg').style.display = 'none';
        };
      }
      if (audio.paused) {
        audio.play();
        playBtn.querySelector('.play-svg').style.display = 'none';
        playBtn.querySelector('.pause-svg').style.display = '';
      } else {
        audio.pause();
        playBtn.querySelector('.play-svg').style.display = '';
        playBtn.querySelector('.pause-svg').style.display = 'none';
      }
    });

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chatInner.appendChild(msg);
    scrollToBottom();
    return bubble;
  }

  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  // Mic button: tap = show tooltip, tap+hold = record
  let micHoldTimer = null;
  let micHolding = false;

  function micPointerDown(e) {
    e.preventDefault();
    micHolding = false;
    showMicTooltip();
    micHoldTimer = setTimeout(async () => {
      micHolding = true;
      hideMicTooltip();
      await startRecording();
    }, 200);
  }

  function micPointerUp(e) {
    e.preventDefault();
    clearTimeout(micHoldTimer);
    if (micHolding) {
      stopRecording();
      micHolding = false;
    }
  }

  micBtn.addEventListener('pointerdown', micPointerDown);
  micBtn.addEventListener('pointerup', micPointerUp);
  micBtn.addEventListener('pointerleave', micPointerUp);
  micBtn.addEventListener('contextmenu', e => e.preventDefault());

  // ===== END VOICE FEATURE =====

  sendBtn.addEventListener('click', () => sendMessage(input.value));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input.value);
    }
  });

  document.addEventListener('click', (e) => {
    const card = e.target.closest('.suggestion');
    if (card) {
      if (card.dataset.imagePrompt) {
        setImageMode(true);
        input.value = card.dataset.imagePrompt;
      } else {
        input.value = card.dataset.prompt;
      }
      autoResize();
      input.focus();
    }
  });

  newChatBtn?.addEventListener('click', startNewChat);
  newChatBtnSidebar?.addEventListener('click', startNewChat);

  // Keyboard accessibility for history items and suggestions
  function setupKeyboardAccessibility() {
    // Handle history items
    historyList.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const item = e.target.closest('.history-item');
        if (item) {
          item.click();
        }
      }
    });

    // Handle suggestions in empty state
    chatInner.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const suggestion = e.target.closest('.suggestion');
        if (suggestion) {
          suggestion.click();
        }
      }
    });
  }

  // ---------- Offline/PWA mode ----------
  function setOfflineUiState(){
    const offline = !navigator.onLine;
    document.body.classList.toggle('is-offline', offline);
    if (offline) {
      if (statusDot) statusDot.className = 'dot offline';
      if (statusText) statusText.textContent = 'Offline';
    } else {
      checkHealth?.();
      refreshUsageCycle?.();
    }
  }

  async function registerOfflineServiceWorker(){
    if (!('serviceWorker' in navigator)) return;
    try {
      const reg = await navigator.serviceWorker.register('/service-worker.js', { scope: '/' });
      if (reg.waiting) reg.waiting.postMessage({type:'SKIP_WAITING'});
    } catch (e) {
      console.warn('Offline service worker registration failed:', e);
    }
  }

  window.addEventListener('online', () => {
    setOfflineUiState();
    suiteToast?.('Back online. Vigzone can sync and reply now.');
    syncBrainCloud?.();
  });
  window.addEventListener('offline', () => {
    setOfflineUiState();
    suiteToast?.('Offline mode enabled. Saved chats still work.');
  });


  // ---------- Vigzone Product Suite: Brain Pro Sync, Continue, File Studio, Website Studio ----------
  const fileStudioBtn = $('#fileStudioBtn');
  const fileStudioModalOverlay = $('#fileStudioModalOverlay');
  const fileStudioCloseBtn = $('#fileStudioCloseBtn');
  const fileStudioBody = $('#fileStudioBody');
  const fileStudioSearchInput = $('#fileStudioSearchInput');
  const fileStudioRefreshBtn = $('#fileStudioRefreshBtn');

  const websiteStudioBtn = $('#websiteStudioBtn');
  const websiteStudioModalOverlay = $('#websiteStudioModalOverlay');
  const websiteStudioCloseBtn = $('#websiteStudioCloseBtn');
  const websiteStudioPrompt = $('#websiteStudioPrompt');
  const websiteStudioStyle = $('#websiteStudioStyle');
  const websiteStudioGenerateBtn = $('#websiteStudioGenerateBtn');
  const websiteStudioPlanBtn = $('#websiteStudioPlanBtn');
  const websiteStudioExportBtn = $('#websiteStudioExportBtn');

  const brainCloudSyncBtn = $('#brainCloudSyncBtn');
  const versionOpenBtn = $('#versionOpenBtn');
  const versionModalOverlay = $('#versionModalOverlay');
  const versionModalCloseBtn = $('#versionModalCloseBtn');
  const versionModalBody = $('#versionModalBody');

  function suiteAuthHeaders(json=true){
    return {
      ...(json ? {'Content-Type':'application/json'} : {})
    };
  }

  // Compatibility helper used by Workspace/File Studio features.
  // Previously authHeaders() was referenced but never defined.
  function authHeaders(json=false){
    return suiteAuthHeaders(json);
  }

  function suiteToast(text){
    const el = document.createElement('div');
    el.className = 'mode-hint-banner';
    el.textContent = text;
    el.style.position = 'fixed';
    el.style.left = '50%';
    el.style.bottom = '88px';
    el.style.transform = 'translateX(-50%)';
    el.style.zIndex = '260';
    el.style.boxShadow = '0 18px 55px -28px var(--sidebar-shadow)';
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2600);
  }

  let brainCloudVersion = 0;

  function mergeConversationMaps(cloudMap={}, localMap={}){
    const merged = {...cloudMap};
    Object.entries(localMap || {}).forEach(([id, local]) => {
      const remote = merged[id];
      if (!remote || Number(local?.updatedAt || 0) >= Number(remote?.updatedAt || 0)) {
        merged[id] = local;
      }
    });
    return merged;
  }

  function mergeCloudPayload(payload={}){
    store.conversations = mergeConversationMaps(payload.conversations || {}, store.conversations || {});
    store.order = Array.from(new Set([...(store.order || []), ...(payload.order || [])]))
      .filter(id => store.conversations[id])
      .sort((a,b) => Number(store.conversations[b]?.updatedAt || 0) - Number(store.conversations[a]?.updatedAt || 0));
    store.pins = {...(payload.pins || {}), ...(store.pins || {})};
    if (!store.activeId && payload.activeId && store.conversations[payload.activeId]) {
      store.activeId = payload.activeId;
      messages = store.conversations[store.activeId].messages || [];
      renderAll();
    }
    if (payload.brainMeta) {
      const localMeta = loadBrainMeta ? loadBrainMeta() : {};
      saveBrainMeta({...payload.brainMeta, ...localMeta});
    }
    persistStore();
    renderHistoryList();
    refreshBrainIfOpen();
  }

  function productSuitePayload(){
    const data = brainBuildData ? brainBuildData() : { summaries:[], tasks:[], files:[], categories:[] };
    return {
      conversations: store.conversations || {},
      order: store.order || [],
      activeId: store.activeId || null,
      pins: store.pins || {},
      brainMeta: loadBrainMeta ? loadBrainMeta() : {},
      modeMemory: JSON.parse(localStorage.getItem(scopedLocalKey('vigzone_mode_memory_v1')) || '{}'),
      brainStats: {
        chats: data.summaries.length,
        tasks: data.tasks.length,
        files: data.files.length,
        categories: data.categories.map(c => ({id:c.id, name:c.name, count:c.count}))
      }
    };
  }

  async function syncBrainCloud(isRetry=false){
    if (!brainCloudSyncBtn) return;
    brainCloudSyncBtn.textContent = 'Syncing…';
    try {
      const res = await fetch('/api/brain/cloud', {
        method:'POST',
        headers:suiteAuthHeaders(true),
        body:JSON.stringify({
          data: productSuitePayload(),
          client_updated_at:new Date().toISOString(),
          base_version: brainCloudVersion
        })
      });
      const data = await res.json().catch(()=>({}));
      if (res.status === 409 && !isRetry) {
        const current = data.current || {};
        brainCloudVersion = Number(current.version || 0);
        mergeCloudPayload(current.payload || {});
        return syncBrainCloud(true);
      }
      if (!res.ok) throw new Error(data.detail || 'Cloud sync failed');
      brainCloudVersion = Number(data.version || brainCloudVersion);
      brainCloudSyncBtn.textContent = 'Synced ✓';
      suiteToast('Vigzone Brain synced to cloud.');
      setTimeout(() => brainCloudSyncBtn.textContent = 'Cloud Sync', 1500);
    } catch (e) {
      brainCloudSyncBtn.textContent = 'Cloud Sync';
      suiteToast(e.message || 'Could not sync Brain.');
    }
  }

  async function loadBrainCloudOnStart(){
    try {
      const res = await fetch('/api/brain/cloud', {headers:suiteAuthHeaders(false)});
      if (!res.ok) return;
      const cloud = await res.json();
      brainCloudVersion = Number(cloud.version || 0);
      const payload = cloud.payload || {};
      if (!payload.conversations) return;
      const before = Object.keys(store.conversations || {}).length;
      mergeCloudPayload(payload);
      const after = Object.keys(store.conversations || {}).length;
      if (after > before) suiteToast('Cloud Brain restored on this device.');
    } catch {}
  }

  function rememberModeUse(mode, note=''){
    const key = scopedLocalKey('vigzone_mode_memory_v1');
    let mem = {};
    try { mem = JSON.parse(localStorage.getItem(key) || '{}'); } catch {}
    mem[mode] = mem[mode] || {count:0, lastUsed:null, notes:[]};
    mem[mode].count += 1;
    mem[mode].lastUsed = new Date().toISOString();
    if (note && !mem[mode].notes.includes(note)) mem[mode].notes.unshift(note);
    mem[mode].notes = (mem[mode].notes || []).slice(0, 6);
    localStorage.setItem(key, JSON.stringify(mem));
  }

  function renderContinueBanner(){
    if (!emptyState || !emptyState.isConnected) return;
    if (emptyState.querySelector('.continue-work-banner')) return;
    const data = brainBuildData ? brainBuildData() : null;
    if (!data || !data.summaries.length) return;
    const focus = data.tasks[0] || data.summaries[0];
    if (!focus) return;
    const convId = focus.convId || focus.id;
    const title = focus.title || focus.convTitle || 'your last task';
    const banner = document.createElement('div');
    banner.className = 'continue-work-banner';
    banner.innerHTML = `
      <div>
        <strong>Continue where you stopped</strong>
        <span>${escapeHtml(truncateText(title, 120))}</span>
      </div>
      <button class="deep-action-btn" type="button">Continue</button>`;
    banner.querySelector('button').addEventListener('click', () => brainContinueConversation(convId, title));
    const shell = emptyState.querySelector('.empty-shell') || emptyState;
    shell.appendChild(banner);
  }

  function renderFileStudio(){
    if (!fileStudioBody) return;
    const data = brainBuildData ? brainBuildData() : {files:[]};
    const localUploads = loadUploadedFileHistory().map(f => ({
      ...f,
      convTitle: 'Uploaded file history',
      category: {name:'Local files'},
      convId: store.activeId || null,
      fromUploadHistory: true
    }));
    const q = (fileStudioSearchInput?.value || '').toLowerCase().trim();
    const files = [...(data.files || []), ...localUploads]
      .filter((f, index, arr) => arr.findIndex(x => x.name === f.name && x.kind === f.kind) === index)
      .filter(f => !q || [f.name, f.kind, f.convTitle, f.category?.name].join(' ').toLowerCase().includes(q));
    fileStudioBody.innerHTML = files.length ? files.map(f => `
      <div class="suite-card">
        <div class="suite-card-icon">${f.kind === 'image' ? '🖼️' : '📄'}</div>
        <div class="suite-card-main">
          <div class="suite-card-title">${escapeHtml(f.name || 'file')}</div>
          <div class="suite-card-desc">Linked to: ${escapeHtml(f.convTitle || 'chat')}</div>
          <div class="suite-pill-row">
            <span class="brain-pill">${escapeHtml(f.kind || 'file')}</span>
            <span class="brain-pill">${escapeHtml(f.category?.name || 'General')}</span>
            <span class="brain-pill">${brainTimeAgo(f.updatedAt)}</span>
          </div>
          <div class="brain-actions"><button class="brain-mini-btn primary" data-suite-open-chat="${escapeHtml(f.convId)}" type="button">Open chat</button></div>
        </div>
      </div>`).join('') : `<div class="brain-empty">No files or generated images found yet.</div>`;
  }

  function openFileStudio(){
    renderFileStudio();
    fileStudioModalOverlay?.classList.add('visible');
  }
  function closeFileStudio(){ fileStudioModalOverlay?.classList.remove('visible'); }

  function buildWebsiteStudioPrompt(planOnly=false){
    const goal = (websiteStudioPrompt?.value || '').trim();
    const style = websiteStudioStyle?.value || 'modern glass UI';
    return `${planOnly ? 'Create a complete website build plan first, then wait for my approval.' : 'Build a complete production-ready website now.'}

Goal:
${goal || 'Create a modern responsive website.'}

Style:
${style}

Requirements:
- Modern responsive design, mobile-first
- Strong hero section, clean navigation, sections, CTA buttons
- Polished CSS with excellent spacing and visual hierarchy
- Accessibility, SEO basics, semantic HTML
- Return complete runnable HTML/CSS/JS in organized code blocks
- Include a short file tree and explain how to run/export it
- Every local interaction must work; clearly label any external backend/payment integration still required
- Do not invent asset URLs; use sourced images or original inline SVG/CSS illustrations`;
  }


  function extractLatestHtmlFromMessages(){
    const source = [...(messages || [])].reverse().find(m => m.role === 'assistant' && /```html|<!doctype html|<html[\s>]/i.test(exportMessageText(m)));
    if (!source) return '';
    const text = exportMessageText(source);
    const fenced = text.match(/```html\s*([\s\S]*?)```/i) || text.match(/```\s*([\s\S]*?<html[\s\S]*?)```/i);
    if (fenced) return fenced[1].trim();
    const doc = text.match(/<!doctype html[\s\S]*<\/html>/i) || text.match(/<html[\s\S]*<\/html>/i);
    return doc ? doc[0].trim() : '';
  }

  async function exportLatestWebsiteZip(){
    const html = extractLatestHtmlFromMessages();
    if (!html) {
      suiteToast('No HTML website found in the latest assistant replies yet.');
      return;
    }
    try {
      const res = await fetch('/api/website/export', {
        method:'POST',
        headers:suiteAuthHeaders(true),
        body:JSON.stringify({html, filename:'vigzone-website.zip'})
      });
      if (!res.ok) throw new Error((await res.json().catch(()=>({}))).detail || 'Could not export website.');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'vigzone-website.zip';
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 0);
      suiteToast('Website ZIP exported.');
    } catch (e) {
      suiteToast(e.message || 'Website export failed.');
    }
  }

  function openWebsiteStudio(){
    websiteStudioModalOverlay?.classList.add('visible');
    setTimeout(() => websiteStudioPrompt?.focus(), 80);
  }
  function closeWebsiteStudio(){ websiteStudioModalOverlay?.classList.remove('visible'); }

  function generateWebsiteFromStudio(planOnly=false){
    setSmartMode('website');
    rememberModeUse('website', 'Uses Website Studio for modern responsive sites');
    input.value = buildWebsiteStudioPrompt(planOnly);
    autoResize();
    closeWebsiteStudio();
    input.focus();
  }

  async function openVersionModal(){
    versionModalOverlay?.classList.add('visible');
    if (!versionModalBody) return;
    versionModalBody.innerHTML = '<div class="usage-modal-loading">Loading version…</div>';
    try {
      const res = await fetch('/api/app/version');
      const data = await res.json();
      versionModalBody.innerHTML = `
        <div class="suite-card">
          <div class="suite-card-icon">⚡</div>
          <div class="suite-card-main">
            <div class="suite-card-title">${escapeHtml(data.name || 'Vigzone AI')}</div>
            <div class="suite-card-desc">Current version: <strong>${escapeHtml(data.version || 'unknown')}</strong></div>
            <div class="suite-pill-row">${(data.features || []).map(f => `<span class="brain-pill">${escapeHtml(f)}</span>`).join('')}</div>
          </div>
        </div>`;
    } catch {
      versionModalBody.innerHTML = '<div class="brain-empty">Could not load version info.</div>';
    }
  }

  async function shareCurrentChat(){
    if (!messages.length) return suiteToast('No chat to share yet.');
    try {
      const title = store.activeId && store.conversations[store.activeId] ? store.conversations[store.activeId].title : titleFromMessages(messages);
      const res = await fetch('/api/share/chat', {
        method:'POST',
        headers:suiteAuthHeaders(true),
        body:JSON.stringify({title, messages, public:true})
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Share failed');
      const url = new URL(data.url, location.origin).href;
      let copied = false;
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(url);
          copied = true;
        }
      } catch {}
      if (!copied) window.prompt('Copy this public share link:', url);
      const expiry = data.expires_at ? new Date(data.expires_at).toLocaleString() : 'the configured expiry';
      suiteToast(`${copied ? 'Public share link copied' : 'Public share link ready'} · expires ${expiry}.`);
      loadSharedLinks();
    } catch (error) {
      suiteToast(error.message || 'Could not create share link.');
    }
  }

  function attachProductSuiteEvents(){
    fileStudioBtn?.addEventListener('click', openFileStudio);
    fileStudioCloseBtn?.addEventListener('click', closeFileStudio);
    fileStudioModalOverlay?.addEventListener('click', e => { if (e.target === fileStudioModalOverlay) closeFileStudio(); });
    fileStudioSearchInput?.addEventListener('input', renderFileStudio);
    fileStudioRefreshBtn?.addEventListener('click', renderFileStudio);
    fileStudioBody?.addEventListener('click', e => {
      const btn = e.target.closest('[data-suite-open-chat]');
      if (btn) {
        switchConversation(btn.dataset.suiteOpenChat);
        closeFileStudio();
      }
    });

    websiteStudioBtn?.addEventListener('click', openWebsiteStudio);
    websiteStudioCloseBtn?.addEventListener('click', closeWebsiteStudio);
    websiteStudioModalOverlay?.addEventListener('click', e => { if (e.target === websiteStudioModalOverlay) closeWebsiteStudio(); });
    websiteStudioGenerateBtn?.addEventListener('click', () => generateWebsiteFromStudio(false));
    websiteStudioPlanBtn?.addEventListener('click', () => generateWebsiteFromStudio(true));
    websiteStudioExportBtn?.addEventListener('click', exportLatestWebsiteZip);

    brainCloudSyncBtn?.addEventListener('click', () => syncBrainCloud(false));
    versionOpenBtn?.addEventListener('click', openVersionModal);
    versionModalCloseBtn?.addEventListener('click', () => versionModalOverlay?.classList.remove('visible'));
    versionModalOverlay?.addEventListener('click', e => { if (e.target === versionModalOverlay) versionModalOverlay.classList.remove('visible'); });
    $('#shareChatBtn')?.addEventListener('click', shareCurrentChat);

    // Feature Suite: Model Selector, Code Sandbox, Voice TTS
    initModelSelector();
    initCodeSandbox();
    initVoiceTts();
  }

  /* ── 1. Model Selector Controller ────────────────────────────────────────── */
  let activeSelectedModel = localStorage.getItem('vigzone_model') || 'llama-3.3-70b-versatile';
  function getActiveModel(){ return activeSelectedModel; }

  function initModelSelector(){
    const wrap = $('#modelPickerWrap');
    const btn = $('#modelPickerBtn');
    const menu = $('#modelDropdownMenu');
    const nameEl = $('#modelPickerName');
    const badgeEl = $('#modelPickerBadge');
    const iconEl = $('#modelPickerIcon');

    const modelMeta = {
      'llama-3.3-70b-versatile': { name: 'Llama 3.3 70B', badge: 'Powerhouse', icon: '⚡', color: 'linear-gradient(135deg, #3b82f6, #8b5cf6)' },
      'deepseek-r1-distill-llama-70b': { name: 'DeepSeek R1', badge: 'Reasoning', icon: '🧠', color: '#8b5cf6' },
      'llama-3.1-8b-instant': { name: 'Llama 3.1 8B', badge: 'Fast', icon: '🚀', color: '#10b981' },
      'qwen/qwen3.6-27b': { name: 'Qwen 3.6', badge: 'Coding', icon: '💻', color: '#06b6d4' }
    };

    function updateUi(modelId){
      activeSelectedModel = modelId;
      localStorage.setItem('vigzone_model', modelId);
      const meta = modelMeta[modelId] || { name: modelId, badge: 'AI', icon: '⚡', color: '#3b82f6' };
      if (nameEl) nameEl.textContent = meta.name;
      if (badgeEl) {
        badgeEl.textContent = meta.badge;
        badgeEl.style.background = meta.color;
      }
      if (iconEl) iconEl.textContent = meta.icon;
      $$('.model-dropdown-item').forEach(item => {
        item.classList.toggle('active', item.dataset.model === modelId);
      });
    }

    btn?.addEventListener('click', (e) => {
      e.stopPropagation();
      wrap?.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (!wrap?.contains(e.target)) wrap?.classList.remove('open');
    });

    $$('.model-dropdown-item').forEach(item => {
      item.addEventListener('click', () => {
        const m = item.dataset.model;
        if (m) {
          updateUi(m);
          wrap?.classList.remove('open');
          suiteToast?.(`Switched active AI model to ${item.querySelector('.model-item-header')?.textContent || m}`);
        }
      });
    });

    updateUi(activeSelectedModel);
  }

  /* ── 2. Live Code Sandbox Controller ─────────────────────────────────────── */
  function initCodeSandbox(){
    const backdrop = $('#sandboxModalBackdrop');
    const closeBtn = $('#sandboxCloseBtn');
    const refreshBtn = $('#sandboxRefreshBtn');
    const iframe = $('#sandboxIframe');

    closeBtn?.addEventListener('click', () => {
      if (backdrop) backdrop.style.display = 'none';
      if (iframe) iframe.srcdoc = '';
    });
    backdrop?.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        backdrop.style.display = 'none';
        if (iframe) iframe.srcdoc = '';
      }
    });
    refreshBtn?.addEventListener('click', () => {
      if (iframe && iframe.dataset.lastCode) {
        iframe.srcdoc = iframe.dataset.lastCode;
        suiteToast?.('Sandbox preview reloaded.');
      }
    });
  }

  window.openLiveCodeSandbox = function(btn){
    const card = btn.closest('.code-card-wrap');
    if (!card) return;
    const codeEl = card.querySelector('code');
    if (!codeEl) return;
    const rawCode = codeEl.textContent || '';
    const lang = (card.querySelector('pre')?.dataset?.lang || '').toLowerCase();

    let fullDoc = rawCode;
    if (lang === 'svg') {
      fullDoc = `<!DOCTYPE html><html><body style="margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#0f111a;color:#fff;">${rawCode}</body></html>`;
    } else if (lang === 'js' || lang === 'javascript') {
      fullDoc = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{font-family:sans-serif;padding:20px;background:#0f111a;color:#fff;}</style></head><body><div id="output"></div><script>console.log = function(...args){ document.getElementById('output').innerHTML += args.join(' ') + '<br>'; }; try { ${rawCode} } catch(e) { document.getElementById('output').innerHTML += '<span style="color:#ef4444;">Error: ' + e.message + '</span>'; }<\/script></body></html>`;
    } else if (!rawCode.toLowerCase().includes('<!doctype') && !rawCode.toLowerCase().includes('<html')) {
      fullDoc = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{font-family:Inter,system-ui,sans-serif;margin:0;padding:20px;background:#fff;color:#1e293b;}</style></head><body>${rawCode}</body></html>`;
    }

    const backdrop = $('#sandboxModalBackdrop');
    const iframe = $('#sandboxIframe');
    if (backdrop && iframe) {
      iframe.dataset.lastCode = fullDoc;
      iframe.srcdoc = fullDoc;
      backdrop.style.display = 'flex';
      suiteToast?.('Live sandbox preview running.');
    }
  };

  window.copyCodeSnippet = async function(btn){
    const card = btn.closest('.code-card-wrap');
    const code = card?.querySelector('code')?.textContent || '';
    try {
      await navigator.clipboard.writeText(code);
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    } catch {
      btn.textContent = 'Failed';
    }
  };

  /* ── 3. Voice Output (TTS) Controller ────────────────────────────────────── */
  let isVoiceTtsEnabled = localStorage.getItem('vigzone_tts') === 'true';

  function initVoiceTts(){
    const toggleBtn = $('#voiceTopToggle');
    const labelEl = $('#voiceToggleLabel');

    function updateVoiceState(){
      toggleBtn?.classList.toggle('active', isVoiceTtsEnabled);
      if (labelEl) labelEl.textContent = isVoiceTtsEnabled ? 'Voice On' : 'Voice Off';
      localStorage.setItem('vigzone_tts', isVoiceTtsEnabled ? 'true' : 'false');
      if (!isVoiceTtsEnabled && window.speechSynthesis) window.speechSynthesis.cancel();
    }

    toggleBtn?.addEventListener('click', () => {
      isVoiceTtsEnabled = !isVoiceTtsEnabled;
      updateVoiceState();
      suiteToast?.(isVoiceTtsEnabled ? 'Voice response enabled (Text-to-Speech active)' : 'Voice response muted');
    });

    updateVoiceState();
  }

  window.speakAssistantText = function(text, btnEl = null){
    if (!window.speechSynthesis) {
      suiteToast?.('Speech synthesis not supported on this browser.');
      return;
    }
    window.speechSynthesis.cancel();
    if (!text) return;
    const cleanText = text
      .replace(/```[\s\S]*?```/g, ' Code snippet omitted. ')
      .replace(/<think>[\s\S]*?<\/think>/gi, '')
      .replace(/[#*_`~]/g, '')
      .trim();

    if (!cleanText) return;
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    if (btnEl) btnEl.classList.add('speaking');
    utterance.onend = () => { if (btnEl) btnEl.classList.remove('speaking'); };
    utterance.onerror = () => { if (btnEl) btnEl.classList.remove('speaking'); };

    window.speechSynthesis.speak(utterance);
  };

  attachProductSuiteEvents();

  // Setup keyboard accessibility after initial render
  setupKeyboardAccessibility();
  applyChatTheme(getChatTheme(), false);
  registerOfflineServiceWorker();
  setOfflineUiState();
  loadLiveConfig();

  setSidebarCollapsed(isMobile() ? true : (localStorage.getItem(SIDEBAR_KEY) === '1'));
  renderHistoryList();

  renderAll();
  setTimeout(renderContinueBanner, 80);
  loadBrainCloudOnStart();
  checkHealth();
  loadAccount();
  autoResize();
  usageCycleRefreshTimer = setInterval(refreshUsageCycle, 60000);

