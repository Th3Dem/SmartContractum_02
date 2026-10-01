/**
 * SmartContractum Mobile Emulator Controller
 * 100% Offline-first, Zero-emojis
 */

(function () {
  'use strict';

  // Device Presets Catalog
  const DEVICE_PRESETS = {
    iphone15pro: {
      name: 'iPhone 15 Pro',
      width: 393,
      height: 852,
      radius: 50,
      aspect: '19.5:9',
      hasIsland: true,
      hasNotch: false,
      bezel: 12
    },
    iphone14: {
      name: 'iPhone 14 / 13',
      width: 390,
      height: 844,
      radius: 47,
      aspect: '19.5:9',
      hasIsland: false,
      hasNotch: true,
      bezel: 12
    },
    iphonese: {
      name: 'iPhone SE',
      width: 375,
      height: 667,
      radius: 20,
      aspect: '16:9',
      hasIsland: false,
      hasNotch: false,
      bezel: 14
    },
    galaxys23: {
      name: 'Samsung Galaxy S23',
      width: 360,
      height: 780,
      radius: 42,
      aspect: '19.5:9',
      hasIsland: false,
      hasNotch: false,
      bezel: 10
    },
    pixel7: {
      name: 'Google Pixel 7',
      width: 412,
      height: 915,
      radius: 44,
      aspect: '20:9',
      hasIsland: false,
      hasNotch: false,
      bezel: 11
    },
    xiaomi13: {
      name: 'Xiaomi 13',
      width: 393,
      height: 873,
      radius: 40,
      aspect: '20:9',
      hasIsland: false,
      hasNotch: false,
      bezel: 10
    },
    ipadmini: {
      name: 'iPad Mini',
      width: 768,
      height: 1024,
      radius: 32,
      aspect: '4:3',
      hasIsland: false,
      hasNotch: false,
      bezel: 16
    }
  };

  // State
  let currentDeviceKey = 'iphone15pro';
  let orientation = 'portrait'; // 'portrait' | 'landscape'
  let isFitMode = true;
  let customScale = 1.0;
  let isLocked = false;
  let isTouchCursorActive = false;

  // DOM Elements
  const stage = document.getElementById('emulatorStage');
  const scaler = document.getElementById('deviceScaler');
  const frame = document.getElementById('smartphoneFrame');
  const iframe = document.getElementById('phoneFrame');
  const island = document.getElementById('dynamicIsland');
  const lockOverlay = document.getElementById('screenLockOverlay');
  const statusClock = document.getElementById('statusClock');
  const lockClock = document.getElementById('lockClock');
  const lockDate = document.getElementById('lockDate');
  const deviceSelect = document.getElementById('deviceSelect');
  const orientationLabel = document.getElementById('orientationLabel');
  const btnRotate = document.getElementById('btnRotate');
  const btnFit = document.getElementById('btnFit');
  const btnZoomIn = document.getElementById('btnZoomIn');
  const btnZoomOut = document.getElementById('btnZoomOut');
  const zoomValue = document.getElementById('zoomValue');
  const scaleValue = document.getElementById('scaleValue');
  const resValue = document.getElementById('resValue');
  const aspectValue = document.getElementById('aspectValue');
  const urlInput = document.getElementById('urlInput');
  const btnGo = document.getElementById('btnGo');
  const btnBack = document.getElementById('btnBack');
  const btnForward = document.getElementById('btnForward');
  const btnReload = document.getElementById('btnReload');
  const btnOpenExternal = document.getElementById('btnOpenExternal');
  const btnToggleSiteTheme = document.getElementById('btnToggleSiteTheme');
  const btnTouchCursor = document.getElementById('btnTouchCursor');
  const touchCursorDot = document.getElementById('touchCursorDot');
  const homeIndicator = document.getElementById('homeIndicatorBar');
  const btnPower = document.getElementById('btnHardwarePower');
  const btnVolUp = document.getElementById('btnHardwareVolUp');
  const btnVolDown = document.getElementById('btnHardwareVolDown');
  const pageTabs = document.querySelectorAll('.page-tab');

  // Initialize
  function init() {
    setupInitialUrlFromQuery();
    applyDevicePreset(currentDeviceKey);
    bindEvents();
    startClock();
    autoScale();
    window.addEventListener('resize', onWindowResize);
  }

  // Parse ?page=... or ?url=...
  function setupInitialUrlFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const pageParam = params.get('page') || params.get('url');
    if (pageParam) {
      loadPage(pageParam);
    }
  }

  // Apply device size and geometry
  function applyDevicePreset(key) {
    const dev = DEVICE_PRESETS[key] || DEVICE_PRESETS.iphone15pro;
    currentDeviceKey = key;

    let w = dev.width;
    let h = dev.height;

    if (orientation === 'landscape') {
      const tmp = w;
      w = h;
      h = tmp;
    }

    document.documentElement.style.setProperty('--phone-w', `${w}px`);
    document.documentElement.style.setProperty('--phone-h', `${h}px`);
    document.documentElement.style.setProperty('--phone-radius', `${dev.radius}px`);
    document.documentElement.style.setProperty('--phone-bezel-w', `${dev.bezel}px`);

    frame.setAttribute('data-device', key);
    frame.setAttribute('data-orientation', orientation);

    if (island) {
      island.style.display = dev.hasIsland ? 'flex' : 'none';
    }

    resValue.textContent = `${w} × ${h} px`;
    aspectValue.textContent = dev.aspect;

    if (isFitMode) {
      autoScale();
    }
  }

  // Auto scale calculation to fit screen without scrolling
  function autoScale() {
    if (!stage || !scaler) return;

    const dev = DEVICE_PRESETS[currentDeviceKey] || DEVICE_PRESETS.iphone15pro;
    let w = dev.width + (dev.bezel * 2) + 24; // with buttons margin
    let h = dev.height + (dev.bezel * 2) + 24;

    if (orientation === 'landscape') {
      const tmp = w;
      w = h;
      h = tmp;
    }

    const availW = stage.clientWidth - 48;
    const availH = stage.clientHeight - 48;

    if (availW <= 0 || availH <= 0) return;

    const scaleX = availW / w;
    const scaleY = availH / h;
    const computedScale = Math.min(1.0, scaleX, scaleY);

    customScale = Math.max(0.3, Math.min(2.0, computedScale));
    applyScale(customScale);

    zoomValue.textContent = `${Math.round(customScale * 100)}%`;
    scaleValue.textContent = `${Math.round(customScale * 100)}%`;
  }

  function applyScale(scale) {
    scaler.style.transform = `scale(${scale})`;
    scaleValue.textContent = `${Math.round(scale * 100)}%`;
  }

  function onWindowResize() {
    if (isFitMode) {
      autoScale();
    }
  }

  // Load a page inside iframe
  function loadPage(pageUrl) {
    let cleanUrl = pageUrl.trim();
    if (cleanUrl.startsWith('http://localhost:8000/')) {
      cleanUrl = cleanUrl.replace('http://localhost:8000/', '');
    }
    if (cleanUrl.startsWith('/')) {
      cleanUrl = cleanUrl.substring(1);
    }
    if (!cleanUrl) {
      cleanUrl = 'feed.html';
    }

    iframe.src = cleanUrl;
    urlInput.value = cleanUrl;

    // Highlight matching page tab
    pageTabs.forEach(tab => {
      const tabUrl = tab.getAttribute('data-url');
      if (tabUrl && cleanUrl.startsWith(tabUrl)) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });
  }

  // Clock in status bar
  function startClock() {
    function update() {
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const timeStr = `${hours}:${minutes}`;

      if (statusClock) statusClock.textContent = timeStr;
      if (lockClock) lockClock.textContent = timeStr;

      const options = { weekday: 'long', day: 'numeric', month: 'long' };
      if (lockDate) {
        const dateStr = now.toLocaleDateString('ru-RU', options);
        lockDate.textContent = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
      }
    }
    update();
    setInterval(update, 1000);
  }

  // Bind UI Events
  function bindEvents() {
    // Device preset selection
    deviceSelect.addEventListener('change', (e) => {
      if (e.target.value === 'custom') {
        const customW = prompt('Ширина экрана (px):', '390');
        const customH = prompt('Высота экрана (px):', '844');
        if (customW && customH) {
          DEVICE_PRESETS.custom = {
            name: 'Пользовательский',
            width: parseInt(customW, 10) || 390,
            height: parseInt(customH, 10) || 844,
            radius: 36,
            aspect: 'custom',
            hasIsland: false,
            hasNotch: false,
            bezel: 12
          };
          applyDevicePreset('custom');
        } else {
          deviceSelect.value = currentDeviceKey;
        }
      } else {
        applyDevicePreset(e.target.value);
      }
    });

    // Orientation toggle
    btnRotate.addEventListener('click', toggleOrientation);

    // Zoom controls
    btnFit.addEventListener('click', () => {
      isFitMode = true;
      btnFit.classList.add('active');
      autoScale();
    });

    btnZoomIn.addEventListener('click', () => {
      isFitMode = false;
      btnFit.classList.remove('active');
      customScale = Math.min(1.5, customScale + 0.1);
      applyScale(customScale);
      zoomValue.textContent = `${Math.round(customScale * 100)}%`;
    });

    btnZoomOut.addEventListener('click', () => {
      isFitMode = false;
      btnFit.classList.remove('active');
      customScale = Math.max(0.4, customScale - 0.1);
      applyScale(customScale);
      zoomValue.textContent = `${Math.round(customScale * 100)}%`;
    });

    // Page tabs
    pageTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const url = tab.getAttribute('data-url');
        if (url) {
          loadPage(url);
        }
      });
    });

    // Address Bar
    btnGo.addEventListener('click', () => {
      loadPage(urlInput.value);
    });

    urlInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        loadPage(urlInput.value);
      }
    });

    // Navigation buttons
    btnBack.addEventListener('click', () => {
      try {
        iframe.contentWindow.history.back();
      } catch (e) {}
    });

    btnForward.addEventListener('click', () => {
      try {
        iframe.contentWindow.history.forward();
      } catch (e) {}
    });

    btnReload.addEventListener('click', () => {
      try {
        iframe.contentWindow.location.reload();
      } catch (e) {
        iframe.src = iframe.src;
      }
    });

    btnOpenExternal.addEventListener('click', () => {
      const url = urlInput.value || 'feed.html';
      window.open(url, '_blank');
    });

    // Sync address bar when iframe navigates
    iframe.addEventListener('load', () => {
      try {
        const path = iframe.contentWindow.location.pathname.replace(/^\//, '');
        const search = iframe.contentWindow.location.search || '';
        const full = path ? `${path}${search}` : 'feed.html';
        urlInput.value = full;

        // Sync tab highlights
        pageTabs.forEach(tab => {
          const tabUrl = tab.getAttribute('data-url');
          if (tabUrl && full.startsWith(tabUrl)) {
            tab.classList.add('active');
          } else {
            tab.classList.remove('active');
          }
        });
      } catch (e) {}
    });

    // Toggle Site Theme inside iframe
    btnToggleSiteTheme.addEventListener('click', () => {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        if (!doc) return;

        const curTheme = doc.documentElement.getAttribute('data-theme') || 'dark';
        const nextTheme = curTheme === 'dark' ? 'light' : 'dark';
        doc.documentElement.setAttribute('data-theme', nextTheme);

        try {
          iframe.contentWindow.localStorage.setItem('ag_theme', nextTheme);
          iframe.contentWindow.localStorage.setItem('sc_theme', nextTheme);
        } catch (e) {}

        const themeBtn = doc.getElementById('btnThemeToggle');
        if (themeBtn) {
          themeBtn.setAttribute('aria-checked', nextTheme === 'light' ? 'true' : 'false');
        }
      } catch (e) {}
    });

    // Touch Cursor simulation
    btnTouchCursor.addEventListener('click', () => {
      isTouchCursorActive = !isTouchCursorActive;
      btnTouchCursor.classList.toggle('active', isTouchCursorActive);
      touchCursorDot.style.display = isTouchCursorActive ? 'block' : 'none';
    });

    // Move touch dot inside phone screen
    const screen = document.getElementById('phoneScreen');
    screen.addEventListener('mousemove', (e) => {
      if (!isTouchCursorActive) return;
      const rect = screen.getBoundingClientRect();
      const x = (e.clientX - rect.left) / customScale;
      const y = (e.clientY - rect.top) / customScale;
      touchCursorDot.style.left = `${x}px`;
      touchCursorDot.style.top = `${y}px`;
    });

    screen.addEventListener('mousedown', () => {
      if (isTouchCursorActive) {
        touchCursorDot.classList.add('active-tap');
      }
    });

    window.addEventListener('mouseup', () => {
      if (isTouchCursorActive) {
        touchCursorDot.classList.remove('active-tap');
      }
    });

    // Hardware buttons
    if (btnPower) {
      btnPower.addEventListener('click', toggleScreenLock);
    }

    if (lockOverlay) {
      lockOverlay.addEventListener('click', unlockScreen);
    }

    if (btnVolUp) {
      btnVolUp.addEventListener('click', () => {
        try {
          iframe.contentWindow.scrollBy({ top: -150, behavior: 'smooth' });
        } catch (e) {}
      });
    }

    if (btnVolDown) {
      btnVolDown.addEventListener('click', () => {
        try {
          iframe.contentWindow.scrollBy({ top: 150, behavior: 'smooth' });
        } catch (e) {}
      });
    }

    // Home Indicator (tap to scroll to top)
    if (homeIndicator) {
      homeIndicator.addEventListener('click', () => {
        try {
          iframe.contentWindow.scrollTo({ top: 0, behavior: 'smooth' });
        } catch (e) {}
      });
    }

    // Dynamic island fun animation
    if (island) {
      island.addEventListener('click', () => {
        island.style.transform = 'scale(1.08)';
        setTimeout(() => {
          island.style.transform = 'scale(1)';
        }, 200);
      });
    }

    // Global keyboard shortcuts
    window.addEventListener('keydown', (e) => {
      // Ignore if focus is in an input field
      if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) {
        return;
      }

      if (e.key === 'r' || e.key === 'R' || e.key === 'к' || e.key === 'К') {
        e.preventDefault();
        btnReload.click();
      } else if (e.key === 'o' || e.key === 'O' || e.key === 'щ' || e.key === 'Щ') {
        e.preventDefault();
        toggleOrientation();
      } else if (e.key === 'f' || e.key === 'F' || e.key === 'а' || e.key === 'А') {
        e.preventDefault();
        btnFit.click();
      } else if (e.key === 't' || e.key === 'T' || e.key === 'е' || e.key === 'Е') {
        e.preventDefault();
        btnToggleSiteTheme.click();
      } else if (e.key === '1') {
        loadPage('feed.html');
      } else if (e.key === '2') {
        loadPage('article.html');
      } else if (e.key === '3') {
        loadPage('editor.html');
      }
    });
  }

  function toggleOrientation() {
    orientation = orientation === 'portrait' ? 'landscape' : 'portrait';
    orientationLabel.textContent = orientation === 'portrait' ? 'Книжная' : 'Альбомная';
    btnRotate.classList.toggle('active', orientation === 'landscape');
    applyDevicePreset(currentDeviceKey);
  }

  function toggleScreenLock() {
    isLocked = !isLocked;
    lockOverlay.classList.toggle('is-locked', isLocked);
  }

  function unlockScreen() {
    isLocked = false;
    lockOverlay.classList.remove('is-locked');
  }

  // Run on DOM Ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
