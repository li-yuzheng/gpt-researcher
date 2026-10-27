/* ==========================================================================
   Stripe 风格交互增强
   --------------------------------------------------------------------------
   1. 按钮涟漪 / 按压反馈
   2. 提交按钮加载态
   3. 卡片滚动入场
   4. 研究完成提示音（优先播放 frontend/apologize.mp3，缺失时用合成音兜底）
   5. 提示音开关

   本文件不修改 scripts.js 的任何函数，只做「加法」：
   scripts.js 在收到 type === 'path' 时会调用 window.__onResearchComplete()。
   ========================================================================== */

(function () {
    'use strict';

    /* ------------------------------------------------------------------
       1. 全局音频上下文
       ------------------------------------------------------------------
       浏览器要求音频必须在「用户手势」之后才能播放。策略是：
       - 首次点击/触摸/按键时创建并解锁 AudioContext（此时属于用户手势）
       - 之后报告完成时再播放就不会被拦截
       ------------------------------------------------------------------ */
    let audioCtx = null;
    let audioUnlocked = false;

    function unlockAudio() {
        if (audioUnlocked) return;
        try {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return;
            audioCtx = new Ctx();
            if (audioCtx.state === 'suspended') audioCtx.resume();
            // 播放一个 0 音量的极短声音，确保 iOS/Safari 真正解锁
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            gain.gain.value = 0;
            osc.connect(gain).connect(audioCtx.destination);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.01);
            audioUnlocked = true;
        } catch (e) {
            console.warn('[stripe-ui] 音频初始化失败:', e);
        }
    }

    ['pointerdown', 'touchstart', 'keydown'].forEach(function (evt) {
        document.addEventListener(evt, unlockAudio, { once: false, passive: true });
    });

    /* ------------------------------------------------------------------
       2. 提示音
       ------------------------------------------------------------------
       版权说明：Apologize 是环球音乐的版权作品，不能随项目分发。
       把你自己合法获取的 apologize.mp3 放到 frontend/ 目录即可自动启用。
       没有该文件时，退化为一段原创的合成提示音（不涉及任何版权）。
       ------------------------------------------------------------------ */
    const SOUND_SOURCES = ['/site/apologize.mp3', '/site/apologize.m4a'];
    const SOUND_ENABLED_KEY = 'gptr_result_sound_enabled';

    // 隐私模式/禁用 Cookie 时 localStorage 可能直接抛异常，不能让整段脚本挂掉
    function readFlag() {
        try {
            return localStorage.getItem(SOUND_ENABLED_KEY) !== '0';
        } catch (e) {
            return true;
        }
    }

    function writeFlag(value) {
        try {
            localStorage.setItem(SOUND_ENABLED_KEY, value ? '1' : '0');
        } catch (e) {
            /* 存不了就算了，本次会话内仍然生效 */
        }
    }

    let soundEnabled = readFlag();
    let soundElement = null;
    let soundResolved = null; // null=未探测, true=可用, false=不可用

    function probeCustomSound() {
        // 逐个尝试候选文件，命中第一个可播放的就用它
        return new Promise(function (resolve) {
            let index = 0;
            function tryNext() {
                if (index >= SOUND_SOURCES.length) {
                    soundElement = null;
                    resolve(false);
                    return;
                }
                const url = SOUND_SOURCES[index++];
                const el = new Audio();
                el.preload = 'auto';
                el.volume = 0.85;

                const done = function (ok) {
                    el.removeEventListener('canplaythrough', onOk);
                    el.removeEventListener('error', onErr);
                    if (ok) {
                        soundElement = el;
                        resolve(true);
                    } else {
                        tryNext();
                    }
                };
                const onOk = function () { done(true); };
                const onErr = function () { done(false); };

                el.addEventListener('canplaythrough', onOk, { once: true });
                el.addEventListener('error', onErr, { once: true });
                el.src = url;
                el.load();
            }
            tryNext();
        });
    }

    // 页面空闲时探测一次，避免第一次出结果才去加载造成延迟
    if ('requestIdleCallback' in window) {
        requestIdleCallback(function () { probeCustomSound().then(function (ok) { soundResolved = ok; }); });
    } else {
        setTimeout(function () { probeCustomSound().then(function (ok) { soundResolved = ok; }); }, 1200);
    }

    /**
     * 合成提示音：三个上行音 + 一个柔和长音，作为默认提示。
     * 完全由振荡器生成，不依赖任何音频文件。
     */
    function playSynthChime() {
        try {
            if (!audioCtx) unlockAudio();
            if (!audioCtx) return;
            if (audioCtx.state === 'suspended') audioCtx.resume();

            const now = audioCtx.currentTime;
            // E5 - G5 - B5 - E6，简单的上行大三和弦琶音
            const notes = [
                { freq: 659.25, at: 0.00, dur: 0.34 },
                { freq: 783.99, at: 0.16, dur: 0.34 },
                { freq: 987.77, at: 0.32, dur: 0.40 },
                { freq: 1318.51, at: 0.50, dur: 0.85 }
            ];

            notes.forEach(function (n) {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(n.freq, now + n.at);

                gain.gain.setValueAtTime(0, now + n.at);
                gain.gain.linearRampToValueAtTime(0.20, now + n.at + 0.03);
                gain.gain.exponentialRampToValueAtTime(0.0008, now + n.at + n.dur);

                osc.connect(gain).connect(audioCtx.destination);
                osc.start(now + n.at);
                osc.stop(now + n.at + n.dur + 0.05);
            });
        } catch (e) {
            console.warn('[stripe-ui] 合成提示音失败:', e);
        }
    }

    function playResultSound() {
        if (!soundEnabled) return;

        const fallback = function () { playSynthChime(); };

        if (soundResolved === true && soundElement) {
            try {
                soundElement.currentTime = 0;
                const p = soundElement.play();
                if (p && typeof p.catch === 'function') p.catch(fallback);
            } catch (e) {
                fallback();
            }
            return;
        }

        // 还没探测完，先播兜底音，同时补探测
        if (soundResolved === null) {
            probeCustomSound().then(function (ok) { soundResolved = ok; });
        }
        fallback();
    }

    /* ------------------------------------------------------------------
       3. 提示音开关
       ------------------------------------------------------------------ */
    function injectSoundToggle() {
        const btn = document.createElement('button');
        btn.id = 'soundToggleBtn';
        btn.className = 'sound-toggle' + (soundEnabled ? '' : ' is-off');
        btn.type = 'button';
        btn.title = '研究完成时播放提示音';
        renderSoundToggle(btn);

        btn.addEventListener('click', function () {
            soundEnabled = !soundEnabled;
            writeFlag(soundEnabled);
            renderSoundToggle(btn);
            if (soundEnabled) {
                unlockAudio();
                playSynthChime(); // 立即试听，让用户确认已开启
            }
        });

        document.body.appendChild(btn);
    }

    function renderSoundToggle(btn) {
        btn.innerHTML = soundEnabled
            ? '<i class="fas fa-bell"></i><span>完成提醒 · 开</span>'
            : '<i class="fas fa-bell-slash"></i><span>完成提醒 · 关</span>';
        btn.setAttribute('aria-pressed', String(soundEnabled));
    }

    /* ------------------------------------------------------------------
       4. 研究完成
       ------------------------------------------------------------------ */
    window.__onResearchComplete = function () {
        // 结束提交按钮的加载态
        const submitBtn = document.getElementById('submitButton');
        if (submitBtn) submitBtn.classList.remove('is-loading');

        document.body.classList.add('research-done');
        playResultSound();
    };

    /* ------------------------------------------------------------------
       5. 按钮涟漪
       ------------------------------------------------------------------ */
    const RIPPLE_SELECTOR = [
        '.btn',
        '#submitButton',
        '#sendChatBtn',
        '.report-action-btn',
        '.download-option-btn',
        '.preset-btn',
        '#mcpFormatBtn',
        '.top-history-button',
        '.top-websocket-button',
        '.history-entry-action',
        '.icon-button',
        '.expand-button'
    ].join(',');

    document.addEventListener('pointerdown', function (event) {
        const target = event.target.closest(RIPPLE_SELECTOR);
        if (!target) return;
        if (target.classList.contains('disabled')) return;
        // 让既有逻辑（展开、复制等）不受影响，只叠加视觉层
        if (getComputedStyle(target).position === 'static') {
            target.style.position = 'relative';
        }
        target.style.overflow = 'hidden';

        const rect = target.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const span = document.createElement('span');
        span.className = 'ripple';
        span.style.width = span.style.height = size + 'px';
        span.style.left = (event.clientX - rect.left - size / 2) + 'px';
        span.style.top = (event.clientY - rect.top - size / 2) + 'px';

        target.appendChild(span);
        span.addEventListener('animationend', function () { span.remove(); });
        // 兜底移除，防止动画事件丢失后残留
        setTimeout(function () { if (span.parentNode) span.remove(); }, 900);
    }, { passive: true });

    /* ------------------------------------------------------------------
       6. 提交按钮加载态
       ------------------------------------------------------------------ */
    document.addEventListener('submit', function (event) {
        if (event.target && event.target.id === 'researchForm') {
            const btn = document.getElementById('submitButton');
            if (btn) btn.classList.add('is-loading');
        }
    }, true);

    /* ------------------------------------------------------------------
       7. 滚动入场（只作用于始终可见的元素，避免影响动态显示的面板）
       ------------------------------------------------------------------ */
    function initReveal() {
        const targets = document.querySelectorAll('.container, footer');
        if (!('IntersectionObserver' in window)) return;

        const io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    io.unobserve(entry.target);
                }
            });
        }, { threshold: 0.06, rootMargin: '0px 0px -40px 0px' });

        targets.forEach(function (el) {
            el.classList.add('st-reveal');
            io.observe(el);
            // 2 秒后仍未触发则强制显示，避免任何情况下内容不可见
            setTimeout(function () { el.classList.add('is-visible'); }, 2000);
        });
    }

    /* ------------------------------------------------------------------
       8. 初始化
       ------------------------------------------------------------------ */
    function init() {
        injectSoundToggle();
        initReveal();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
