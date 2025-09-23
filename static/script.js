// static/script.js
document.addEventListener('DOMContentLoaded', () => {
  /* ====== NAV / BURGER ====== */
  const burger = document.getElementById('burger-menu');
  const nav = document.getElementById('main-nav');

  const closeNav = () => {
    if (!nav) return;
    nav.classList.remove('is-open');
    if (burger) {
      burger.classList.remove('is-open');
      burger.setAttribute('aria-expanded', 'false');
    }
  };

  if (burger && nav) {
    burger.addEventListener('click', () => {
      const isOpen = nav.classList.toggle('is-open');
      burger.classList.toggle('is-open', isOpen);
      burger.setAttribute('aria-expanded', String(isOpen));
    });

    // Закрыть по клику на ссылку
    nav.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', closeNav);
    });

    // Клик вне меню
    document.addEventListener('click', (e) => {
      if (!nav.classList.contains('is-open')) return;
      const clickInsideNav = nav.contains(e.target);
      const clickBurger = burger.contains(e.target);
      if (!clickInsideNav && !clickBurger) closeNav();
    });

    // Esc
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeNav();
    });
  }

  /* ====== MODAL ====== */
  const modal = document.getElementById('modal-signup');
  const openBtns = document.querySelectorAll('.js-open-modal');
  let lastFocused = null;

  const getFocusable = (root) =>
    root.querySelectorAll('a, button, input, textarea, select, [tabindex]:not([tabindex="-1"])');

  const openModal = () => {
    if (!modal) return;
    lastFocused = document.activeElement;
    modal.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    // Фокус на первый интерактивный элемент
    const focusables = getFocusable(modal);
    if (focusables.length) focusables[0].focus();
  };

  const closeModal = () => {
    if (!modal) return;
    modal.classList.remove('is-open');
    document.body.style.overflow = '';
    if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus();
  };

  if (modal) {
    // Открыть
    openBtns.forEach(btn => btn.addEventListener('click', (e) => {
      e.preventDefault();
      openModal();
    }));

    // Закрыть по Х
    const closeBtn = modal.querySelector('.close-modal');
    if (closeBtn) closeBtn.addEventListener('click', closeModal);

    // Клик по фону
    modal.addEventListener('click', (e) => {
      const win = modal.querySelector('.modal-window');
      if (!win || win.contains(e.target)) return;
      closeModal();
    });

    // Esc и trap фокуса
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeModal();
      } else if (e.key === 'Tab') {
        // Трап фокуса
        const focusables = Array.from(getFocusable(modal));
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault(); last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault(); first.focus();
        }
      }
    });
  }
});
// ===== YouTube: вставка iframe по клику (поддержка .video-wrap[data-yt] и .js-yt[data-yt]) =====
const mountYouTubeIframe = (wrap) => {
  const id = wrap.getAttribute('data-yt');
  if (!id) return;
  const iframe = document.createElement('iframe');
  iframe.setAttribute('loading', 'lazy');
  iframe.setAttribute('allowfullscreen', '');
  iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
  iframe.setAttribute(
    'allow',
    'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share'
  );
  iframe.src = `https://www.youtube-nocookie.com/embed/${id}?rel=0&autoplay=1`;
  iframe.style.position = 'absolute';
  iframe.style.inset = '0';
  iframe.style.width = '100%';
  iframe.style.height = '100%';
  iframe.style.border = '0';
  // Очищаем превью и вставляем iframe прямо в текущий контейнер
  wrap.innerHTML = '';
  // Гарантируем, что контейнер имеет нужные стили (если это <a>, они уже есть в CSS)
  wrap.classList.add('video-wrap');
  wrap.style.position = 'relative';
  wrap.style.aspectRatio = '16 / 9';
  wrap.appendChild(iframe);
};

// Клик мышью
document.addEventListener('click', (e) => {
  const wrap = e.target.closest('.video-wrap[data-yt], .js-yt[data-yt]');
  if (!wrap) return;
  e.preventDefault();
  mountYouTubeIframe(wrap);
});

// Доступность — запуск по Enter/Space
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const wrap = document.activeElement?.closest?.('.video-wrap[data-yt], .js-yt[data-yt]');
  if (!wrap) return;
  e.preventDefault();
  mountYouTubeIframe(wrap);
});
