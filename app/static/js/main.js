(() => {
  let tickerTimeoutId = null;
  let ajaxNavigationInitialized = false;

  const formatPhoneNumber = (value) => {
    const digits = String(value || '').replace(/\D/g, '').slice(0, 11);
    if (digits.length <= 3) return digits;
    if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  };

  const mapAlertToToastVariant = (alertClass) => {
    const variant = (alertClass || '').replace('alert-', '');
    if (variant === 'danger') return 'danger';
    if (variant === 'warning') return 'warning';
    if (variant === 'success') return 'success';
    return 'primary';
  };

  const showToast = (message, variant = 'primary') => {
    const container = document.getElementById('appToastContainer');
    if (!container || !window.bootstrap) return;

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${variant} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="닫기"></button>
      </div>
    `;
    container.appendChild(toast);

    const instance = new bootstrap.Toast(toast, { delay: 2600 });
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
    instance.show();
  };

  const showFlashesAsToasts = (root = document) => {
    const flashStack = root.querySelector('[data-flash-stack]');
    if (!flashStack) return;

    flashStack.querySelectorAll('.alert').forEach((alert) => {
      const alertClass = Array.from(alert.classList).find((name) => name.startsWith('alert-') && name !== 'alert');
      showToast(alert.textContent.trim(), mapAlertToToastVariant(alertClass));
    });
    flashStack.remove();
  };

  const initPhoneInputs = (root = document) => {
    root.querySelectorAll('input[name="phone"]').forEach((input) => {
      if (input.dataset.phoneBound === 'true') return;
      input.dataset.phoneBound = 'true';

      input.addEventListener('input', (event) => {
        event.target.value = formatPhoneNumber(event.target.value);
      });

      input.addEventListener('blur', (event) => {
        event.target.value = formatPhoneNumber(event.target.value);
      });
    });
  };

  const initTickerBoard = (root = document) => {
    const board = root.querySelector('[data-ticker-board]');
    if (!board) return;

    if (tickerTimeoutId) {
      clearTimeout(tickerTimeoutId);
      tickerTimeoutId = null;
    }

    const items = Array.from(board.querySelectorAll('[data-ticker-item]'));
    if (items.length <= 1) return;

    const showItem = (index) => {
      items.forEach((item, itemIndex) => item.classList.toggle('is-active', itemIndex === index));
      const seconds = parseInt(items[index].dataset.displaySeconds || '3', 10);
      tickerTimeoutId = window.setTimeout(() => {
        showItem((index + 1) % items.length);
      }, Math.max(seconds, 1) * 1000);
    };

    showItem(0);
  };

  const initInlineConsentPanels = (root = document) => {
    root.querySelectorAll('.js-open-consent-panel').forEach((button) => {
      if (button.dataset.bound === 'true') return;
      button.dataset.bound = 'true';
      button.addEventListener('click', () => {
        const target = document.getElementById(button.dataset.consentTarget);
        if (target) target.classList.remove('d-none');
      });
    });

    root.querySelectorAll('.js-confirm-inline-consent').forEach((button) => {
      if (button.dataset.bound === 'true') return;
      button.dataset.bound = 'true';
      button.addEventListener('click', () => {
        const panel = button.closest('.consent-panel');
        if (!panel) return;
        const detailBox = panel.querySelector('.consent-detail-box');
        const openButton = panel.querySelector('.js-open-consent-panel');
        const checkbox = panel.querySelector('.js-consent-checkbox');
        const submitButtons = panel.closest('form')?.querySelectorAll('.js-consent-submit');
        const status = panel.querySelector('.js-consent-status');
        if (checkbox) checkbox.checked = true;
        submitButtons?.forEach((btn) => (btn.disabled = false));
        if (status) status.textContent = '동의 완료';
        if (openButton) {
          openButton.textContent = '동의완료';
          openButton.classList.remove('btn-outline-primary');
          openButton.classList.add('btn-success');
        }
        if (detailBox) detailBox.classList.add('d-none');
      });
    });
  };

  const initPaymentRequestConsentModal = (root = document) => {
    const consentModalEl = root.querySelector('#privacyConsentModal');
    if (!consentModalEl) return;
    if (consentModalEl.dataset.bound === 'true') return;
    consentModalEl.dataset.bound = 'true';

    let currentConsentButton = null;
    root.querySelectorAll('.js-open-consent-modal').forEach((button) => {
      button.addEventListener('click', () => {
        currentConsentButton = button;
      });
    });

    const confirmBtn = consentModalEl.querySelector('#privacyConsentConfirmBtn');
    confirmBtn?.addEventListener('click', () => {
      if (!currentConsentButton) return;
      const panel = currentConsentButton.closest('.consent-panel');
      const checkbox = panel?.querySelector('.js-consent-checkbox');
      const submitButtons = panel?.closest('form')?.querySelectorAll('.js-consent-submit');
      const status = panel?.querySelector('.js-consent-status');
      if (checkbox) checkbox.checked = true;
      submitButtons?.forEach((btn) => (btn.disabled = false));
      if (status) status.textContent = '동의 완료';
      currentConsentButton.textContent = '동의완료';
      currentConsentButton.classList.remove('btn-outline-primary');
      currentConsentButton.classList.add('btn-success');
      bootstrap.Modal.getOrCreateInstance(consentModalEl).hide();
    });
  };

  const initPasswordForms = (root = document) => {
    root.querySelectorAll('.password-form').forEach((form) => {
      if (form.dataset.bound === 'true') return;
      form.dataset.bound = 'true';

      const input = form.querySelector('.password-input');
      const button = form.querySelector('.random-password-btn');
      if (!button || !input) return;

      button.addEventListener('click', async () => {
        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = '생성중...';

        try {
          const response = await fetch(button.dataset.url || '/forie_admin/passwords/generate', {
            method: 'GET',
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.error || '랜덤 비밀번호 생성에 실패했습니다.');
          }
          input.value = data.password || '';
          showToast('랜덤 비밀번호가 생성되었습니다.', 'success');
        } catch (error) {
          showToast(error.message || '랜덤 비밀번호 생성에 실패했습니다.', 'danger');
        } finally {
          button.disabled = false;
          button.textContent = originalText;
        }
      });
    });
  };

  const initCopyButtons = (root = document) => {
    root.querySelectorAll('.js-copy-account-number').forEach((button) => {
      if (button.dataset.bound === 'true') return;
      button.dataset.bound = 'true';

      button.addEventListener('click', async () => {
        const accountNumber = (button.dataset.accountNumber || '').replace(/\D/g, '');
        const input = button.closest('.input-group')?.querySelector('.js-copy-account-number-input');
        if (!accountNumber) {
          showToast('복사할 계좌번호가 없습니다.', 'warning');
          return;
        }

        if (input) {
          input.focus();
          input.removeAttribute('readonly');
          input.select();
          input.setSelectionRange(0, input.value.length);
          input.setAttribute('readonly', 'readonly');
        }

        try {
          if (window.isSecureContext && navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(accountNumber);
          } else {
            const tempInput = document.createElement('textarea');
            tempInput.value = accountNumber;
            tempInput.setAttribute('readonly', '');
            tempInput.setAttribute('aria-hidden', 'true');
            tempInput.style.position = 'fixed';
            tempInput.style.top = '0';
            tempInput.style.left = '0';
            tempInput.style.width = '1px';
            tempInput.style.height = '1px';
            tempInput.style.padding = '0';
            tempInput.style.border = '0';
            tempInput.style.opacity = '0';
            tempInput.style.pointerEvents = 'none';
            document.body.appendChild(tempInput);
            tempInput.focus();
            tempInput.select();
            tempInput.setSelectionRange(0, tempInput.value.length);

            const copied = document.execCommand('copy');
            tempInput.remove();

            if (!copied) {
              throw new Error('execCommand copy failed');
            }
          }
          showToast('계좌번호가 복사되었습니다.', 'success');
        } catch (error) {
          if (input) {
            input.focus();
            input.select();
            input.setSelectionRange(0, input.value.length);
          }
          showToast('자동 복사가 어려우면 숫자를 길게 눌러 복사해주세요.', 'warning');
        }
      });
    });
  };

  const initMonthSelection = (root = document) => {
    const monthChips = root.querySelectorAll('.js-month-chip');
    if (!monthChips.length) return;

    const slotCard = root.querySelector('.slot-card');
    const slotCardTarget = slotCard?.querySelector('.section-title');
    const slotMeta = slotCard?.querySelector('.slot-meta');
    const reservationButton = root.querySelector('[data-bs-target="#reservationApplyModal"]');
    const slotSectionTitle = root.querySelector('.js-slot-section-title');
    const slotHeroTitle = root.querySelector('.js-slot-hero-title');
    const slotStatus = root.querySelector('.js-slot-status');
    const slotReserved = root.querySelector('.js-slot-reserved');
    const slotCapacity = root.querySelector('.js-slot-capacity');
    const slotConfirmed = root.querySelector('.js-slot-confirmed');
    const slotCapacitySecondary = root.querySelector('.js-slot-capacity-secondary');
    const slotOpenDate = root.querySelector('.js-slot-open-date');
    const slotCloseDate = root.querySelector('.js-slot-close-date');
    const slotPeriod = root.querySelector('.js-slot-period');
    const slotUrgency = root.querySelector('.js-slot-urgency');
    const monthDetailUrl = (id) => `/api/month/${id}`;
    const statusBadgeClass = (status) => `status-${status?.toLowerCase() || 'inactive'}`;
    const urgencyBadgeClass = (label) => {
      if (label === '정원마감') return 'is-danger';
      if (label === '정원임박') return 'is-warning';
      return 'is-deadline';
    };
    const renderUrgencyBadges = (labels = []) => labels
      .map((label) => `<span class="urgency-badge ${urgencyBadgeClass(label)}">${label}</span>`)
      .join('');
    const syncUrgencyContainer = (container, labels = []) => {
      if (!container) return;
      if (!labels.length) {
        container.innerHTML = '';
        container.classList.add('d-none');
        return;
      }
      container.innerHTML = renderUrgencyBadges(labels);
      container.classList.remove('d-none');
    };

    const updateSlotCard = (payload) => {
      if (!slotCard) return;
      if (slotCardTarget) slotCardTarget.textContent = `${payload.target_month} 월 이용 신청`;
      if (slotSectionTitle) slotSectionTitle.textContent = `${payload.target_month} 이용 안내`;
      if (slotHeroTitle) slotHeroTitle.textContent = `${payload.target_month} 월 이용 신청`;
      if (slotMeta) slotMeta.textContent = `운영 상태: ${payload.status_label}`;
      if (slotStatus) slotStatus.textContent = `운영 상태: ${payload.status_label}`;
      if (slotReserved) slotReserved.textContent = payload.slot_reserved ?? 0;
      if (slotCapacity) slotCapacity.textContent = payload.slot_capacity ?? 0;
      if (slotConfirmed) slotConfirmed.textContent = payload.slot_confirmed ?? 0;
      if (slotCapacitySecondary) slotCapacitySecondary.textContent = payload.slot_capacity ?? 0;
      if (slotOpenDate) slotOpenDate.textContent = payload.open_date_display || '-';
      if (slotCloseDate) slotCloseDate.textContent = payload.close_date_display || '-';
      if (slotPeriod) slotPeriod.textContent = payload.reservation_period_display || '-';
      syncUrgencyContainer(slotUrgency, payload.urgency_labels || []);
      if (reservationButton) reservationButton.disabled = Boolean(payload.reservation_disabled);
      slotCard.dataset.monthId = payload.id;

      const modalTitle = root.querySelector('#reservationApplyModal .modal-title');
      const monthInput = root.querySelector('#reservationApplyModal input[name="month_id"]');
      const slotInput = root.querySelector('#reservationApplyModal input[name="slot_id"]');
      if (modalTitle) modalTitle.textContent = `${payload.target_month} 예약 신청`;
      if (monthInput) monthInput.value = payload.id;
      if (slotInput) slotInput.value = payload.slot_id || '';
    };

    const updateChipDetails = (chip, payload) => {
      const badge = chip.querySelector('.status-badge');
      if (badge) {
        badge.className = 'status-badge';
        badge.classList.add(statusBadgeClass(payload.status_variant || payload.status));
        badge.textContent = payload.status_label;
      }
      const reserved = chip.querySelector('.js-chip-reserved');
      const capacity = chip.querySelector('.js-chip-capacity');
      const confirmed = chip.querySelector('.js-chip-confirmed');
      const capacitySecondary = chip.querySelector('.js-chip-capacity-secondary');
      const openDate = chip.querySelector('.js-chip-open-date');
      const closeDate = chip.querySelector('.js-chip-close-date');
      const urgency = chip.querySelector('.js-chip-urgency');
      if (reserved) reserved.textContent = payload.slot_reserved ?? 0;
      if (capacity) capacity.textContent = payload.slot_capacity ?? 0;
      if (confirmed) confirmed.textContent = payload.slot_confirmed ?? 0;
      if (capacitySecondary) capacitySecondary.textContent = payload.slot_capacity ?? 0;
      if (openDate) openDate.textContent = payload.open_date_display || '-';
      if (closeDate) closeDate.textContent = payload.close_date_display || '-';
      syncUrgencyContainer(urgency, payload.urgency_labels || []);
    };

    const updateChips = (payload) => {
      monthChips.forEach((chip) => {
        const chipId = Number(chip.dataset.monthId);
        if (chipId === payload.id) {
          chip.classList.add('is-active');
          updateChipDetails(chip, payload);
        } else {
          chip.classList.remove('is-active');
        }
      });
    };

    monthChips.forEach((chip) => {
      if (chip.dataset.bound === 'true') return;
      chip.dataset.bound = 'true';
      chip.addEventListener('click', async (event) => {
        event.preventDefault();
        const monthId = chip.dataset.monthId;
        if (!monthId) return;

        try {
          const response = await fetch(monthDetailUrl(monthId), {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          });
          if (!response.ok) throw new Error('월 정보를 불러오지 못했습니다.');
          const payload = await response.json();
          updateSlotCard(payload);
          updateChips(payload);
          history.replaceState(null, '', `/?month_id=${payload.id}`);
        } catch (error) {
          showToast(error.message || '월 정보를 불러오지 못했습니다.', 'danger');
        }
      });
    });
  };

  const shouldHandleLinkWithAjax = (link, event) => {
    if (!link) return false;
    if (event.defaultPrevented) return false;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
    if (link.target && link.target !== '_self') return false;
    if (link.dataset.noAjax === 'true') return false;
    if (link.hasAttribute('download')) return false;
    if (link.dataset.bsToggle) return false;

    const href = link.getAttribute('href') || '';
    if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) {
      return false;
    }

    const url = new URL(link.href, window.location.origin);
    if (url.origin !== window.location.origin) return false;
    if (url.pathname.includes('/export')) return false;
    return true;
  };

  const cleanupModalArtifacts = () => {
    document.querySelectorAll('.modal.show').forEach((modalEl) => {
      try {
        const instance = window.bootstrap?.Modal.getInstance(modalEl);
        instance?.hide();
      } catch (error) {
        console.warn('Failed to hide modal instance:', error);
      }

      modalEl.classList.remove('show');
      modalEl.setAttribute('aria-hidden', 'true');
      if (modalEl.style.display === 'block') {
        modalEl.style.display = 'none';
      }
    });

    document.querySelectorAll('.modal-backdrop').forEach((backdrop) => backdrop.remove());
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
  };

  const replaceAppShellFromHtml = (html, targetUrl, { pushState = true } = {}) => {
    const parser = new DOMParser();
    const nextDocument = parser.parseFromString(html, 'text/html');
    const nextShell = nextDocument.querySelector('#app-shell');
    const currentShell = document.querySelector('#app-shell');

    if (!nextShell || !currentShell) {
      window.location.href = targetUrl;
      return;
    }

    cleanupModalArtifacts();
    currentShell.replaceWith(nextShell);
    document.title = nextDocument.title || document.title;
    if (pushState) {
      history.pushState({}, '', targetUrl);
    }
    initPage(document);
  };

  const performAjaxNavigation = async (url, options = {}) => {
    const response = await fetch(url, {
      ...options,
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        ...(options.headers || {}),
      },
    });

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('text/html')) {
      const html = await response.text();
      replaceAppShellFromHtml(html, response.url, { pushState: options.pushState !== false });
      return;
    }

    if (contentType.includes('application/json')) {
      return response.json();
    }

    window.location.href = response.url || url;
  };

  const initAjaxNavigation = () => {
    if (ajaxNavigationInitialized) return;
    ajaxNavigationInitialized = true;

    document.addEventListener('click', async (event) => {
      const link = event.target.closest('a[href]');
      if (!shouldHandleLinkWithAjax(link, event)) return;
      event.preventDefault();

      try {
        await performAjaxNavigation(link.href);
      } catch (error) {
        showToast(error.message || '페이지를 불러오지 못했습니다.', 'danger');
      }
    });

    document.addEventListener('submit', async (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (form.dataset.noAjax === 'true' || form.dataset.ajax !== 'true') return;

      const submitter = event.submitter || document.activeElement;
      const action = submitter?.formAction || form.action || window.location.href;
      const method = (submitter?.formMethod || form.method || 'GET').toUpperCase();
      if (new URL(action, window.location.origin).origin !== window.location.origin) return;

      event.preventDefault();

      try {
        const formData = new FormData(form);
        if (submitter?.name) {
          formData.append(submitter.name, submitter.value || '');
        }

        if (method === 'GET') {
          const query = new URLSearchParams(formData).toString();
          const separator = action.includes('?') ? '&' : '?';
          await performAjaxNavigation(`${action}${query ? separator + query : ''}`);
          return;
        }

        await performAjaxNavigation(action, {
          method,
          body: formData,
        });
      } catch (error) {
        showToast(error.message || '요청 처리 중 오류가 발생했습니다.', 'danger');
      }
    });

    window.addEventListener('popstate', async () => {
      try {
        await performAjaxNavigation(window.location.href, { pushState: false });
      } catch (error) {
        showToast(error.message || '페이지를 불러오지 못했습니다.', 'danger');
      }
    });
  };

  const initPage = (root = document) => {
    initPhoneInputs(root);
    initTickerBoard(root);
    initInlineConsentPanels(root);
    initPaymentRequestConsentModal(root);
    initPasswordForms(root);
    initCopyButtons(root);
    initMonthSelection(root);
    showFlashesAsToasts(root);
  };

  document.addEventListener('DOMContentLoaded', () => {
    initPage(document);
    initAjaxNavigation();
  });
})();