'use strict';

const api = window.vigiDesktop;
const root = document.getElementById('desktopVigi');
const panel = document.getElementById('speechPanel');
const petButton = document.getElementById('petButton');
const collapseButton = document.getElementById('collapseButton');
const form = document.getElementById('quickForm');
const prompt = document.getElementById('quickPrompt');
const count = document.getElementById('promptCount');
const askButton = document.getElementById('askButton');
const context = document.getElementById('chatContext');
const welcome = document.getElementById('welcomeCopy');
const status = document.getElementById('statusCopy');
const preview = document.getElementById('replyPreview');
const replyText = document.getElementById('replyText');
const openConversation = document.getElementById('openConversationButton');
const suggestions = document.querySelector('.suggestions');

let expanded = false;
let busy = false;
let updateAvailable = false;

function setState(state) {
  root.dataset.state = state;
}

async function setExpanded(next, notifyHost = true) {
  expanded = !!next;
  root.classList.toggle('expanded', expanded);
  panel.setAttribute('aria-hidden', expanded ? 'false' : 'true');
  petButton.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  if (notifyHost) await api.setExpanded(expanded);
  if (expanded) window.setTimeout(() => prompt.focus(), 80);
}

function applyStatus(data) {
  if (data?.title) context.textContent = data.title;
  if (data?.authenticated === false && data?.ready !== false) {
    status.textContent = 'Open Vigzone and sign in once before using quick chat.';
  } else if (data?.error) {
    status.textContent = data.error;
  } else if (!busy) {
    status.textContent = '';
  }
}

function plainPreview(value) {
  return String(value || '')
    .replace(/```[\s\S]*?```/g, ' [code included] ')
    .replace(/[`*_>#~-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 320);
}

async function askVigi() {
  const message = prompt.value.trim();
  if (!message || busy) return;
  busy = true;
  askButton.disabled = true;
  setState('thinking');
  status.textContent = 'Vigi is working in your last opened chat…';
  preview.hidden = true;
  try {
    const result = await api.ask(message);
    if (!result?.ok) throw new Error(result?.error || 'Vigi could not complete that message.');
    prompt.value = '';
    count.textContent = '0 / 4000';
    context.textContent = result.conversationTitle || context.textContent;
    replyText.textContent = plainPreview(result.preview) || 'The full reply is ready in Vigzone.';
    updateAvailable = false;
    openConversation.textContent = 'Open full conversation →';
    preview.hidden = false;
    status.textContent = '';
    setState('success');
    window.setTimeout(() => { if (!busy) setState('ready'); }, 1800);
  } catch (error) {
    status.textContent = error?.message || 'Vigi could not reach Vigzone.';
    setState('error');
  } finally {
    busy = false;
    askButton.disabled = false;
  }
}

petButton.addEventListener('click', () => setExpanded(!expanded));
collapseButton.addEventListener('click', () => setExpanded(false));
openConversation.addEventListener('click', () => updateAvailable ? api.openUpdate() : api.openVigzone());
form.addEventListener('submit', event => { event.preventDefault(); askVigi(); });
prompt.addEventListener('input', () => { count.textContent = `${prompt.value.length} / 4000`; });
prompt.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    askVigi();
  }
});
suggestions.addEventListener('click', event => {
  const button = event.target.closest('[data-prompt]');
  if (!button) return;
  prompt.value = button.dataset.prompt || '';
  count.textContent = `${prompt.value.length} / 4000`;
  prompt.focus();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && expanded) setExpanded(false);
});

api.onMainMinimized(payload => {
  welcome.textContent = payload?.message || 'Ask anything from Vigi. Your message will continue in the last opened chat.';
  setExpanded(true);
});
api.onMainRestored(() => {
  if (!busy && preview.hidden) setExpanded(false);
});
api.onStatus(applyStatus);
api.onUpdateAvailable(payload => {
  const version = String(payload?.version || '').trim();
  updateAvailable = true;
  context.textContent = 'Vigzone update';
  welcome.textContent = version
    ? `Vigzone Desktop v${version} is ready.`
    : 'A new Vigzone Desktop release is ready.';
  replyText.textContent = 'Review the release notes and download the official Windows installer from Vigzone.';
  openConversation.textContent = 'Open update in Vigzone →';
  preview.hidden = false;
  status.textContent = '';
  setState('success');
  setExpanded(true);
});
api.onExpanded(payload => setExpanded(!!payload?.expanded, false));

api.getStatus().then(applyStatus).catch(() => {
  status.textContent = 'Open Vigzone once to connect Vigi quick chat.';
});
