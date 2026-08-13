/* Classic Vigi: desktop-only companion driven by authenticated plan and usage state. */
(function () {
  'use strict';

  const companion = document.getElementById('vigiCompanion');
  const petButton = document.getElementById('vigiPetButton');
  const petState = document.getElementById('vigiPetState');
  const popover = document.getElementById('vigiPopover');
  const popoverClose = document.getElementById('vigiPopoverClose');
  const roleBadge = document.getElementById('vigiRoleBadge');
  const statusCopy = document.getElementById('vigiStatusCopy');
  const usageLabel = document.getElementById('vigiUsageLabel');
  const usageValue = document.getElementById('vigiUsageValue');
  const usageDetail = document.getElementById('vigiUsageDetail');
  const usageTrack = document.getElementById('vigiUsageTrack');
  const usageFill = document.getElementById('vigiUsageFill');
  const actions = document.getElementById('vigiActions');
  const planAction = document.getElementById('vigiPlanAction');
  const planActionLabel = document.getElementById('vigiPlanActionLabel');
  const settingsToggle = document.getElementById('vigiSettingsToggle');
  const settingsToggleLabel = document.getElementById('vigiSettingsToggleLabel');
  const workBadge = document.getElementById('vigiWorkBadge');
  const workLabel = document.getElementById('vigiWorkLabel');
  if (!companion || !petButton || !popover) return;

  const DESKTOP_QUERY = '(min-width:900px) and (hover:hover) and (pointer:fine)';
  const desktopMedia = window.matchMedia(DESKTOP_QUERY);
  const STORAGE_ENABLED = 'vigzone_vigi_enabled_v1';
  const STORAGE_POSITION = 'vigzone_vigi_position_v1';
  const PLAN_PRESENTATION = Object.freeze({
    free: {
      label: 'FREE',
      actionLabel: 'Explore upgrades',
      actionTarget: 'upgradePlanBtn',
      ready: 'Classic Vigi is ready. Chat, web search, File Studio and Projects are unlocked.'
    },
    pro: {
      label: 'PRO',
      actionLabel: 'Website Studio',
      actionTarget: 'websiteStudioBtn',
      ready: 'Classic Vigi is ready with all models, creative tools and PRO Projects.'
    },
    team: {
      label: 'TEAM',
      actionLabel: 'TEAM Hub',
      actionTarget: 'teamHubBtn',
      ready: 'Classic Vigi is connected to your TEAM workspace and shared quota.'
    },
    admin: {
      label: 'ADMIN',
      actionLabel: 'Admin dashboard',
      actionTarget: 'adminPanelBtn',
      ready: 'Classic Vigi is in administrator mode. Every Vigzone capability is unlocked.'
    }
  });

  let userId = null;
  let accountReady = false;
  let enabled = true;
  let plan = 'free';
  let entitlements = {};
  let usage = null;
  let activity = 'ready';
  let activityDetail = {};
  let terminalStateTimer = 0;
  let suppressNextClick = false;

  function scopedKey(base) {
    return userId ? `${base}:${userId}` : `${base}:guest`;
  }

  function readEnabled() {
    try { return localStorage.getItem(scopedKey(STORAGE_ENABLED)) !== 'false'; }
    catch (_) { return true; }
  }

  function syncSettingsToggle() {
    if (!settingsToggle) return;
    settingsToggle.setAttribute('aria-checked', enabled ? 'true' : 'false');
    settingsToggle.classList.toggle('is-on', enabled);
    if (settingsToggleLabel) settingsToggleLabel.textContent = enabled ? 'On' : 'Off';
  }

  function setEnabled(next) {
    enabled = !!next;
    try { localStorage.setItem(scopedKey(STORAGE_ENABLED), String(enabled)); } catch (_) {}
    if (!enabled) closePopover();
    syncSettingsToggle();
    syncVisibility();
  }

  function syncVisibility() {
    companion.classList.toggle('is-ready', accountReady);
    companion.classList.toggle('is-enabled', enabled && desktopMedia.matches);
    companion.setAttribute('aria-hidden', accountReady && enabled && desktopMedia.matches ? 'false' : 'true');
  }

  function clampPosition(left, top) {
    const rect = petButton.getBoundingClientRect();
    const width = rect.width || 132;
    const height = rect.height || 150;
    const padding = 12;
    return {
      left: Math.max(padding, Math.min(Number(left) || padding, window.innerWidth - width - padding)),
      top: Math.max(padding, Math.min(Number(top) || padding, window.innerHeight - height - padding))
    };
  }

  function applyPosition(position) {
    if (!position || !Number.isFinite(Number(position.left)) || !Number.isFinite(Number(position.top))) return;
    const safe = clampPosition(position.left, position.top);
    companion.style.left = `${safe.left}px`;
    companion.style.top = `${safe.top}px`;
    companion.style.right = 'auto';
    companion.style.bottom = 'auto';
  }

  function restorePosition() {
    companion.removeAttribute('style');
    try {
      const saved = JSON.parse(localStorage.getItem(scopedKey(STORAGE_POSITION)) || 'null');
      applyPosition(saved);
    } catch (_) {}
  }

  function savePosition() {
    const rect = petButton.getBoundingClientRect();
    try {
      localStorage.setItem(scopedKey(STORAGE_POSITION), JSON.stringify({left:Math.round(rect.left), top:Math.round(rect.top)}));
    } catch (_) {}
  }

  function normalizedPlan(detail) {
    if (detail?.isAdmin || detail?.displayPlan === 'admin') return 'admin';
    const candidate = String(detail?.effectivePlan || detail?.displayPlan || 'free').toLowerCase();
    return Object.prototype.hasOwnProperty.call(PLAN_PRESENTATION, candidate) ? candidate : 'free';
  }

  function syncPlan() {
    const presentation = PLAN_PRESENTATION[plan];
    companion.dataset.plan = plan;
    roleBadge.textContent = presentation.label;
    planActionLabel.textContent = presentation.actionLabel;
    planAction.dataset.target = presentation.actionTarget;
    renderStatus();
  }

  function usageNumbers(data) {
    const limit = Math.max(0, Number(data?.daily_limit || 0));
    const used = Math.max(0, Number(data?.used_today || 0));
    const reserved = Math.max(0, Number(data?.reserved_today || 0));
    const counted = Math.max(0, Number(data?.counted_today ?? (used + reserved)));
    const unlimited = !!data?.quota_unlimited || limit <= 0;
    const remaining = unlimited ? null : Math.max(0, Number(data?.remaining_today ?? (limit - counted)));
    const percent = unlimited || !limit ? 0 : Math.max(0, Math.min(100, (counted / limit) * 100));
    return {limit, used, reserved, counted, unlimited, remaining, percent};
  }

  function compactNumber(value) {
    return new Intl.NumberFormat(undefined, {notation:'compact', maximumFractionDigits:1}).format(Math.max(0, Number(value) || 0));
  }

  function renderUsage() {
    if (!usage) {
      usageLabel.textContent = 'Usage today';
      usageValue.textContent = 'Loading…';
      usageDetail.textContent = 'Using Vigzone\'s verified quota service';
      usageFill.style.width = '0%';
      usageTrack.setAttribute('aria-valuenow', '0');
      return;
    }
    if (usage.tracking_error) {
      usageLabel.textContent = 'Usage service';
      usageValue.textContent = 'Unavailable';
      usageDetail.textContent = 'Provider calls remain protected from untracked use';
      usageFill.style.width = '0%';
      usageTrack.setAttribute('aria-valuenow', '0');
      return;
    }
    if (usage.mode === 'testing') {
      usageLabel.textContent = 'Usage tracking';
      usageValue.textContent = 'Testing';
      usageDetail.textContent = 'Daily tracking is disabled in testing mode';
      usageFill.style.width = '0%';
      usageTrack.setAttribute('aria-valuenow', '0');
      return;
    }
    const stats = usageNumbers(usage);
    usageLabel.textContent = usage.quota_label || `${PLAN_PRESENTATION[plan].label} usage`;
    usageValue.textContent = stats.unlimited ? 'Unlimited' : `${Math.round(stats.percent)}% used`;
    usageDetail.textContent = stats.unlimited
      ? `${stats.used.toLocaleString()} tokens recorded today · no daily cap`
      : `${compactNumber(stats.remaining)} tokens left of ${compactNumber(stats.limit)}`;
    usageFill.style.width = `${stats.percent}%`;
    usageTrack.setAttribute('aria-valuenow', String(Math.round(stats.percent)));
    usageTrack.setAttribute('aria-valuetext', stats.unlimited ? 'Unlimited' : `${Math.round(stats.percent)} percent used`);
  }

  function effectiveState() {
    if (!navigator.onLine) return 'offline';
    if (usage?.tracking_error) return 'warning';
    if (usage?.is_limited) return 'limited';
    return ['thinking', 'coding', 'complete', 'error'].includes(activity) ? activity : 'ready';
  }

  function codingStatusCopy() {
    const count = Math.max(0, Number(activityDetail.fileCount || 0));
    const fileCopy = count ? ` ${count} file${count === 1 ? '' : 's'}` : '';
    return {
      reading: `Vigi is reading the selected project files and mapping the code…`,
      analyzing: `Vigi is tracing logic across${fileCopy || ' the project'}…`,
      editing: `Vigi is planning focused edits across${fileCopy || ' the project'}…`,
      generating: 'Vigi is building and checking the code response…',
      writing: `Vigi is writing${fileCopy || ' reviewed changes'} to the approved project folder…`
    }[activityDetail.phase] || 'Vigi is focused on the code…';
  }

  function completionStatusCopy() {
    const count = Math.max(0, Number(activityDetail.fileCount || 0));
    if (activityDetail.phase === 'applied') {
      return `Vigi saved ${count || 'the'} reviewed file change${count === 1 ? '' : 's'} successfully.`;
    }
    if (activityDetail.phase === 'reviewed' && count) {
      return `Vigi finished the project review. ${count} proposed file change${count === 1 ? '' : 's'} ${count === 1 ? 'is' : 'are'} ready for your approval.`;
    }
    if (activityDetail.phase === 'analyzed') return 'Vigi finished analyzing the project. No file edits were proposed.';
    return 'Vigi finished the coding task. The result is ready to review.';
  }

  function syncWorkBadge(state) {
    if (!workBadge || !workLabel) return;
    const labels = {
      coding: activityDetail.phase === 'writing' ? 'Writing files' : 'Coding',
      complete: 'Code ready',
      error: 'Coding stopped'
    };
    workLabel.textContent = labels[state] || '';
    workBadge.setAttribute('aria-hidden', labels[state] ? 'false' : 'true');
  }

  function renderStatus() {
    const state = effectiveState();
    companion.dataset.state = state;
    const presentation = PLAN_PRESENTATION[plan];
    const copy = {
      offline: 'Vigi is offline. Saved chats remain available on this device.',
      warning: 'Vigi cannot verify usage right now. Limited plans stay protected.',
      limited: 'Your daily Vigzone quota is used. Vigi will be ready after the reset.',
      thinking: 'Vigi is working on your request…',
      coding: codingStatusCopy(),
      complete: completionStatusCopy(),
      error: 'Vigi could not finish that coding operation. Your existing project files remain protected.',
      ready: presentation.ready
    }[state];
    syncWorkBadge(state);
    statusCopy.textContent = copy;
    petState.textContent = state === 'thinking'
      ? 'Vigi is thinking'
      : state === 'coding'
        ? `Vigi is coding: ${activityDetail.phase || 'working'}`
        : `Vigi is ${state}`;
    petButton.setAttribute('aria-label', `${presentation.label} Vigi · ${copy}`);
  }

  function positionPopover() {
    if (popover.hidden) return;
    const petRect = petButton.getBoundingClientRect();
    const width = Math.min(320, window.innerWidth - 24);
    popover.style.width = `${width}px`;
    popover.style.left = `${Math.max(12, Math.min(window.innerWidth - width - 12, petRect.right - width))}px`;
    const height = popover.getBoundingClientRect().height;
    const preferredTop = petRect.top - height - 8;
    const top = preferredTop >= 12
      ? preferredTop
      : Math.min(window.innerHeight - height - 12, petRect.bottom + 8);
    popover.style.top = `${Math.max(12, top)}px`;
  }

  function openPopover() {
    if (!enabled || !desktopMedia.matches) return;
    popover.hidden = false;
    companion.classList.add('is-open');
    petButton.setAttribute('aria-expanded', 'true');
    positionPopover();
    popoverClose?.focus({preventScroll:true});
  }

  function closePopover() {
    popover.hidden = true;
    companion.classList.remove('is-open');
    petButton.setAttribute('aria-expanded', 'false');
  }

  function togglePopover() {
    if (popover.hidden) openPopover();
    else closePopover();
  }

  function clickRealControl(id) {
    const target = document.getElementById(id);
    if (!target || target.disabled) return false;
    target.click();
    return true;
  }

  function runAction(name) {
    closePopover();
    if (name === 'ask') {
      const input = document.getElementById('input');
      input?.focus({preventScroll:false});
      input?.scrollIntoView({behavior:'smooth', block:'center'});
      return;
    }
    if (name === 'projects') {
      clickRealControl('workspaceSidebarBtn');
      return;
    }
    if (name === 'usage') {
      clickRealControl('usageTodayBtn');
      return;
    }
    if (name === 'plan') clickRealControl(planAction.dataset.target);
  }

  function acceptAccount(detail) {
    userId = detail?.userId || window._vigzoneUserId || null;
    plan = normalizedPlan(detail);
    entitlements = detail?.entitlements || window._vigzoneEntitlements || {};
    accountReady = !!userId;
    enabled = readEnabled();
    restorePosition();
    syncSettingsToggle();
    syncPlan();
    renderUsage();
    syncVisibility();
  }

  document.addEventListener('vigzone:account', event => acceptAccount(event.detail || {}));
  document.addEventListener('vigzone:usage', event => {
    usage = event.detail?.usage || null;
    renderUsage();
    renderStatus();
  });
  document.addEventListener('vigzone:activity', event => {
    window.clearTimeout(terminalStateTimer);
    const nextState = String(event.detail?.state || 'ready');
    activity = ['thinking', 'coding', 'complete', 'error'].includes(nextState) ? nextState : 'ready';
    activityDetail = event.detail || {};
    renderStatus();
    if (activity === 'complete' || activity === 'error') {
      const terminalState = activity;
      terminalStateTimer = window.setTimeout(() => {
        if (activity !== terminalState) return;
        activity = 'ready';
        activityDetail = {};
        renderStatus();
      }, activity === 'complete' ? 4400 : 5200);
    }
  });

  settingsToggle?.addEventListener('click', () => setEnabled(!enabled));
  popoverClose?.addEventListener('click', closePopover);
  actions?.addEventListener('click', event => {
    const button = event.target.closest('[data-vigi-action]');
    if (button) runAction(button.dataset.vigiAction);
  });
  document.addEventListener('pointerdown', event => {
    if (!popover.hidden && !companion.contains(event.target)) closePopover();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !popover.hidden) {
      closePopover();
      petButton.focus({preventScroll:true});
    }
  });

  let drag = null;
  petButton.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    const rect = petButton.getBoundingClientRect();
    drag = {pointerId:event.pointerId, startX:event.clientX, startY:event.clientY, left:rect.left, top:rect.top, moved:false};
    petButton.setPointerCapture?.(event.pointerId);
  });
  petButton.addEventListener('pointermove', event => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    drag.moved = true;
    companion.classList.add('is-dragging');
    applyPosition({left:drag.left + dx, top:drag.top + dy});
    event.preventDefault();
  });
  function finishDrag(event) {
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.moved) {
      suppressNextClick = true;
      savePosition();
    }
    companion.classList.remove('is-dragging');
    drag = null;
  }
  petButton.addEventListener('pointerup', finishDrag);
  petButton.addEventListener('pointercancel', finishDrag);
  petButton.addEventListener('click', event => {
    if (suppressNextClick) {
      suppressNextClick = false;
      event.preventDefault();
      return;
    }
    togglePopover();
  });

  window.addEventListener('online', renderStatus);
  window.addEventListener('offline', renderStatus);
  window.addEventListener('resize', () => {
    if (companion.style.left) {
      const rect = petButton.getBoundingClientRect();
      applyPosition({left:rect.left, top:rect.top});
      savePosition();
    }
    positionPopover();
  });
  desktopMedia.addEventListener?.('change', syncVisibility);

  // The account request is asynchronous, but this also covers cached/immediate auth responses.
  window.setTimeout(() => {
    if (!accountReady && window._vigzoneUserId) {
      acceptAccount({
        userId:window._vigzoneUserId,
        effectivePlan:window._vigzoneUserPlan,
        displayPlan:window._vigzoneUserIsAdmin ? 'admin' : window._vigzoneUserPlan,
        isAdmin:!!window._vigzoneUserIsAdmin,
        entitlements:window._vigzoneEntitlements || {}
      });
    }
  }, 0);
})();
