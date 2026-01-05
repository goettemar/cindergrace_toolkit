// ==UserScript==
// @name         Tunee.ai Bulk MP3 Downloader
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Automatisch alle Songs von Tunee.ai als MP3 herunterladen
// @author       Cindergrace Toolkit
// @match        https://www.tunee.ai/home/music*
// @match        https://www.tunee.ai/project/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

    // Konfiguration
    const CONFIG = {
        delayBetweenSongs: 3000,      // 3 Sekunden zwischen Downloads
        delayAfterMenuClick: 500,      // 0.5 Sekunden nach Menu-Klick
        delayAfterDownloadClick: 1000, // 1 Sekunde nach Download-Klick
        delayForModalOpen: 800,        // 0.8 Sekunden für Modal-Öffnung
        maxRetries: 3                  // Maximale Wiederholungen bei Fehler
    };

    // UI erstellen
    function createUI() {
        const container = document.createElement('div');
        container.id = 'tunee-bulk-downloader';
        container.innerHTML = `
            <style>
                #tunee-bulk-downloader {
                    position: fixed;
                    top: 80px;
                    right: 20px;
                    background: white;
                    border: 2px solid #6366f1;
                    border-radius: 12px;
                    padding: 16px;
                    z-index: 10000;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
                    font-family: system-ui, sans-serif;
                    min-width: 280px;
                }
                #tunee-bulk-downloader h3 {
                    margin: 0 0 12px 0;
                    color: #6366f1;
                    font-size: 16px;
                }
                #tunee-bulk-downloader .status {
                    background: #f3f4f6;
                    padding: 8px 12px;
                    border-radius: 6px;
                    margin: 8px 0;
                    font-size: 13px;
                    max-height: 150px;
                    overflow-y: auto;
                }
                #tunee-bulk-downloader button {
                    background: #6366f1;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    margin: 4px;
                }
                #tunee-bulk-downloader button:hover {
                    background: #4f46e5;
                }
                #tunee-bulk-downloader button:disabled {
                    background: #9ca3af;
                    cursor: not-allowed;
                }
                #tunee-bulk-downloader button.stop {
                    background: #ef4444;
                }
                #tunee-bulk-downloader .progress {
                    background: #e5e7eb;
                    height: 8px;
                    border-radius: 4px;
                    margin: 8px 0;
                    overflow: hidden;
                }
                #tunee-bulk-downloader .progress-bar {
                    background: #6366f1;
                    height: 100%;
                    width: 0%;
                    transition: width 0.3s;
                }
                #tunee-bulk-downloader .info {
                    font-size: 12px;
                    color: #6b7280;
                    margin-top: 8px;
                }
            </style>
            <h3>🎵 Tunee Bulk Downloader</h3>
            <div class="status" id="bulk-status">Bereit. Klicke Start um alle sichtbaren Songs herunterzuladen.</div>
            <div class="progress"><div class="progress-bar" id="bulk-progress"></div></div>
            <div>
                <button id="bulk-start">▶️ Start</button>
                <button id="bulk-stop" class="stop" disabled>⏹️ Stop</button>
            </div>
            <div class="info">
                Tipp: Scrolle zuerst ganz nach unten um alle Songs zu laden!
            </div>
        `;
        document.body.appendChild(container);
        return container;
    }

    let isRunning = false;
    let shouldStop = false;

    function log(message) {
        const status = document.getElementById('bulk-status');
        if (status) {
            status.innerHTML = message + '<br>' + status.innerHTML;
            status.scrollTop = 0;
        }
        console.log('[Tunee Bulk]', message);
    }

    function updateProgress(current, total) {
        const bar = document.getElementById('bulk-progress');
        if (bar) {
            bar.style.width = (current / total * 100) + '%';
        }
    }

    // Finde alle Song-Zeilen mit "..." Menü-Button
    function findSongRows() {
        // Suche nach Zeilen die einen "..." Button haben
        const allButtons = document.querySelectorAll('button');
        const menuButtons = [];

        allButtons.forEach(btn => {
            // Der "..." Button hat normalerweise ein SVG mit drei Punkten
            const rect = btn.getBoundingClientRect();
            // Buttons am rechten Rand der Zeilen (nach Remix und Star)
            if (rect.width < 60 && rect.height < 60 && rect.x > 1400) {
                // Prüfe ob es ein Menu-Button ist (hat keine Text-Kinder)
                if (!btn.textContent.trim() || btn.textContent.includes('...')) {
                    menuButtons.push(btn);
                }
            }
        });

        return menuButtons;
    }

    // Klicke auf Download im Menü
    async function clickDownloadInMenu() {
        await delay(CONFIG.delayAfterMenuClick);

        // Suche nach "Download" im Menü
        const menuItems = document.querySelectorAll('[role="menuitem"], [class*="menu"] button, [class*="dropdown"] button');
        for (const item of menuItems) {
            if (item.textContent.toLowerCase().includes('download') &&
                !item.textContent.toLowerCase().includes('get stems')) {
                item.click();
                return true;
            }
        }

        // Alternative: Suche nach Text "Download"
        const allElements = document.querySelectorAll('div, span, button');
        for (const el of allElements) {
            if (el.textContent === 'Download' && el.offsetParent !== null) {
                el.click();
                return true;
            }
        }

        return false;
    }

    // Klicke auf MP3 Download im Modal
    async function clickMP3Download() {
        await delay(CONFIG.delayForModalOpen);

        // Suche nach dem Dialog/Modal
        const dialog = document.querySelector('dialog, [role="dialog"], [class*="modal"]');
        if (!dialog) {
            log('⚠️ Download-Modal nicht gefunden');
            return false;
        }

        // Finde alle Download-Buttons im Modal
        const downloadBtns = dialog.querySelectorAll('button');
        for (const btn of downloadBtns) {
            // Der erste "Download" Button ist MP3
            if (btn.textContent.includes('Download')) {
                btn.click();
                return true;
            }
        }

        return false;
    }

    // Schließe das Modal
    async function closeModal() {
        await delay(CONFIG.delayAfterDownloadClick);

        // Suche nach Close-Button oder klicke außerhalb
        const closeBtn = document.querySelector('dialog button[aria-label*="close"], [role="dialog"] button:first-child, [class*="modal"] button:first-child');
        if (closeBtn) {
            closeBtn.click();
            return;
        }

        // Alternative: Escape drücken
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', keyCode: 27 }));
    }

    // Hauptfunktion zum Herunterladen aller Songs
    async function downloadAllSongs() {
        if (isRunning) return;
        isRunning = true;
        shouldStop = false;

        document.getElementById('bulk-start').disabled = true;
        document.getElementById('bulk-stop').disabled = false;

        log('🔍 Suche Songs...');

        // Finde alle "..." Menü-Buttons
        const menuButtons = findSongRows();
        const total = menuButtons.length;

        if (total === 0) {
            log('❌ Keine Songs gefunden. Bist du auf der Music-Seite?');
            isRunning = false;
            document.getElementById('bulk-start').disabled = false;
            document.getElementById('bulk-stop').disabled = true;
            return;
        }

        log(`📋 ${total} Songs gefunden. Starte Download...`);

        let downloaded = 0;
        let errors = 0;

        for (let i = 0; i < menuButtons.length; i++) {
            if (shouldStop) {
                log('⏹️ Gestoppt durch Benutzer');
                break;
            }

            const btn = menuButtons[i];
            const songName = btn.closest('tr, [class*="row"], [class*="item"]')?.querySelector('[class*="title"], h3, h4, span')?.textContent || `Song ${i + 1}`;

            log(`⏳ (${i + 1}/${total}) ${songName.substring(0, 30)}...`);
            updateProgress(i + 1, total);

            try {
                // 1. Klicke auf "..." Menü
                btn.click();
                await delay(CONFIG.delayAfterMenuClick);

                // 2. Klicke auf "Download" im Menü
                const menuClicked = await clickDownloadInMenu();
                if (!menuClicked) {
                    log(`⚠️ Download-Option nicht gefunden für ${songName}`);
                    errors++;
                    // Schließe das Menü durch Klick woanders
                    document.body.click();
                    await delay(300);
                    continue;
                }

                // 3. Klicke auf MP3 Download im Modal
                const mp3Clicked = await clickMP3Download();
                if (!mp3Clicked) {
                    log(`⚠️ MP3-Button nicht gefunden für ${songName}`);
                    errors++;
                    await closeModal();
                    continue;
                }

                downloaded++;
                log(`✅ ${songName.substring(0, 25)} heruntergeladen`);

                // 4. Schließe das Modal
                await closeModal();

                // 5. Warte zwischen Downloads
                await delay(CONFIG.delayBetweenSongs);

            } catch (error) {
                log(`❌ Fehler bei ${songName}: ${error.message}`);
                errors++;
                // Versuche aufzuräumen
                document.body.click();
                await delay(500);
            }
        }

        isRunning = false;
        document.getElementById('bulk-start').disabled = false;
        document.getElementById('bulk-stop').disabled = true;

        log(`🎉 Fertig! ${downloaded} heruntergeladen, ${errors} Fehler`);
        updateProgress(total, total);
    }

    function stopDownload() {
        shouldStop = true;
        log('⏸️ Stoppe nach aktuellem Download...');
    }

    // Initialisierung
    function init() {
        // Warte bis Seite geladen
        if (document.readyState !== 'complete') {
            window.addEventListener('load', init);
            return;
        }

        // UI erstellen
        createUI();

        // Event Listener
        document.getElementById('bulk-start').addEventListener('click', downloadAllSongs);
        document.getElementById('bulk-stop').addEventListener('click', stopDownload);

        log('✅ Bulk Downloader bereit!');
    }

    // Starte nach kurzer Verzögerung
    setTimeout(init, 1000);
})();
