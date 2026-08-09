/* Vigzone Projects: browser-approved local folders with metered AI assistance. */
(function () {
  'use strict';

  const modal = document.getElementById('workspaceModalOverlay');
  const body = document.getElementById('workspaceModalBody');
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
    currentPath: '',
    currentText: '',
    dirty: false,
    readOnly: false,
    loading: false,
    busy: false,
    instruction: '',
    result: null
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
    state.selectedPaths = new Set();
    state.currentPath = '';
    state.currentText = '';
    state.dirty = false;
    state.readOnly = false;
    state.loading = false;
    state.busy = false;
    state.instruction = '';
    state.result = null;
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
      if (state.currentPath && !state.files.some(function (item) { return item.path === state.currentPath; })) {
        state.currentPath = '';
        state.currentText = '';
        state.dirty = false;
      }
    } catch (error) {
      state.permission = 'prompt';
      state.files = [];
      notify(error.message || 'Could not scan this folder.');
    } finally {
      state.loading = false;
      renderWorkbench();
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
    else renderWorkbench();
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
      renderWorkbench();
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
    resetFolderState(state.projectId);
    renderWorkbench();
  }

  function activeProject() {
    return (workspaces || []).find(function (item) {
      return Number(item.id) === Number(activeWorkspaceId);
    }) || null;
  }

  function updateProjectIndicator() {
    if (typeof updateWorkspacePill === 'function') updateWorkspacePill();
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
  }

  async function selectProject(projectId) {
    if (state.dirty && !window.confirm('Discard the unsaved local file edit and switch projects?')) return;
    activeWorkspaceId = Number(projectId);
    localStorage.setItem('vigzone_active_workspace_id', String(activeWorkspaceId));
    resetFolderState(activeWorkspaceId);
    updateProjectIndicator();
    renderProjects();
    await restoreFolder(activeWorkspaceId);
    await loadNotes(activeWorkspaceId);
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
    renderProjects();
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
    activeWorkspaceId = null;
    localStorage.removeItem('vigzone_active_workspace_id');
    resetFolderState(null);
    await loadProjects();
    renderProjects();
    notify('Project record deleted. Your local folder was untouched.');
  }

  async function loadNotes(projectId) {
    const target = document.getElementById('projectNotesList');
    if (!target || Number(projectId) !== Number(activeWorkspaceId)) return;
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

  async function openFile(path) {
    if (state.dirty && state.currentPath !== path && !window.confirm('Discard the unsaved edit in ' + state.currentPath + '?')) return;
    const entry = state.files.find(function (item) { return item.path === path; });
    try {
      state.currentText = await readEntry(entry);
      state.currentPath = path;
      state.dirty = false;
      state.selectedPaths.add(path);
      renderWorkbench();
    } catch (error) {
      notify(error.message || 'Could not open this file.');
    }
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

  async function saveCurrentFile() {
    if (!state.currentPath || state.readOnly) return;
    try {
      await writeFile(state.currentPath, state.currentText);
      state.dirty = false;
      notify('Saved ' + state.currentPath + ' to the local folder.');
      renderWorkbench();
    } catch (error) {
      notify(error.message || 'Could not save this file.');
    }
  }

  function rankedContextEntries() {
    let entries = state.files.filter(function (item) { return state.selectedPaths.has(item.path); });
    if (!entries.length && state.currentPath) {
      entries = state.files.filter(function (item) { return item.path === state.currentPath; });
    }
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
      let content = state.currentPath === entry.path && state.dirty
        ? state.currentText
        : await readEntry(entry);
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

  async function runAssistant(action) {
    const project = activeProject();
    if (!project || state.busy) return;
    if (!state.files.length) return notify('Connect a project folder containing text or code files first.');
    const instructionInput = document.getElementById('projectInstruction');
    state.instruction = instructionInput ? instructionInput.value.trim() : state.instruction;
    state.busy = true;
    state.result = null;
    renderWorkbench();
    try {
      const files = await collectAiFiles();
      if (!files.length) throw new Error('Select at least one readable text file.');
      const response = await fetch('/api/projects/assist', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          project_id: Number(project.id),
          action: action,
          instruction: state.instruction,
          model: typeof getActiveModel === 'function' ? getActiveModel() : 'openai/gpt-oss-20b',
          tree: state.files.map(function (item) { return item.path; }),
          files: files
        })
      });
      const data = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(data.detail || 'Project AI action failed.');
      state.result = {
        action: action,
        summary: data.summary || 'Project analysis complete.',
        changes: Array.isArray(data.changes) ? data.changes : [],
        meta: data.meta || {}
      };
    } catch (error) {
      state.result = {action: action, summary: error.message || 'Project AI action failed.', changes: [], error: true};
    } finally {
      state.busy = false;
      renderWorkbench();
      if (typeof refreshUsageCycle === 'function') refreshUsageCycle();
    }
  }

  async function applyChanges() {
    if (state.readOnly || !state.handle || !state.result || !state.result.changes.length) return;
    const selected = Array.from(document.querySelectorAll('[data-project-change-index]:checked')).map(function (input) {
      return state.result.changes[Number(input.getAttribute('data-project-change-index'))];
    }).filter(Boolean);
    if (!selected.length) return notify('Select at least one proposed file change.');
    if (!window.confirm('Write ' + selected.length + ' reviewed change(s) to your local project folder?')) return;
    try {
      for (const change of selected) {
        const path = safeRelativePath(change.path);
        if (!path) throw new Error('Vigzone proposed an unsafe file path.');
        await writeFile(path, String(change.content == null ? '' : change.content));
      }
      const currentPath = state.currentPath;
      state.result = null;
      state.dirty = false;
      await rescanFolder();
      if (currentPath && state.files.some(function (item) { return item.path === currentPath; })) {
        await openFile(currentPath);
      }
      notify('Reviewed changes were saved to your local folder.');
    } catch (error) {
      notify(error.message || 'Could not apply the proposed changes.');
    }
  }

  function renderResult() {
    if (state.busy) {
      return '<div class="project-ai-result loading"><div class="usage-modal-loading">Vigzone is reviewing the selected files. This usage counts toward today\'s plan quota…</div></div>';
    }
    if (!state.result) return '';
    const changes = state.result.changes || [];
    const changeHtml = changes.length ? '<div class="project-change-list">' + changes.map(function (change, index) {
      return '<div class="project-change-row"><input type="checkbox" data-project-change-index="' + index +
        '" checked><span><strong>' + esc(change.path) + '</strong><small>' +
        esc(change.reason || 'AI-proposed change') + '</small><details><summary>Review full replacement content</summary><pre>' +
        esc(change.content || '') + '</pre></details></span></div>';
    }).join('') + '</div>' : '<div class="suite-note">No file changes were proposed.</div>';
    const apply = changes.length
      ? '<button class="deep-action-btn project-primary" id="projectApplyChangesBtn" type="button"' +
        (state.readOnly ? ' disabled title="Reconnect with read/write access to apply changes"' : '') +
        '>Apply reviewed changes</button>'
      : '';
    return '<div class="project-ai-result' + (state.result.error ? ' error' : '') + '">' +
      '<div class="settings-section-title">Vigzone result</div><pre>' + esc(state.result.summary) +
      '</pre>' + changeHtml + '<div class="project-result-actions">' + apply + '</div></div>';
  }

  function renderWorkbench() {
    const target = document.getElementById('projectWorkbench');
    const project = activeProject();
    if (!target || !project || Number(project.id) !== Number(activeWorkspaceId)) return;
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
      const active = entry.path === state.currentPath ? ' active' : '';
      const checked = state.selectedPaths.has(entry.path) ? ' checked' : '';
      return '<div class="project-file-row' + active + '"><input type="checkbox" data-project-select-file="' +
        esc(entry.path) + '"' + checked + ' aria-label="Include ' + esc(entry.path) + ' in AI context">' +
        '<button type="button" data-project-open-file="' + esc(entry.path) + '"><span>' +
        esc(entry.path) + '</span><small>' + Math.max(1, Math.ceil(entry.size / 1024)) + ' KB</small></button></div>';
    }).join('');
    const editor = state.currentPath
      ? '<div class="project-editor-head"><strong>' + esc(state.currentPath) + '</strong><span>' +
        (state.dirty ? 'Unsaved changes' : (state.readOnly ? 'Read-only import' : 'Saved locally')) +
        '</span></div><textarea id="projectFileEditor" class="project-file-editor" spellcheck="false">' +
        esc(state.currentText) + '</textarea><div class="project-editor-actions"><button class="deep-action-btn" id="projectSaveFileBtn" type="button"' +
        (state.readOnly || !state.dirty ? ' disabled' : '') + '>Save file</button></div>'
      : '<div class="project-editor-empty">Select a file to inspect or edit it.</div>';
    target.innerHTML = '<div class="project-folder-toolbar"><div><strong>📁 ' + esc(state.folderName) +
      '</strong><small>' + state.files.length + ' text/code files · ' + state.ignoredCount +
      ' ignored safely' + (state.readOnly ? ' · read-only browser import' : '') +
      '</small></div><div><button class="deep-action-btn" id="projectRescanBtn" type="button"' +
      (state.handle ? '' : ' disabled') + '>Rescan</button><button class="deep-action-btn" id="projectDisconnectBtn" type="button">Disconnect</button></div></div>' +
      '<div class="project-workbench-grid"><aside class="project-file-tree"><div class="project-pane-label">Files selected for AI</div>' +
      rows + '</aside><section class="project-editor-pane">' + editor + '</section></div>' +
      '<div class="project-ai-panel"><label for="projectInstruction">What should Vigzone do?</label>' +
      '<textarea id="projectInstruction" maxlength="4000" placeholder="Example: Find the login bug, explain the cause, and propose the smallest safe fix.">' +
      esc(state.instruction) + '</textarea><div class="project-ai-actions"><span>Selected file text and the approved folder\'s filtered file names are sent securely to Vigzone. AI usage follows your plan quota.</span>' +
      '<button class="deep-action-btn" id="projectAnalyzeBtn" type="button">Analyze selected</button>' +
      '<button class="deep-action-btn project-primary" id="projectEditBtn" type="button">Propose edits</button></div></div>' +
      renderResult();

    target.querySelectorAll('[data-project-open-file]').forEach(function (button) {
      button.addEventListener('click', function () { openFile(button.getAttribute('data-project-open-file')); });
    });
    target.querySelectorAll('[data-project-select-file]').forEach(function (checkbox) {
      checkbox.addEventListener('change', function () {
        const path = checkbox.getAttribute('data-project-select-file');
        if (checkbox.checked) state.selectedPaths.add(path);
        else state.selectedPaths.delete(path);
      });
    });
    const editorInput = document.getElementById('projectFileEditor');
    if (editorInput) editorInput.addEventListener('input', function () {
      state.currentText = editorInput.value;
      state.dirty = true;
      const saveButton = document.getElementById('projectSaveFileBtn');
      if (saveButton && !state.readOnly) saveButton.disabled = false;
      const status = target.querySelector('.project-editor-head span');
      if (status) status.textContent = 'Unsaved changes';
    });
    const instructionInput = document.getElementById('projectInstruction');
    if (instructionInput) instructionInput.addEventListener('input', function () {
      state.instruction = instructionInput.value;
    });
    document.getElementById('projectSaveFileBtn')?.addEventListener('click', saveCurrentFile);
    document.getElementById('projectRescanBtn')?.addEventListener('click', rescanFolder);
    document.getElementById('projectDisconnectBtn')?.addEventListener('click', disconnectFolder);
    document.getElementById('projectAnalyzeBtn')?.addEventListener('click', function () { runAssistant('analyze'); });
    document.getElementById('projectEditBtn')?.addEventListener('click', function () { runAssistant('edit'); });
    document.getElementById('projectApplyChangesBtn')?.addEventListener('click', applyChanges);
  }

  function renderProjects() {
    if (!body) return;
    const project = activeProject();
    const canShare = !!(window._vigzoneEntitlements && window._vigzoneEntitlements.features &&
      window._vigzoneEntitlements.features.team_workspace);
    const cards = (workspaces || []).length ? workspaces.map(function (item) {
      const active = Number(item.id) === Number(activeWorkspaceId) ? ' active' : '';
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
      renderProjects();
      if (activeWorkspaceId) await restoreFolder(activeWorkspaceId);
    } catch (error) {
      body.innerHTML = '<div class="usage-modal-empty">' + esc(error.message || 'Could not load projects.') + '</div>';
    }
  }

  window.VigzoneProjects = {open: open};
})();
