(() => {
  if (window.__comicTranslator) return;
  window.__comicTranslator = true;

  const MIN_SIDE = 250;      // меньшие картинки (иконки, аватарки) не трогаем
  const PARALLEL = 2;        // сколько картинок одновременно отправлять на сервер

  const state = new Map();   // img -> { original, originalSrcset, translated, status }
  let toastEl = null;
  let toastTimer = null;

  function toast(text, ms = 3000) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'ct-toast';
      document.documentElement.appendChild(toastEl);
    }
    toastEl.textContent = text;
    toastEl.style.display = 'block';
    clearTimeout(toastTimer);
    if (ms) toastTimer = setTimeout(() => { toastEl.style.display = 'none'; }, ms);
  }

  function badge(img, text, isError = false) {
    let b = img.__ctBadge;
    if (!b) {
      b = document.createElement('div');
      b.className = 'ct-badge';
      document.body.appendChild(b);
      img.__ctBadge = b;
    }
    const r = img.getBoundingClientRect();
    b.style.left = `${r.left + window.scrollX + 8}px`;
    b.style.top = `${r.top + window.scrollY + 8}px`;
    b.textContent = text;
    b.classList.toggle('ct-error', isError);
  }

  function removeBadge(img) {
    img.__ctBadge?.remove();
    img.__ctBadge = null;
  }

  function isComicImage(img) {
    if (!img.complete || !img.currentSrc) return false;
    if (img.naturalWidth < MIN_SIDE || img.naturalHeight < MIN_SIDE) return false;
    const r = img.getBoundingClientRect();
    return r.width >= 150 && r.height >= 150;
  }

  // Сначала то, что видно на экране, потом остальное сверху вниз
  function sortByPriority(imgs) {
    const vh = window.innerHeight;
    return imgs.sort((a, b) => {
      const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
      const va = ra.bottom > 0 && ra.top < vh ? 0 : 1;
      const vb = rb.bottom > 0 && rb.top < vh ? 0 : 1;
      return va - vb || (ra.top - rb.top);
    });
  }

  async function srcForServer(img) {
    const src = img.currentSrc || img.src;
    if (!src.startsWith('blob:')) return src;
    // blob: доступен только на самой странице — превращаем в data:
    const blob = await (await fetch(src)).blob();
    return await new Promise((resolve) => {
      const fr = new FileReader();
      fr.onload = () => resolve(fr.result);
      fr.readAsDataURL(blob);
    });
  }

  async function translateImage(img) {
    const st = state.get(img) || {};
    if (st.status === 'busy') return;
    if (st.translated) { showTranslated(img); return; }

    st.original = img.currentSrc || img.src;
    st.originalSrcset = img.getAttribute('srcset');
    st.status = 'busy';
    state.set(img, st);
    img.classList.add('ct-busy');
    badge(img, 'Перевожу…');

    try {
      const res = await chrome.runtime.sendMessage({ type: 'translate', src: await srcForServer(img) });
      if (!res?.ok) throw new Error(res?.error || 'неизвестная ошибка');
      st.translated = res.dataUrl;
      st.status = 'done';
      showTranslated(img);
      removeBadge(img);
    } catch (e) {
      st.status = 'error';
      badge(img, `Ошибка: ${e.message}`, true);
      setTimeout(() => removeBadge(img), 8000);
    } finally {
      img.classList.remove('ct-busy');
    }
  }

  function showTranslated(img) {
    const st = state.get(img);
    if (st.originalSrcset !== null) img.removeAttribute('srcset');
    img.src = st.translated;
    st.shown = 'translated';
  }

  function showOriginal(img) {
    const st = state.get(img);
    img.src = st.original;
    if (st.originalSrcset !== null) img.setAttribute('srcset', st.originalSrcset);
    st.shown = 'original';
  }

  async function runQueue(imgs) {
    let done = 0;
    const total = imgs.length;
    toast(`Перевожу картинки: 0 из ${total}`, 0);
    const queue = [...imgs];
    const worker = async () => {
      while (queue.length) {
        await translateImage(queue.shift());
        done++;
        toast(`Перевожу картинки: ${done} из ${total}`, done === total ? 3000 : 0);
      }
    };
    await Promise.all(Array.from({ length: Math.min(PARALLEL, total) }, worker));
    const errors = imgs.filter((i) => state.get(i)?.status === 'error').length;
    toast(errors ? `Готово, с ошибками: ${errors} из ${total}` : `Готово: переведено ${total}`);
  }

  function toggle() {
    const all = [...document.images];
    const fresh = all.filter((img) => isComicImage(img) && !state.has(img));
    const shownOriginal = all.filter((img) => state.get(img)?.shown === 'original');
    const shownTranslated = all.filter((img) => state.get(img)?.shown === 'translated');

    if (fresh.length) {
      shownOriginal.forEach(showTranslated);
      runQueue(sortByPriority(fresh));
    } else if (shownOriginal.length) {
      shownOriginal.forEach(showTranslated);
      toast('Показываю перевод');
    } else if (shownTranslated.length) {
      shownTranslated.forEach(showOriginal);
      toast('Показываю оригинал (Alt+T — снова перевод)');
    } else if (window === window.top) {
      toast('Не нашёл на странице картинок комикса');
    }
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === 'toggle') toggle();
    if (msg.type === 'translate-one') {
      const img = [...document.images].find((i) => (i.currentSrc || i.src) === msg.src);
      if (img) runQueue([img]);
    }
  });
})();
