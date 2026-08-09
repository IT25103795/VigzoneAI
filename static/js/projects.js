/* Vigzone Projects: browser-approved local folders with metered AI assistance. */
(function () {
  'use strict';

  const modal = document.getElementById('workspaceModalOverlay');
  const body = document.getElementById('workspaceModalBody');
  const sidebarList = document.getElementById('sidebarProjectsList');
  const sidebarAddButton = document.getElementById('sidebarProjectAddBtn');
  const chatBar = document.getElementById('projectChatBar');
  const chatName = document.getElementById('projectChatName');
  const chatStatus = document.getElementById('projectChatStatus');
  const chatNewButton = document.getElementById('projectChatNewBtn');
  const chatSettingsButton = document.getElementById('projectChatSettingsBtn');
  const DB_NAME = 'vigzone-project-folders';
  const DB_STORE = 'folder-handles';
  const MAX_FILES = 500;
  const MAX_DEPTH = 12;
  const MAX_LOCAL_TEXT_BYTES = 1000000;
  const MAX_AI_FILES = 12;
  const MAX_AI_FILE_CHARS = 60000;
  const MAX_AI_TOTAL_CHARS = 110000;
  const ignoredDirectories = new Set([
    '.git', '.hg', '.svn', '.idea', '.vscode', '__pycache__', 'node_modules',
    'venv', '.venv', 'env', '.envdir', 'dist', 'build', 'coverage', '.next',
    '.nuxt', '.cache', 'target', 'vendor'
  ]);
  const exactTextNames = new Set([
    'dockerfile', 'makefile', 'procfile', 'readme', 'license', 'notice',
    '.gitignore', '.dockerignore', '.editorconfig'
  ]);
  const textExtensions = new Set([
    'txt', 'md', 'mdx', 'rst', 'json', 'jsonc', 'yaml', 'yml', 'toml', 'ini',
    'cfg', 'conf', 'xml', 'csv', 'tsv', 'html', 'htm', 'css', 'scss', 'sass',
    'less', 'js', 'jsx', 'mjs', 'cjs', 'ts', 'tsx', 'vue', 'svelte', 'py',
    'pyi', 'java', 'kt', 'kts', 'go', 'rs', 'rb', 'php', 'cs', 'c', 'h',
    'cpp', 'hpp', 'cc', 'swift', 'sh', 'bash', 'zsh', 'fish', 'ps1', 'bat',
    'cmd', 'sql', 'graphql', 'gql', 'proto', 'gradle', 'properties', 'env.example'
  ]);

  const state = {
    projectId: null,
    handle: null,
    folderName: '',
    permission: 'none',
    files: [],
    ignoredCount: 0,
    selectedPaths: new Set(),
    readOnly: false,
    loading: false,
  };

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function notify(message) {
    if (typeof suiteToast === 'function') suiteToast(message);
    else window.alert(message);
  }

  function selectionStorageKey(projectId) {
    const scope = typeof accountStorageScope !== 'undefined' ? accountStorageScope : 'guest';
    return 'vigzone_project_files:' + encodeURIComponent(scope) + ':' + Number(projectId || 0);
  }

  function loadSelectedPaths(projectId) {
    try {
      const parsed = JSON.parse(localStorage.getItem(selectionStorageKey(projectId)) || '[]');
      return new Set(Array.isArray(parsed) ? parsed.filter(function (path) { return !!safeRelativePath(path); }) : []);
    } catch (error) {
      return new Set();
    }
  }

  function saveSelectedPaths() {
    if (!state.projectId) return;
    localStorage.setItem(selectionStorageKey(state.projectId), JSON.stringify(Array.from(state.selectedPaths)));
  }

  function openDb() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) return resolve(null);
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = function () {
        if (!request.result.objectStoreNames.contains(DB_STORE)) {
          request.result.createObjectStore(DB_STORE);
        }
      };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
    });
  }

  async function folderDbGet(projectId) {
    try {
      const db = await openDb();
      if (!db) return null;
      return await new Promise(function (resolve, reject) {
        const tx = db.transaction(DB_STORE, 'readonly');
        const request = tx.objectStore(DB_STORE).get(String(projectId));
        request.onsuccess = function () { resolve(request.result || null); };
        request.onerror = function () { reject(request.error); };
      });
    } catch (error) {
      console.warn('Could not restore local project folder', error);
      return null;
    }
  }

  async function folderDbSet(projectId, handle) {
    try {
      const db = await openDb();
      if (!db) return;
      await new Promise(function (resolve, reject) {
        const tx = db.transaction(DB_STORE, 'readwrite');
        tx.objectStore(DB_STORE).put(handle, String(projectId));
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function () { reject(tx.error); };
      });
    } catch (error) {
      console.warn('This browser could not persist the folder permission', error);
    }
  }

  async function folderDbDelete(projectId) {
    try {
      const db = await openDb();
      if (!db) return;
      await new Promise(function (resolve, reject) {
        const tx = db.transaction(DB_STORE, 'readwrite');
        tx.objectStore(DB_STORE).delete(String(projectId));
        tx.oncomplete = function () { resolve(); };
        tx.onerror = function () { reject(tx.error); };
      });
    } catch (error) {
      console.warn('Could not remove persisted project folder', error);
    }
  }

  function resetFolderState(projectId) {
    state.projectId = Number(projectId) || null;
    state.handle = null;
    state.folderName = '';
    state.permission = 'none';
    state.files = [];
    state.ignoredCount = 0;
    state.selectedPaths = loadSelectedPaths(state.projectId);
    state.readOnly = false;
    state.loading = false;
  }

  function safeRelativePath(value) {
    const path = String(value || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    const parts = path.split('/');
    if (!path || /^[A-Za-z]:/.test(path) || parts.some(function (part) {
      return !part || part === '.' || part === '..';
    })) return '';
    return parts.join('/');
  }

  function isSensitivePath(path) {
    const lower = String(path || '').toLowerCase();
    const name = lower.split('/').pop() || '';
    return name === '.env' || name.indexOf('.env.') === 0 || name.endsWith('.pem') ||
      name.endsWith('.key') || name.endsWith('.p12') || name.endsWith('.pfx') ||
      name === 'id_rsa' || name === 'id_ed25519' || name.indexOf('credentials') >= 0 ||
      name.indexOf('secrets.') >= 0;
  }

  function isTextPath(path) {
    const lower = String(path || '').toLowerCase();
    const name = lower.split('/').pop() || '';
    if (isSensitivePath(lower)) return false;
    if (exactTextNames.has(name) || name.indexOf('readme.') === 0 || name.indexOf('license.') === 0) return true;
    const dot = name.lastIndexOf('.');
    const ext = dot >= 0 ? name.slice(dot + 1) : '';
    return textExtensions.has(ext);
  }

  async function scanDirectory(handle) {
    const files = [];
    let ignoredCount = 0;
    async function walk(directory, prefix, depth) {
      if (depth > MAX_DEPTH || files.length >= MAX_FILES) return;
      for await (const pair of directory.entries()) {
        if (files.length >= MAX_FILES) break;
        const name = pair[0];
        const entry = pair[1];
        const path = prefix ? prefix + '/' + name : name;
        if (entry.kind === 'directory') {
          if (ignoredDirectories.has(name.toLowerCase())) {
            ignoredCount += 1;
            continue;
          }
          await walk(entry, path, depth + 1);
          continue;
        }
        if (!isTextPath(path)) {
          ignoredCount += 1;
          continue;
        }
        try {
          const file = await entry.getFile();
          if (file.size > MAX_LOCAL_TEXT_BYTES) {
            ignoredCount += 1;
            continue;
          }
          files.push({path: safeRelativePath(path), handle: entry, file: null, size: file.size});
        } catch (error) {
          ignoredCount += 1;
        }
      }
    }
    await walk(handle, '', 0);
    files.sort(function (a, b) { return a.path.localeCompare(b.path); });
    return {files: files, ignoredCount: ignoredCount};
  }

  async function readEntry(entry) {
    if (!entry) throw new Error('File not found in the connected folder.');
    const file = entry.file || await entry.handle.getFile();
    if (file.size > MAX_LOCAL_TEXT_BYTES) throw new Error('This text file is too large for the browser editor.');
    return await file.text();
  }

  async function rescanFolder() {
    if (!state.handle) return;
    state.loading = true;
    renderWorkbench();
    try {
      const scanned = await scanDirectory(state.handle);
      state.files = scanned.files;
      state.ignoredCount = scanned.ignoredCount;
      state.permission = 'granted';
      if (!state.selectedPaths.size) {
        rankedContextEntries().forEach(function (item) { state.selectedPaths.add(item.path); });
        saveSelectedPaths();
      }
    } catch (error) {
      state.permission = 'prompt';
      state.files = [];
      notify(error.message || 'Could not scan this folder.');
    } finally {
      state.loading = false;
      renderWorkbench();
      renderChatBar();
    }
  }

  async function restoreFolder(projectId) {
    if (state.projectId !== Number(projectId)) resetFolderState(projectId);
    if (state.handle || state.files.length) {
      renderWorkbench();
      return;
    }
    state.loading = true;
    renderWorkbench();
    const handle = await folderDbGet(projectId);
    state.loading = false;
    if (!handle) {
      renderWorkbench();
      renderChatBar();
      return;
    }
    state.handle = handle;
    state.folderName = handle.name || 'Local folder';
    try {
      state.permission = handle.queryPermission
        ? await handle.queryPermission({mode: 'readwrite'})
        : 'prompt';
    } catch (error) {
      state.permission = 'prompt';
    }
    if (state.permission === 'granted') await rescanFolder();
    else {
      renderWorkbench();
      renderChatBar();
    }
  }

  async function useFallbackFolderPicker() {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.setAttribute('webkitdirectory', '');
    input.addEventListener('change', async function () {
      const picked = Array.from(input.files || []);
      if (!picked.length) return;
      const firstPath = picked[0].webkitRelativePath || picked[0].name;
      state.folderName = firstPath.split('/')[0] || 'Imported folder';
      state.handle = null;
      state.permission = 'read';
      state.readOnly = true;
      state.files = picked.filter(function (file) {
        return file.size <= MAX_LOCAL_TEXT_BYTES && isTextPath(file.webkitRelativePath || file.name);
      }).slice(0, MAX_FILES).map(function (file) {
        const raw = file.webkitRelativePath || file.name;
        const parts = raw.split('/');
        const path = parts.length > 1 ? parts.slice(1).join('/') : raw;
        return {path: safeRelativePath(path), handle: null, file: file, size: file.size};
      }).filter(function (item) { return !!item.path; });
      state.files.sort(function (a, b) { return a.path.localeCompare(b.path); });
      rankedContextEntries().forEach(function (item) { state.selectedPaths.add(item.path); });
      saveSelectedPaths();
      renderWorkbench();
      renderChatBar();
    }, {once: true});
    input.click();
  }

  async function connectFolder() {
    if (!state.projectId) return;
    if (state.handle && state.handle.requestPermission) {
      try {
        const permission = await state.handle.requestPermission({mode: 'readwrite'});
        if (permission === 'granted') {
          state.permission = permission;
          state.readOnly = false;
          await rescanFolder();
          return;
        }
      } catch (error) {
        console.warn('Existing folder permission could not be renewed', error);
      }
    }
    if (!window.showDirectoryPicker) {
      await useFallbackFolderPicker();
      return;
    }
    try {
      const handle = await window.showDirectoryPicker({mode: 'readwrite'});
      state.handle = handle;
      state.folderName = handle.name || 'Local folder';
      state.permission = 'granted';
      state.readOnly = false;
      await folderDbSet(state.projectId, handle);
      await rescanFolder();
    } catch (error) {
      if (error && error.name !== 'AbortError') notify('Folder access was not granted.');
    }
  }

  async function disconnectFolder() {
    if (!state.projectId) return;
    await folderDbDelete(state.projectId);
    localStorage.removeItem(selectionStorageKey(state.projectId));
    resetFolderState(state.projectId);
    renderWorkbench();
    renderChatBar();
  }

  function activeProject() {
    return (workspaces || []).find(function (item) {
      return Number(item.id) === Number(state.projectId || activeWorkspaceId);
    }) || null;
  }

  function updateProjectIndicator() {
    if (typeof updateWorkspacePill === 'function') updateWorkspacePill();
  }

  function currentProjectConversation() {
    const conversation = window.VigzoneChatBridge?.currentConversation?.();
    return conversation && Number(conversation.projectId) ? conversation : null;
  }

  function renderSidebarProjects() {
    if (!sidebarList) return;
    const activeId = Number(currentProjectConversation()?.projectId || 0);
    const activeConversationId = currentProjectConversation()?.id || '';
    if (!workspaces.length) {
      sidebarList.innerHTML = '<div class="history-empty">No projects yet. Use + to create one.</div>';
      return;
    }
    sidebarList.innerHTML = workspaces.map(function (project) {
      const active = Number(project.id) === activeId ? ' active' : '';
      const subtitle = project.shared ? 'Shared TEAM project' : (project.description || 'Private project');
      const conversations = Number(project.id) === activeId
        ? (window.VigzoneChatBridge?.listProjectConversations?.(project.id) || [])
        : [];
      const threads = conversations.length ? '<div class="sidebar-project-threads">' + conversations.map(function (conversation) {
        const selected = conversation.id === activeConversationId ? ' active' : '';
        return '<button class="sidebar-project-thread' + selected + '" data-project-conversation-id="' + esc(conversation.id) +
          '" type="button"><span>↳</span><strong>' + esc(conversation.projectThreadTitle || 'New conversation') + '</strong></button>';
      }).join('') + '<button class="sidebar-project-thread new" data-new-project-conversation="' + Number(project.id) +
        '" type="button"><span>＋</span><strong>Start new conversation</strong></button></div>' : '';
      return '<div class="sidebar-project-group"><button class="sidebar-project-item' + active + '" data-sidebar-project-id="' + Number(project.id) +
        '" type="button" aria-label="Open ' + esc(project.name) + '">' +
        '<span class="sidebar-project-folder" aria-hidden="true">⌘</span>' +
        '<span class="sidebar-project-copy"><strong>' + esc(project.name) + '</strong><small>' +
        esc(subtitle) + '</small></span><span class="sidebar-project-chevron" aria-hidden="true">›</span></button>' + threads + '</div>';
    }).join('');
    sidebarList.querySelectorAll('[data-sidebar-project-id]').forEach(function (button) {
      button.addEventListener('click', function () {
        openProjectChat(Number(button.getAttribute('data-sidebar-project-id')), false);
      });
    });
    sidebarList.querySelectorAll('[data-project-conversation-id]').forEach(function (button) {
      button.addEventListener('click', function () {
        window.VigzoneChatBridge?.switchConversation?.(button.getAttribute('data-project-conversation-id'));
      });
    });
    sidebarList.querySelectorAll('[data-new-project-conversation]').forEach(function (button) {
      button.addEventListener('click', function () {
        openProjectChat(Number(button.getAttribute('data-new-project-conversation')), true);
      });
    });
  }

  function renderChatBar() {
    if (!chatBar) return;
    const conversation = currentProjectConversation();
    const project = conversation
      ? workspaces.find(function (item) { return Number(item.id) === Number(conversation.projectId); })
      : null;
    const visible = !!project;
    chatBar.hidden = !visible;
    document.body.classList.toggle('project-chat-active', visible);
    renderSidebarProjects();
    if (!visible) return;
    if (chatName) chatName.textContent = project.name;
    if (!chatStatus) return;
    if (state.projectId !== Number(project.id)) {
      chatStatus.textContent = 'Loading the approved local folder…';
      return;
    }
    if (state.loading) chatStatus.textContent = 'Scanning local text and code files…';
    else if (state.files.length) {
      const chosen = rankedContextEntries().length;
      chatStatus.textContent = state.files.length + ' files connected · ' + chosen + ' in AI context · edits require approval';
    } else if (state.handle) chatStatus.textContent = 'Folder permission required — open Files & settings';
    else chatStatus.textContent = 'No folder connected — open Files & settings';
  }

  async function openProjectChat(projectId, forceNew) {
    const project = workspaces.find(function (item) { return Number(item.id) === Number(projectId); });
    if (!project) return;
    window.VigzoneChatBridge?.openProjectConversation?.(project, !!forceNew);
    if (state.projectId !== Number(project.id)) resetFolderState(project.id);
    renderChatBar();
    renderSidebarProjects();
    await restoreFolder(project.id);
    renderChatBar();
    modal?.classList.remove('visible');
  }

  async function openProjectSettings(projectId) {
    if (projectId && state.projectId !== Number(projectId)) resetFolderState(Number(projectId));
    await open();
  }

  async function loadProjects() {
    const response = await fetch('/api/projects', {credentials: 'same-origin'});
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(data.detail || 'Could not load projects.');
    workspaces = Array.isArray(data.projects) ? data.projects : (data.workspaces || []);
    if (activeWorkspaceId && !workspaces.some(function (item) {
      return Number(item.id) === Number(activeWorkspaceId);
    })) {
      activeWorkspaceId = null;
      localStorage.removeItem('vigzone_active_workspace_id');
      resetFolderState(null);
    }
    updateProjectIndicator();
    renderSidebarProjects();
    renderChatBar();
  }

  async function selectProject(projectId) {
    resetFolderState(Number(projectId));
    renderProjects();
    await restoreFolder(state.projectId);
    await loadNotes(state.projectId);
  }

  async function createProject() {
    const nameInput = document.getElementById('projectNameInput');
    const descriptionInput = document.getElementById('projectDescriptionInput');
    const sharedInput = document.getElementById('projectSharedInput');
    const name = nameInput ? nameInput.value.trim() : '';
    if (name.length < 2) return notify('Enter a project name first.');
    const response = await fetch('/api/projects', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        name: name,
        description: descriptionInput ? descriptionInput.value.trim() : '',
        mode: 'general',
        shared: !!(sharedInput && sharedInput.checked)
      })
    });
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) return notify(data.detail || 'Could not create project.');
    await loadProjects();
    await selectProject(data.workspace.id);
  }

  async function saveProjectDetails() {
    const project = activeProject();
    if (!project) return;
    const name = (document.getElementById('projectEditName') || {}).value || '';
    const description = (document.getElementById('projectEditDescription') || {}).value || '';
    const response = await fetch('/api/projects/' + Number(project.id), {
      method: 'PATCH',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: name.trim(), description: description.trim()})
    });
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) return notify(data.detail || 'Could not update project.');
    await loadProjects();
    const updated = workspaces.find(function (item) { return Number(item.id) === Number(project.id); });
    if (updated) window.VigzoneChatBridge?.renameProjectConversations?.(updated.id, updated.name);
    renderProjects();
    renderChatBar();
    notify('Project details saved.');
  }

  async function deleteProject() {
    const project = activeProject();
    if (!project || !window.confirm('Delete the project record named "' + project.name + '"? Local files will not be deleted.')) return;
    const response = await fetch('/api/projects/' + Number(project.id), {
      method: 'DELETE',
      credentials: 'same-origin'
    });
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) return notify(data.detail || 'Could not delete project.');
    await folderDbDelete(project.id);
    localStorage.removeItem(selectionStorageKey(project.id));
    window.VigzoneChatBridge?.removeProjectConversations?.(project.id);
    resetFolderState(null);
    await loadProjects();
    renderProjects();
    notify('Project record deleted. Your local folder was untouched.');
  }

  async function loadNotes(projectId) {
    const target = document.getElementById('projectNotesList');
    if (!target || Number(projectId) !== Number(state.projectId)) return;
    const response = await fetch('/api/projects/' + Number(projectId) + '/notes', {credentials: 'same-origin'});
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      target.innerHTML = '<div class="usage-modal-empty">' + esc(data.detail || 'Could not load project notes.') + '</div>';
      return;
    }
    const notes = Array.isArray(data.notes) ? data.notes : [];
    target.innerHTML = notes.length ? notes.map(function (note) {
      return '<div class="workspace-note-row"><strong>' + esc(note.title || 'Note') +
        '</strong><span>' + esc(note.content || '') + '</span></div>';
    }).join('') : '<div class="usage-modal-note">No project notes yet.</div>';
  }

  async function addNote() {
    const project = activeProject();
    if (!project) return;
    const title = (document.getElementById('projectNoteTitle') || {}).value || 'Note';
    const content = (document.getElementById('projectNoteContent') || {}).value || '';
    if (content.trim().length < 2) return notify('Add some project context first.');
    const response = await fetch('/api/projects/' + Number(project.id) + '/notes', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title: title.trim() || 'Note', content: content.trim(), kind: 'note'})
    });
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) return notify(data.detail || 'Could not add the project note.');
    const titleInput = document.getElementById('projectNoteTitle');
    const contentInput = document.getElementById('projectNoteContent');
    if (titleInput) titleInput.value = '';
    if (contentInput) contentInput.value = '';
    await loadNotes(project.id);
  }

  async function fileHandleForPath(path, create) {
    if (!state.handle) throw new Error('Reconnect the folder with read/write access first.');
    const parts = safeRelativePath(path).split('/');
    if (!parts[0]) throw new Error('Unsafe project path.');
    let directory = state.handle;
    for (let index = 0; index < parts.length - 1; index += 1) {
      directory = await directory.getDirectoryHandle(parts[index], {create: !!create});
    }
    return await directory.getFileHandle(parts[parts.length - 1], {create: !!create});
  }

  async function writeFile(path, content) {
    const handle = await fileHandleForPath(path, true);
    const writer = await handle.createWritable();
    try {
      await writer.write(content);
      await writer.close();
    } catch (error) {
      try { await writer.abort(); } catch (abortError) {}
      throw error;
    }
  }

  function rankedContextEntries() {
    let entries = state.files.filter(function (item) { return state.selectedPaths.has(item.path); });
    if (!entries.length) {
      const important = /(^|\/)(readme|package\.json|pyproject\.toml|requirements.*\.txt|dockerfile|main\.|app\.|index\.|src\/)/i;
      entries = state.files.slice().sort(function (a, b) {
        return Number(important.test(b.path)) - Number(important.test(a.path));
      }).slice(0, MAX_AI_FILES);
    }
    return entries.slice(0, MAX_AI_FILES);
  }

  async function collectAiFiles() {
    const entries = rankedContextEntries();
    const files = [];
    let total = 0;
    for (const entry of entries) {
      let content = await readEntry(entry);
      content = content.slice(0, MAX_AI_FILE_CHARS);
      if (total + content.length > MAX_AI_TOTAL_CHARS) {
        content = content.slice(0, Math.max(0, MAX_AI_TOTAL_CHARS - total));
      }
      if (!content && total >= MAX_AI_TOTAL_CHARS) break;
      files.push({path: entry.path, content: content});
      total += content.length;
      if (total >= MAX_AI_TOTAL_CHARS) break;
    }
    return files;
  }

  function projectActionForInstruction(instruction) {
    return /\b(fix|edit|change|implement|add|remove|delete|rename|refactor|rewrite|update|create|build|complete|finish|repair|replace|improve|optimi[sz]e|simplify|migrate|convert|adjust|modify|resolve|make)\b/i.test(instruction || '')
      ? 'edit'
      : 'analyze';
  }

  function projectError(message, code) {
    const error = new Error(message);
    error.code = code;
    return error;
  }

  async function assist(options) {
    const projectId = Number(options?.projectId || 0);
    if (!navigator.onLine) throw projectError('Project AI needs an internet connection. Your local folder remains on this device.', 'OFFLINE');
    if (!projectId) throw projectError('Open a project conversation first.', 'PROJECT_REQUIRED');
    if (!workspaces.length) await loadProjects();
    const project = workspaces.find(function (item) { return Number(item.id) === projectId; });
    if (!project) throw projectError('This project no longer exists.', 'PROJECT_MISSING');
    if (state.projectId !== projectId) resetFolderState(projectId);
    if (!state.files.length) await restoreFolder(projectId);
    if (!state.files.length) {
      throw projectError('Connect or re-authorize the local folder from Files & settings before asking Vigzone to work on it.', 'FOLDER_REQUIRED');
    }
    const files = await collectAiFiles();
    if (!files.length) throw projectError('Select at least one readable project file in Files & settings.', 'FILES_REQUIRED');
    const instruction = String(options?.instruction || '').slice(0, 12000);
    const action = projectActionForInstruction(instruction);
    const history = Array.isArray(options?.history) ? options.history.slice(-12).map(function (message) {
      return {
        role: message.role === 'assistant' ? 'assistant' : 'user',
        content: String(message.content || '').slice(0, 8000)
      };
    }).filter(function (message) { return message.content.trim(); }) : [];
    const response = await fetch('/api/projects/assist', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        project_id: projectId,
        action: action,
        instruction: instruction,
        model: options?.model || (typeof getActiveModel === 'function' ? getActiveModel() : 'openai/gpt-oss-20b'),
        conversation_id: String(options?.conversationId || '').slice(0, 120) || null,
        history: history,
        tree: state.files.map(function (item) { return item.path; }),
        files: files
      })
    });
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      const error = projectError(data.detail || 'Project AI action failed.', response.status === 429 ? 'QUOTA' : 'REQUEST_FAILED');
      error.status = response.status;
      throw error;
    }
    return {
      projectId: projectId,
      action: action,
      summary: data.summary || 'Project review complete.',
      changes: Array.isArray(data.changes) ? data.changes : [],
      meta: data.meta || {},
      applied: false
    };
  }

  async function applyMessageChanges(result, messageIndex, root) {
    const projectId = Number(result?.projectId || 0);
    if (!projectId || !Array.isArray(result?.changes) || !result.changes.length) return;
    if (state.projectId !== projectId) resetFolderState(projectId);
    if (!state.handle) await restoreFolder(projectId);
    if (state.handle && state.permission !== 'granted' && state.handle.requestPermission) {
      try {
        state.permission = await state.handle.requestPermission({mode: 'readwrite'});
      } catch (error) {
        state.permission = 'prompt';
      }
    }
    if (!state.handle || state.permission !== 'granted' || state.readOnly) {
      notify('Open Files & settings and grant read/write access to this project folder first.');
      return;
    }
    const selectedIndexes = Array.from(root.querySelectorAll('[data-project-chat-change]:checked')).map(function (input) {
      return Number(input.getAttribute('data-project-chat-change'));
    });
    const selected = selectedIndexes.map(function (index) { return result.changes[index]; }).filter(Boolean);
    if (!selected.length) return notify('Select at least one proposed file change.');
    if (!window.confirm('Write ' + selected.length + ' reviewed change(s) to your local project folder?')) return;
    try {
      for (const change of selected) {
        const path = safeRelativePath(change.path);
        if (!path) throw new Error('Vigzone proposed an unsafe file path.');
        await writeFile(path, String(change.content == null ? '' : change.content));
      }
      result.applied = true;
      result.appliedPaths = selected.map(function (change) { return change.path; });
      if (Number.isInteger(messageIndex) && typeof messages !== 'undefined' && messages[messageIndex]?.projectResult) {
        messages[messageIndex].projectResult = result;
        if (typeof saveConversation === 'function') saveConversation();
      }
      const button = root.querySelector('.project-chat-apply');
      if (button) {
        button.disabled = true;
        button.textContent = 'Changes applied';
      }
      await rescanFolder();
      notify('Reviewed changes were saved to your local project folder.');
    } catch (error) {
      notify(error.message || 'Could not apply the proposed changes.');
    }
  }

  function renderMessageResult(bubble, result, messageIndex) {
    if (!bubble || !result || bubble.querySelector('.project-chat-result')) return;
    const changes = Array.isArray(result.changes) ? result.changes : [];
    const root = document.createElement('section');
    root.className = 'project-chat-result';
    if (!changes.length) {
      root.innerHTML = '<div class="project-chat-result-head">Project files reviewed <span>No file edits proposed</span></div>';
      bubble.appendChild(root);
      return;
    }
    root.innerHTML = '<div class="project-chat-result-head">Proposed file changes <span>' + changes.length +
      ' file' + (changes.length === 1 ? '' : 's') + ' · review before saving</span></div>' +
      '<div class="project-chat-change-list">' + changes.map(function (change, index) {
        return '<label class="project-chat-change"><input type="checkbox" data-project-chat-change="' + index + '" checked' +
          (result.applied ? ' disabled' : '') + '><span class="project-chat-change-copy"><strong>' + esc(change.path) +
          '</strong><small>' + esc(change.reason || 'AI-proposed change') +
          '</small><details><summary>Review full replacement</summary><pre>' + esc(change.content || '') +
          '</pre></details></span></label>';
      }).join('') + '</div><div class="project-chat-result-actions"><button class="project-chat-apply" type="button"' +
      (result.applied ? ' disabled' : '') + '>' + (result.applied ? 'Changes applied' : 'Apply selected changes') + '</button></div>';
    root.querySelector('.project-chat-apply')?.addEventListener('click', function () {
      applyMessageChanges(result, Number(messageIndex), root);
    });
    bubble.appendChild(root);
  }

  function handleChatError(error) {
    if (error?.code === 'FOLDER_REQUIRED' || error?.code === 'FILES_REQUIRED') {
      renderChatBar();
      notify('Use Files & settings to connect the project folder, then send the message again.');
    }
  }

  function renderWorkbench() {
    const target = document.getElementById('projectWorkbench');
    const project = activeProject();
    if (!target || !project || Number(project.id) !== Number(state.projectId)) return;
    if (state.projectId !== Number(project.id)) {
      target.innerHTML = '<div class="usage-modal-loading">Loading local folder…</div>';
      restoreFolder(project.id);
      return;
    }
    if (state.loading) {
      target.innerHTML = '<div class="usage-modal-loading">Scanning local text and code files…</div>';
      return;
    }
    if (!state.files.length) {
      const permissionCopy = state.handle && state.permission !== 'granted'
        ? 'Your saved folder needs permission again. Browsers require a user click before restoring read/write access.'
        : 'Choose the folder for this project. Vigzone cannot browse any other folder, and the folder handle stays on this device.';
      target.innerHTML = '<div class="project-connect-card"><div class="project-connect-icon">📁</div>' +
        '<div><strong>' + esc(state.folderName || 'Connect a local project folder') + '</strong><p>' +
        esc(permissionCopy) + '</p></div><button class="deep-action-btn project-primary" id="projectConnectFolderBtn" type="button">' +
        (state.handle ? 'Grant folder permission' : 'Choose folder') + '</button>' +
        '<div class="project-privacy-note">Secret key files, .env files, dependency folders, binaries, and oversized files are excluded automatically.</div></div>';
      document.getElementById('projectConnectFolderBtn').addEventListener('click', connectFolder);
      return;
    }

    const rows = state.files.map(function (entry) {
      const checked = state.selectedPaths.has(entry.path) ? ' checked' : '';
      return '<label class="project-file-row"><input type="checkbox" data-project-select-file="' +
        esc(entry.path) + '"' + checked + ' aria-label="Include ' + esc(entry.path) + ' in AI context">' +
        '<span class="project-setting-file"><span>' + esc(entry.path) + '</span><small>' +
        Math.max(1, Math.ceil(entry.size / 1024)) + ' KB</small></span></label>';
    }).join('');
    target.innerHTML = '<div class="project-folder-settings"><div class="project-folder-toolbar"><div><strong>📁 ' + esc(state.folderName) +
      '</strong><small>' + state.files.length + ' text/code files · ' + state.ignoredCount +
      ' ignored safely' + (state.readOnly ? ' · read-only browser import' : '') +
      '</small></div><div><button class="deep-action-btn" id="projectRescanBtn" type="button"' +
      (state.handle ? '' : ' disabled') + '>Rescan</button><button class="deep-action-btn" id="projectDisconnectBtn" type="button">Disconnect</button></div></div>' +
      '<div><div class="project-pane-label">Files available to this project chat</div><p class="project-privacy-note">' +
      'Choose the most relevant files. Vigzone sends their text only when you message this project. Secret files, dependencies, binaries, and oversized files stay excluded.</p></div>' +
      '<div class="project-folder-file-list">' + rows + '</div></div>';

    target.querySelectorAll('[data-project-select-file]').forEach(function (checkbox) {
      checkbox.addEventListener('change', function () {
        const path = checkbox.getAttribute('data-project-select-file');
        if (checkbox.checked) state.selectedPaths.add(path);
        else state.selectedPaths.delete(path);
        saveSelectedPaths();
        renderChatBar();
      });
    });
    document.getElementById('projectRescanBtn')?.addEventListener('click', rescanFolder);
    document.getElementById('projectDisconnectBtn')?.addEventListener('click', disconnectFolder);
  }

  function renderProjects() {
    if (!body) return;
    const project = activeProject();
    const canShare = !!(window._vigzoneEntitlements && window._vigzoneEntitlements.features &&
      window._vigzoneEntitlements.features.team_workspace);
    const cards = (workspaces || []).length ? workspaces.map(function (item) {
      const active = Number(item.id) === Number(state.projectId) ? ' active' : '';
      return '<button class="workspace-card' + active + '" data-project-id="' + Number(item.id) +
        '" type="button"><span class="workspace-card-title">' + esc(item.name) +
        (item.shared ? ' <span class="team-chip">Shared TEAM</span>' : '') +
        '</span><span class="workspace-card-sub">' + esc(item.description || 'No description') +
        '</span></button>';
    }).join('') : '<div class="usage-modal-empty">No projects yet. Create your first one below.</div>';
    const details = project ? '<section class="project-details-card"><div class="project-section-head"><div><span class="project-eyebrow">Active project</span><h4>' +
      esc(project.name) + '</h4></div><button class="deep-action-btn project-danger" id="projectDeleteBtn" type="button">Delete project</button></div>' +
      '<div class="project-details-grid"><input id="projectEditName" maxlength="80" value="' + esc(project.name) +
      '" aria-label="Project name"><input id="projectEditDescription" maxlength="600" value="' +
      esc(project.description || '') + '" placeholder="Project goal or description" aria-label="Project description">' +
      '<button class="deep-action-btn" id="projectSaveDetailsBtn" type="button">Save details</button></div>' +
      '<div class="project-open-chat-actions"><button class="deep-action-btn" id="projectNewConversationBtn" type="button">New conversation</button>' +
      '<button class="deep-action-btn project-primary" id="projectOpenChatBtn" type="button">Open project chat →</button></div>' +
      '<div id="projectWorkbench"></div><details class="project-context-panel"><summary>Project context notes</summary>' +
      '<div id="projectNotesList"><div class="usage-modal-loading">Loading notes…</div></div>' +
      '<input id="projectNoteTitle" maxlength="120" placeholder="Context title"><textarea id="projectNoteContent" maxlength="5000" placeholder="Save requirements, decisions, or instructions used in project chats…"></textarea>' +
      '<button class="deep-action-btn" id="projectAddNoteBtn" type="button">Add context note</button></details></section>'
      : '<section class="project-empty-state"><div>🗂️</div><h4>Select or create a project</h4><p>Each project can remember cloud context and reconnect to one explicitly approved folder on this computer.</p></section>';
    body.innerHTML = '<div class="projects-shell"><aside class="projects-rail"><div class="project-pane-label">Your projects</div>' +
      '<div class="workspace-list">' + cards + '</div><div class="workspace-form project-create-form">' +
      '<input id="projectNameInput" maxlength="80" placeholder="Project name">' +
      '<textarea id="projectDescriptionInput" maxlength="600" placeholder="Goal or short description"></textarea>' +
      (canShare ? '<label class="team-checkbox"><input id="projectSharedInput" type="checkbox"> Share project context with TEAM members</label>' : '') +
      '<button class="deep-action-btn project-primary" id="projectCreateBtn" type="button">+ Create project</button></div></aside>' +
      '<main class="projects-main">' + details + '</main></div>';

    body.querySelectorAll('[data-project-id]').forEach(function (button) {
      button.addEventListener('click', function () { selectProject(button.getAttribute('data-project-id')); });
    });
    document.getElementById('projectCreateBtn')?.addEventListener('click', createProject);
    document.getElementById('projectSaveDetailsBtn')?.addEventListener('click', saveProjectDetails);
    document.getElementById('projectDeleteBtn')?.addEventListener('click', deleteProject);
    document.getElementById('projectAddNoteBtn')?.addEventListener('click', addNote);
    document.getElementById('projectOpenChatBtn')?.addEventListener('click', function () { openProjectChat(project.id, false); });
    document.getElementById('projectNewConversationBtn')?.addEventListener('click', function () { openProjectChat(project.id, true); });
    if (project) {
      renderWorkbench();
      loadNotes(project.id);
    }
  }

  async function open() {
    if (!modal || !body) return;
    modal.classList.add('visible');
    body.innerHTML = '<div class="usage-modal-loading">Loading projects…</div>';
    try {
      await loadProjects();
      const currentId = Number(currentProjectConversation()?.projectId || 0);
      if (!state.projectId && (currentId || workspaces[0]?.id)) resetFolderState(currentId || workspaces[0].id);
      renderProjects();
      if (state.projectId) await restoreFolder(state.projectId);
    } catch (error) {
      body.innerHTML = '<div class="usage-modal-empty">' + esc(error.message || 'Could not load projects.') + '</div>';
    }
  }

  function decorateEmptyState(conversation) {
    const projectId = Number(conversation?.projectId || 0);
    if (!projectId) return;
    const project = workspaces.find(function (item) { return Number(item.id) === projectId; });
    if (!project) return;
    const shell = document.querySelector('#emptyState .empty-shell');
    if (!shell) return;
    const topline = shell.querySelector('.empty-topline');
    if (topline) {
      const icon = topline.querySelector('svg');
      topline.textContent = '';
      if (icon) topline.appendChild(icon);
      topline.append(document.createTextNode(' Project conversation'));
    }
    const title = shell.querySelector('h1');
    if (title) title.innerHTML = '<span class="greeting-mark">⌘</span><span>' + esc(project.name) + '</span>';
    const description = shell.querySelector(':scope > p');
    if (description) description.textContent = project.description
      ? project.description + ' Ask Vigzone to inspect, explain, fix, or implement work in the connected folder.'
      : 'Ask Vigzone to inspect, explain, fix, or implement work in the connected project folder.';
    const starterLabels = shell.querySelectorAll('.starter-item span');
    if (starterLabels[0]) starterLabels[0].textContent = 'Reads connected files';
    if (starterLabels[1]) starterLabels[1].textContent = 'Proposes exact edits';
    if (starterLabels[2]) starterLabels[2].textContent = 'You approve every write';
    const suggestions = shell.querySelector('.suggestions');
    if (suggestions) suggestions.innerHTML = [
      ['Read this whole project and explain its structure, current behavior, and the most important problems.', 'Understand the project', 'Inspect structure, behavior, and risks'],
      ['Find the root cause of the main broken or incomplete behavior in this project. Explain it, then propose the smallest safe fix.', 'Find and fix the problem', 'Analyze first, then review exact edits'],
      ['Read the project requirements and implement the missing work without adding unnecessary dependencies.', 'Complete the project', 'Implement focused missing features']
    ].map(function (item) {
      return '<div class="suggestion" data-prompt="' + esc(item[0]) + '" tabindex="0" role="button"><div class="suggestion-top">' +
        '<div class="s-icon">⌘</div><div><div class="s-title">' + esc(item[1]) + '</div><div class="s-sub">' +
        esc(item[2]) + '</div></div></div></div>';
    }).join('');
  }

  async function onConversationChanged(conversation) {
    const projectId = Number(conversation?.projectId || 0);
    if (typeof input !== 'undefined' && input) {
      input.placeholder = projectId ? 'Ask Vigzone to analyze or edit this project…' : 'Ask anything';
    }
    renderChatBar();
    if (!projectId) return;
    if (!workspaces.length) {
      try { await loadProjects(); } catch (error) { return; }
    }
    if (state.projectId !== projectId) resetFolderState(projectId);
    renderChatBar();
    await restoreFolder(projectId);
    renderChatBar();
    decorateEmptyState(conversation);
  }

  async function refresh() {
    try {
      await loadProjects();
      await onConversationChanged(currentProjectConversation());
    } catch (error) {
      if (sidebarList) sidebarList.innerHTML = '<div class="history-empty">Projects unavailable.</div>';
    }
  }

  async function initialize() {
    sidebarAddButton?.addEventListener('click', async function () {
      await openProjectSettings(null);
      document.getElementById('projectNameInput')?.focus();
    });
    chatNewButton?.addEventListener('click', function () {
      const projectId = Number(currentProjectConversation()?.projectId || 0);
      if (projectId) openProjectChat(projectId, true);
    });
    chatSettingsButton?.addEventListener('click', function () {
      const projectId = Number(currentProjectConversation()?.projectId || 0);
      if (projectId) openProjectSettings(projectId);
    });
    await refresh();
  }

  window.VigzoneProjects = {
    open: open,
    refresh: refresh,
    renderSidebar: renderSidebarProjects,
    assist: assist,
    renderMessageResult: renderMessageResult,
    handleChatError: handleChatError,
    onConversationChanged: onConversationChanged,
    decorateEmptyState: decorateEmptyState,
    openProjectChat: openProjectChat
  };

  const initializationGate = typeof accountReady !== 'undefined' ? accountReady : Promise.resolve();
  Promise.resolve(initializationGate).then(initialize).catch(function (error) {
    console.warn('Projects could not initialize', error);
  });
})();
