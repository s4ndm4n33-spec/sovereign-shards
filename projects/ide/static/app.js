const API = {
  async fetchJson(path, method = 'GET', body = null) {
    const options = { method };
    if (body) {
      options.headers = { 'Content-Type': 'application/json' };
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    return response.json();
  },
  async listFiles(path = '') {
    return this.fetchJson(`/api/fs/list?path=${encodeURIComponent(path)}`);
  },
  async readFile(path) {
    return this.fetchJson(`/api/fs/read?path=${encodeURIComponent(path)}`);
  },
  async writeFile(path, content) {
    return this.fetchJson('/api/fs/write', 'POST', { path, content });
  },
  async getWorkspaceState() {
    return this.fetchJson('/api/workspace/state');
  },
  async openEditor(path, language) {
    return this.fetchJson('/api/editor/open', 'POST', { path, language });
  },
  async closeEditor(path) {
    return this.fetchJson('/api/editor/close', 'POST', { path });
  },
  async setActiveEditor(path) {
    return this.fetchJson('/api/editor/setActive', 'POST', { path });
  },
  async markEditorDirty(path, dirty) {
    return this.fetchJson('/api/editor/markDirty', 'POST', { path, dirty });
  },
  async setSidebar(visible, activeView, width) {
    return this.fetchJson('/api/workspace/setSidebar', 'POST', { visible, activeView, width });
  },
  async getGitStatus() {
    return this.fetchJson('/api/scm/status');
  },
  async search(q, path) {
    return this.fetchJson(`/api/search?q=${encodeURIComponent(q)}&path=${encodeURIComponent(path)}`);
  },
  async findFiles(q, path = '') {
    return this.fetchJson(`/api/fs/find?q=${encodeURIComponent(q)}&path=${encodeURIComponent(path)}`);
  },
  async listExtensions() {
    return this.fetchJson('/api/extensions/list');
  },
  async getModelMarket() {
    return this.fetchJson('/api/market/models');
  },
  async getChatHistory() {
    return this.fetchJson('/api/chat/history');
  },
  async sendChatMessage(message) {
    return this.fetchJson('/api/chat/send', 'POST', { message });
  },
  async getCommands() {
    return this.fetchJson('/api/command');
  },
  async runCommand(command) {
    return this.fetchJson('/api/command', 'POST', { action: 'run_shell', command });
  },
};

let editor = null;
let editorState = {};
let currentFile = null;
let isDirty = false;
let chatHistory = [];
let commandPaletteMode = 'commands';
let commandPaletteIndex = 0;
const COMMANDS = [
  { id: 'openFile', label: 'Open File...', action: openQuickOpen },
  { id: 'openChat', label: 'Open Chat', action: openChat },
  { id: 'openMarketplace', label: 'Open Marketplace', action: openModelMarket },
  { id: 'searchWorkspace', label: 'Search Workspace', action: () => selectSidebarView('search') },
  { id: 'toggleExplorer', label: 'Toggle Explorer', action: () => selectSidebarView('explorer') },
  { id: 'toggleSCM', label: 'Toggle Source Control', action: () => selectSidebarView('scm') },
  { id: 'toggleDebug', label: 'Toggle Run and Debug', action: () => selectSidebarView('debug') },
  { id: 'toggleExtensions', label: 'Toggle Extensions', action: () => selectSidebarView('extensions') },
  { id: 'saveFile', label: 'Save Current File', action: saveCurrentFile },
];

async function initializeIDE() {
  await setupMonaco();
  await loadWorkspaceState();
  renderActivityBar();
  await renderExplorer();
  setupEventListeners();
  updateStatus();
}

function setupMonaco() {
  return new Promise((resolve) => {
    require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } });
    require(['vs/editor/editor.main'], () => {
      editor = monaco.editor.create(document.getElementById('editorContainer'), {
        value: '// Open a file to start editing\n',
        language: 'plaintext',
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: { enabled: true },
        scrollBeyondLastLine: false,
        lineNumbers: 'on',
        wordWrap: 'on',
        tabSize: 2,
        insertSpaces: true,
        folding: true,
      });
      editor.onDidChangeModelContent(() => {
        if (currentFile) {
          isDirty = true;
          API.markEditorDirty(currentFile, true);
          updateTabStatus();
        }
      });
      resolve();
    });
  });
}

async function loadWorkspaceState() {
  const response = await API.getWorkspaceState();
  if (response.ok) {
    editorState = response.state;
    if (editorState.openEditors && editorState.openEditors.length > 0) {
      renderTabBar();
      const activeId = editorState.activeEditor || editorState.openEditors[0].id;
      await switchToEditor(activeId);
    }
  }
}

function renderActivityBar() {
  const bar = document.querySelector('.activity-bar');
  const items = bar.querySelectorAll('.activity-item');
  items.forEach((item) => {
    item.addEventListener('click', async () => {
      const view = item.dataset.view;
      items.forEach((i) => i.classList.remove('active'));
      item.classList.add('active');
      await renderSidebarView(view);
    });
  });
  items[0].click();
}

async function renderSidebarView(view) {
  const title = document.getElementById('sidebarTitle');
  const content = document.getElementById('sidebarContent');
  content.innerHTML = '';
  if (view === 'explorer') {
    title.textContent = 'Explorer';
    await renderExplorer();
  } else if (view === 'search') {
    title.textContent = 'Search';
    renderSearch();
  } else if (view === 'scm') {
    title.textContent = 'Source Control';
    await renderSourceControl();
  } else if (view === 'debug') {
    title.textContent = 'Run and Debug';
    await renderDebug();
  } else if (view === 'chat') {
    title.textContent = 'Chat';
    await renderChat();
  } else if (view === 'extensions') {
    title.textContent = 'Extensions';
    await renderExtensions();
  } else if (view === 'market') {
    title.textContent = 'Marketplace';
    await renderModelMarket();
  }
}

async function renderExplorer() {
  const response = await API.listFiles('');
  if (!response.ok) return;
  const content = document.getElementById('sidebarContent');
  content.innerHTML = '';
  renderFileTree(response.entries, '', content, 0);
}

function renderFileTree(entries, basePath, container, depth) {
  entries.forEach((entry) => {
    const item = document.createElement('div');
    item.className = 'file-item';
    if (entry.isDirectory) item.classList.add('directory');
    item.style.paddingLeft = `${12 + depth * 16}px`;
    const expand = document.createElement('div');
    expand.className = 'file-item-expand';
    if (entry.isDirectory) {
      expand.innerHTML = '▶';
      expand.style.cursor = 'pointer';
      expand.addEventListener('click', (e) => {
        e.stopPropagation();
        const isExpanded = item.classList.contains('expanded');
        if (isExpanded) {
          item.classList.remove('expanded');
          const nextSibling = item.nextSibling;
          while (nextSibling && nextSibling.style.paddingLeft && parseInt(nextSibling.style.paddingLeft) > parseInt(item.style.paddingLeft)) {
            const toRemove = nextSibling;
            nextSibling = nextSibling.nextSibling;
            toRemove.remove();
          }
        } else {
          item.classList.add('expanded');
          expand.innerHTML = '▼';
          API.listFiles(entry.path).then((res) => {
            if (res.ok) {
              const fragment = document.createDocumentFragment();
              const tempDiv = document.createElement('div');
              renderFileTree(res.entries, entry.path, tempDiv, depth + 1);
              Array.from(tempDiv.children).forEach((child) => {
                item.parentNode.insertBefore(child, item.nextSibling);
              });
            }
          });
        }
      });
    }
    item.appendChild(expand);
    const icon = document.createElement('div');
    icon.className = 'file-item-icon';
    icon.textContent = entry.isDirectory ? '📁' : '📄';
    item.appendChild(icon);
    const name = document.createElement('div');
    name.className = 'file-item-name';
    name.textContent = entry.name;
    item.appendChild(name);
    item.addEventListener('click', async () => {
      if (entry.isFile) {
        document.querySelectorAll('.file-item.selected').forEach((e) => e.classList.remove('selected'));
        item.classList.add('selected');
        await openFile(entry.path, entry.name);
      }
    });
    container.appendChild(item);
  });
}

async function openFile(path, name) {
  const response = await API.readFile(path);
  if (!response.ok) return;
  currentFile = path;
  isDirty = false;
  editor.setValue(response.content);
  monaco.editor.setModelLanguage(editor.getModel(), response.language || 'plaintext');
  updateBreadcrumb(path);
  const editorResponse = await API.openEditor(path, response.language);
  if (editorResponse.ok) {
    await loadWorkspaceState();
    renderTabBar();
    updateTabStatus();
  }
}

function renderTabBar() {
  const tabBar = document.getElementById('tabBar');
  tabBar.innerHTML = '';
  if (!editorState.openEditors) return;
  editorState.openEditors.forEach((editor) => {
    const tab = document.createElement('button');
    tab.className = 'tab';
    if (editor.id === editorState.activeEditor || editor.id === currentFile) {
      tab.classList.add('active');
    }
    if (editor.dirty) {
      tab.classList.add('dirty');
    }
    const icon = document.createElement('span');
    icon.textContent = '📄 ';
    tab.appendChild(icon);
    const label = document.createElement('span');
    label.textContent = editor.id.split('/').pop();
    tab.appendChild(label);
    const closeBtn = document.createElement('span');
    closeBtn.className = 'tab-close';
    closeBtn.innerHTML = '✕';
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      API.closeEditor(editor.id);
      loadWorkspaceState();
    });
    tab.appendChild(closeBtn);
    tab.addEventListener('click', () => switchToEditor(editor.id));
    tabBar.appendChild(tab);
  });
}

async function switchToEditor(editorId) {
  const response = await API.readFile(editorId);
  if (!response.ok) return;
  currentFile = editorId;
  editor.setValue(response.content);
  monaco.editor.setModelLanguage(editor.getModel(), response.language || 'plaintext');
  updateBreadcrumb(editorId);
  API.setActiveEditor(editorId);
  renderTabBar();
  isDirty = false;
  updateTabStatus();
}

function updateBreadcrumb(path) {
  const parts = path.split('/').filter((p) => p);
  const breadcrumb = document.getElementById('breadcrumb');
  breadcrumb.innerHTML = parts.map((part, idx) => `<div class="breadcrumb-item">${idx > 0 ? '<span class="breadcrumb-separator">›</span>' : ''}${part}</div>`).join('');
}

function updateTabStatus() {
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.classList.remove('dirty');
  });
  if (isDirty && currentFile) {
    document.querySelectorAll('.tab').forEach((tab) => {
      if (tab.textContent.includes(currentFile.split('/').pop())) {
        tab.classList.add('dirty');
      }
    });
  }
}

function renderSearch() {
  const content = document.getElementById('sidebarContent');
  content.innerHTML = '';
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'Search in workspace...';
  input.style.padding = '8px 12px';
  input.style.margin = '8px';
  input.style.background = 'var(--bg-tertiary)';
  input.style.border = '1px solid var(--border)';
  input.style.color = 'var(--fg-primary)';
  const results = document.createElement('div');
  results.style.margin = '8px 0';
  input.addEventListener('input', async (e) => {
    const query = e.target.value.trim();
    results.innerHTML = '';
    if (!query) {
      return;
    }
    const response = await API.search(query);
    if (response.ok && response.results) {
      response.results.slice(0, 20).forEach((result) => {
        const file = document.createElement('div');
        file.style.padding = '4px 12px';
        file.style.marginBottom = '8px';
        file.style.cursor = 'pointer';
        file.textContent = result.path;
        file.addEventListener('click', async () => {
          await openFile(result.path, result.path.split('/').pop());
        });
        results.appendChild(file);
        result.matches.forEach((match) => {
          const line = document.createElement('div');
          line.style.paddingLeft = '24px';
          line.style.fontSize = '11px';
          line.style.color = 'var(--fg-secondary)';
          line.textContent = `${match.line}: ${match.text}`;
          results.appendChild(line);
        });
      });
    } else {
      results.textContent = 'No results';
    }
  });
  content.appendChild(input);
  content.appendChild(results);
}

async function renderSourceControl() {
  const response = await API.getGitStatus();
  const content = document.getElementById('sidebarContent');
  content.innerHTML = '';
  if (!response.ok) {
    content.innerHTML = '<div style="padding: 16px; color: var(--fg-secondary);">Not a git repository</div>';
    return;
  }
  const changes = response.changes || [];
  if (!changes.length) {
    content.innerHTML = '<div style="padding: 16px; color: var(--fg-secondary);">Clean working tree</div>';
    return;
  }
  changes.forEach((change) => {
    const item = document.createElement('div');
    item.style.padding = '4px 12px';
    item.style.cursor = 'pointer';
    item.textContent = `${change.status} ${change.path}`;
    item.addEventListener('click', () => openFile(change.path, change.path.split('/').pop()));
    content.appendChild(item);
  });
}

function setupEventListeners() {
  document.getElementById('sidebarToggle').addEventListener('click', async () => {
    const sidebar = document.querySelector('.sidebar');
    const isVisible = !sidebar.classList.contains('hidden');
    sidebar.classList.toggle('hidden');
    await API.setSidebar(!isVisible, 'explorer', 300);
  });
  document.querySelectorAll('.menu-item').forEach((item) => {
    item.addEventListener('click', async () => {
      const action = item.dataset.action;
      if (action === 'openFile') openQuickOpen();
      if (action === 'commandPalette') openCommandPalette();
      if (action === 'toggleExplorer') selectSidebarView('explorer');
      if (action === 'toggleSearch') selectSidebarView('search');
      if (action === 'toggleSCM') selectSidebarView('scm');
      if (action === 'toggleExtensions') selectSidebarView('extensions');
      if (action === 'saveFile') saveCurrentFile();
    });
  });
  document.addEventListener('keydown', async (e) => {
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'p') {
      e.preventDefault();
      openCommandPalette();
    }
    if (e.ctrlKey && e.key.toLowerCase() === 'p' && !e.shiftKey) {
      e.preventDefault();
      openQuickOpen();
    }
    if (e.ctrlKey && e.key.toLowerCase() === 's') {
      e.preventDefault();
      saveCurrentFile();
    }
    if (e.key === 'Escape') {
      closeCommandPalette();
    }
  });
  document.getElementById('commandInput').addEventListener('input', () => {
    renderCommandResults();
  });
  document.getElementById('commandInput').addEventListener('keydown', (e) => {
    const results = document.querySelectorAll('.command-results .command-item');
    if (!results.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      commandPaletteIndex = Math.min(commandPaletteIndex + 1, results.length - 1);
      highlightCommandResult(results);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      commandPaletteIndex = Math.max(commandPaletteIndex - 1, 0);
      highlightCommandResult(results);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const selected = results[commandPaletteIndex];
      if (selected) {
        selected.click();
      }
    }
  });
}

function highlightCommandResult(results) {
  results.forEach((item, index) => {
    item.classList.toggle('active', index === commandPaletteIndex);
  });
}

function openCommandPalette() {
  commandPaletteMode = 'commands';
  commandPaletteIndex = 0;
  const palette = document.getElementById('commandPalette');
  palette.classList.remove('hidden');
  const input = document.getElementById('commandInput');
  input.value = '>';
  input.placeholder = 'Type a command';
  renderCommandResults();
  input.focus();
}

function openQuickOpen() {
  commandPaletteMode = 'files';
  commandPaletteIndex = 0;
  const palette = document.getElementById('commandPalette');
  palette.classList.remove('hidden');
  const input = document.getElementById('commandInput');
  input.value = '';
  input.placeholder = 'Type a file name...';
  renderCommandResults();
  input.focus();
}

function closeCommandPalette() {
  const palette = document.getElementById('commandPalette');
  palette.classList.add('hidden');
}

async function renderCommandResults() {
  const input = document.getElementById('commandInput');
  const query = input.value.trim();
  const results = document.getElementById('commandResults');
  commandPaletteIndex = 0;
  results.innerHTML = '';
  if (commandPaletteMode === 'commands') {
    const candidates = COMMANDS.filter((command) => {
      if (!query || query === '>') return true;
      return command.label.toLowerCase().includes(query.replace(/^>/, '').trim().toLowerCase());
    });
    candidates.forEach((command, index) => {
      const item = document.createElement('div');
      item.className = 'command-item';
      item.textContent = command.label;
      item.addEventListener('click', async () => {
        closeCommandPalette();
        await command.action();
      });
      results.appendChild(item);
      if (index === commandPaletteIndex) {
        item.classList.add('active');
      }
    });
  } else {
    const queryValue = query.trim();
    if (!queryValue) {
      results.innerHTML = '<div class="command-item" style="cursor: default;">Start typing to search files</div>';
      return;
    }
    const response = await API.findFiles(queryValue);
    if (!response.ok) {
      results.innerHTML = `<div class="command-item" style="cursor: default;">${response.error || 'No results'}</div>`;
      return;
    }
    response.results.slice(0, 50).forEach((file, index) => {
      const item = document.createElement('div');
      item.className = 'command-item';
      item.textContent = file.path;
      item.addEventListener('click', async () => {
        closeCommandPalette();
        await openFile(file.path, file.name);
      });
      results.appendChild(item);
      if (index === commandPaletteIndex) {
        item.classList.add('active');
      }
    });
  }
}

function selectSidebarView(view) {
  document.querySelectorAll('.activity-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.view === view);
  });
  renderSidebarView(view);
}

function openChat() {
  selectSidebarView('chat');
}

function openModelMarket() {
  selectSidebarView('market');
}

async function saveCurrentFile() {
  if (!currentFile || !isDirty) return;
  const content = editor.getValue();
  const response = await API.writeFile(currentFile, content);
  if (response.ok) {
    isDirty = false;
    API.markEditorDirty(currentFile, false);
    updateTabStatus();
  }
}

async function renderDebug() {
  const content = document.getElementById('sidebarContent');
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'Run shell command';
  input.style.width = '100%';
  input.style.boxSizing = 'border-box';
  input.style.margin = '8px 0';
  const button = document.createElement('button');
  button.textContent = 'Run';
  button.addEventListener('click', async () => {
    if (!input.value.trim()) return;
    await API.runCommand(input.value.trim());
    input.value = '';
    await renderDebug();
  });
  const controls = document.createElement('div');
  controls.style.display = 'flex';
  controls.style.gap = '8px';
  controls.appendChild(input);
  controls.appendChild(button);
  content.innerHTML = '';
  content.appendChild(controls);
  const state = await API.getCommands();
  const commands = state.commands || [];
  if (!commands.length) {
    const empty = document.createElement('div');
    empty.style.padding = '12px';
    empty.style.color = 'var(--fg-secondary)';
    empty.textContent = 'No commands have been run yet.';
    content.appendChild(empty);
    return;
  }
  commands.slice().reverse().forEach((task) => {
    const block = document.createElement('div');
    block.className = 'extension-item';
    const title = document.createElement('div');
    title.textContent = `#${task.id} ${task.command}`;
    title.style.fontWeight = '600';
    const status = document.createElement('div');
    status.textContent = `Status: ${task.status}`;
    status.style.marginBottom = '8px';
    const output = document.createElement('pre');
    output.style.maxHeight = '120px';
    output.style.overflow = 'auto';
    output.style.whiteSpace = 'pre-wrap';
    output.textContent = task.output || '(no output yet)';
    block.appendChild(title);
    block.appendChild(status);
    block.appendChild(output);
    content.appendChild(block);
  });
}

async function renderExtensions() {
  const content = document.getElementById('sidebarContent');
  const response = await API.listExtensions();
  if (!response.ok) {
    content.innerHTML = `<div style="padding: 16px; color: var(--fg-secondary);">${response.error || 'Unable to load extensions.'}</div>`;
    return;
  }
  const extensions = response.extensions || [];
  if (!extensions.length) {
    content.innerHTML = '<div style="padding: 16px; color: var(--fg-secondary);">No extensions installed.</div>';
    return;
  }
  content.innerHTML = '';
  extensions.forEach((ext) => {
    const item = document.createElement('div');
    item.className = 'extension-item';
    const label = document.createElement('div');
    label.textContent = ext.name;
    label.style.fontWeight = '600';
    const path = document.createElement('div');
    path.textContent = ext.path;
    path.style.color = 'var(--fg-secondary)';
    const button = document.createElement('button');
    button.textContent = 'Load';
    button.addEventListener('click', () => {
      const script = document.createElement('script');
      script.src = `/${ext.path}`;
      document.body.appendChild(script);
      button.textContent = 'Loaded';
      button.disabled = true;
    });
    item.appendChild(label);
    item.appendChild(path);
    item.appendChild(button);
    content.appendChild(item);
  });
}

async function renderChat() {
  const content = document.getElementById('sidebarContent');
  content.innerHTML = '';
  const history = await API.getChatHistory();
  chatHistory = history.messages || [];

  const conversation = document.createElement('div');
  conversation.className = 'chat-history';
  conversation.style.padding = '12px';
  conversation.style.maxHeight = 'calc(100vh - 220px)';
  conversation.style.overflow = 'auto';
  chatHistory.forEach((message) => {
    const entry = document.createElement('div');
    entry.className = `chat-message ${message.role}`;
    entry.textContent = `${message.role === 'assistant' ? 'Agent' : 'You'}: ${message.text}`;
    conversation.appendChild(entry);
  });

  const input = document.createElement('textarea');
  input.id = 'chatInput';
  input.placeholder = 'Type a message to the chat agent...';
  input.style.width = '100%';
  input.style.height = '90px';
  input.style.marginTop = '8px';
  input.style.boxSizing = 'border-box';

  const sendButton = document.createElement('button');
  sendButton.textContent = 'Send';
  sendButton.style.marginTop = '8px';
  sendButton.addEventListener('click', async () => {
    const message = input.value.trim();
    if (!message) return;
    sendButton.disabled = true;
    const response = await API.sendChatMessage(message);
    sendButton.disabled = false;
    if (!response.ok) return;
    input.value = '';
    await renderChat();
  });

  content.appendChild(conversation);
  content.appendChild(input);
  content.appendChild(sendButton);
}

async function renderModelMarket() {
  const content = document.getElementById('sidebarContent');
  content.innerHTML = '';
  const response = await API.getModelMarket();
  if (!response.ok) {
    content.innerHTML = `<div style="padding: 16px; color: var(--fg-secondary);">${response.error || 'Unable to load marketplace.'}</div>`;
    return;
  }
  const models = response.models || [];
  if (!models.length) {
    content.innerHTML = '<div style="padding: 16px; color: var(--fg-secondary);">No models available.</div>';
    return;
  }
  models.forEach((model) => {
    const item = document.createElement('div');
    item.className = 'extension-item';
    const label = document.createElement('div');
    label.textContent = model.name;
    label.style.fontWeight = '600';
    const description = document.createElement('div');
    description.textContent = model.description || 'Model available for download';
    description.style.color = 'var(--fg-secondary)';
    const button = document.createElement('button');
    button.textContent = 'Install';
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = 'Installing...';
      await API.fetchJson('/api/market/install', 'POST', { model: model.name });
      button.textContent = 'Installed';
    });
    item.appendChild(label);
    item.appendChild(description);
    item.appendChild(button);
    content.appendChild(item);
  });
}

function updateStatus() {
  API.getGitStatus().then((response) => {
    if (response.ok && response.changes) {
      document.getElementById('gitStatus').textContent = `$(git) ${response.changes.length} changes`;
    }
  });
  setInterval(() => {
    if (editor && currentFile) {
      const model = editor.getModel();
      if (model) {
        const position = editor.getPosition();
        document.getElementById('editorStats').textContent = `Ln ${position.lineNumber}, Col ${position.column}`;
      }
    }
  }, 100);
}

window.addEventListener('DOMContentLoaded', initializeIDE);
