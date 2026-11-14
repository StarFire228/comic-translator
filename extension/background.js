const SERVER = 'http://127.0.0.1:8000';

// Настройки перевода для manga-image-translator
const CONFIG = {
  translator: { translator: 'custom_openai', target_lang: 'RUS' },
  detector: { detector: 'default', detection_size: 2048 },
  inpainter: { inpainter: 'lama_large', inpainting_size: 2048 },
  // alignment: 'left' — для блоков текста (карточки, описания); для облачков комиксов лучше 'center'
  render: { renderer: 'default', direction: 'horizontal', alignment: 'left' },
  ocr: { ocr: '48px' },
  // Апскейл x2 перед распознаванием: мелкие картинки читаются точнее, шрифт крупнее и чётче
  upscale: { upscaler: 'esrgan', upscale_ratio: 2, revert_upscaling: true },
  mask_dilation_offset: 20,
};

function sendToTab(tabId, message) {
  chrome.tabs.sendMessage(tabId, message).catch(() => {});
}

chrome.action.onClicked.addListener((tab) => sendToTab(tab.id, { type: 'toggle' }));

chrome.commands.onCommand.addListener((command, tab) => {
  if (command === 'translate-page' && tab) sendToTab(tab.id, { type: 'toggle' });
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: 'translate-image', title: 'Перевести эту картинку', contexts: ['image'] });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'translate-image') {
    sendToTab(tab.id, { type: 'translate-one', src: info.srcUrl });
  }
});

async function blobToDataUrl(blob) {
  const buf = new Uint8Array(await blob.arrayBuffer());
  let bin = '';
  for (let i = 0; i < buf.length; i += 0x8000) {
    bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  }
  return `data:${blob.type || 'image/png'};base64,${btoa(bin)}`;
}

async function translate(src, pageUrl) {
  let imgBlob;
  if (src.startsWith('data:')) {
    imgBlob = await (await fetch(src)).blob();
  } else {
    const resp = await fetch(src, { credentials: 'include' });
    if (!resp.ok) throw new Error(`Не удалось скачать картинку: HTTP ${resp.status}`);
    imgBlob = await resp.blob();
  }

  const form = new FormData();
  form.append('image', imgBlob, 'page.png');
  form.append('config', JSON.stringify(CONFIG));

  let resp;
  try {
    resp = await fetch(`${SERVER}/translate/with-form/image`, { method: 'POST', body: form });
  } catch (e) {
    throw new Error('Сервер переводчика не запущен (ярлык «Переводчик комиксов» на рабочем столе)');
  }
  if (!resp.ok) throw new Error(`Ошибка сервера: HTTP ${resp.status} ${await resp.text()}`);
  return blobToDataUrl(await resp.blob());
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type !== 'translate') return;
  translate(msg.src, sender.tab?.url)
    .then((dataUrl) => sendResponse({ ok: true, dataUrl }))
    .catch((e) => sendResponse({ ok: false, error: String(e.message || e) }));
  return true;
});
