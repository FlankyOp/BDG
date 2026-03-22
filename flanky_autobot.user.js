// ==UserScript==
// @name         Flanky Autobot - BDG Game
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Automates betting on BDG Game linked to local Python Python broker
// @author       FlankyOp / AI
// @match        https://bdggame5.com/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// ==/UserScript==

(function() {
    'use strict';

    const BROKER_URL = "http://127.0.0.1:8787/api/bot";
    let lastExecutedPeriod = null;

    console.log("[FlankyBot] Initialized. Waiting for Wingo page...");

    function logStatus(msg) {
        console.log("[FlankyBot]", msg);
        GM_xmlhttpRequest({
            method: "POST",
            url: `${BROKER_URL}/status`,
            headers: { "Content-Type": "application/json" },
            data: JSON.stringify({ message: msg, timestamp: Date.now() })
        });
    }

    function pollCommand() {
        GM_xmlhttpRequest({
            method: "GET",
            url: `${BROKER_URL}/command`,
            onload: function(res) {
                try {
                    const data = JSON.parse(res.responseText);
                    if (data.status === "success" && data.data) {
                        handleCommand(data.data);
                    }
                } catch (e) {
                    console.error("[FlankyBot] Parse error", e);
                }
            }
        });
    }

    // Poll the dashboard broker every 1.5 seconds
    setInterval(pollCommand, 1500);

    async function handleCommand(cmd) {
        // Expected payload: { period: "...", target: "Big", amount: 30 }
        // For array targets (like Number betting), target might be an array: [4, 9, 8]
        // But for simplicity, we process one order at a time, or looping.
        if (!cmd.period || !cmd.target || !cmd.amount) return;
        if (cmd.period === lastExecutedPeriod) return;

        // Check if we are actually on a supported Wingo page
        if (!location.href.includes("WinGo")) return;

        // Prevent firing in the last 5 seconds lock-out window
        const timerStr = document.querySelector('.time-box') ? document.querySelector('.time-box').textContent.replace(/\s+/g,'') : "";
        if (timerStr.includes("0000000") || (timerStr.length > 5 && parseInt(timerStr.slice(-2)) < 5)) {
            logStatus(`⚠️ Period ${cmd.period} lockout active. Skipping.`);
            lastExecutedPeriod = cmd.period;
            return;
        }

        lastExecutedPeriod = cmd.period;
        
        let targets = Array.isArray(cmd.target) ? cmd.target : [cmd.target];
        logStatus(`Executing order for ${cmd.period}: Rs ${cmd.amount} on [${targets.join(', ')}]`);

        for (let t of targets) {
            try {
                await executeBet(t, cmd.amount);
                logStatus(`✅ Placed Rs ${cmd.amount} on ${t}`);
            } catch (err) {
                logStatus(`❌ Failed to place Rs ${cmd.amount} on ${t}: ${err.message}`);
            }
        }
    }

    async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    async function executeBet(targetText, amount) {
        // 1. Click target button on the grid
        const buttons = Array.from(document.querySelectorAll('div, span, button'));
        const targetBtn = buttons.find(el => el.textContent.trim() === String(targetText) && el.childElementCount === 0);

        if (!targetBtn) {
            // Additional fallback for Number balls which might be deeply nested
            const altBtn = Array.from(document.querySelectorAll('.ball')).find(el => el.textContent.trim() === String(targetText));
            if (altBtn) {
                altBtn.click();
            } else {
                throw new Error(`Target button '${targetText}' not found on grid`);
            }
        } else {
            targetBtn.click();
        }

        await sleep(500); // Wait for modal slide up

        // 2. Determine best Base Stake (1, 10, 100, 1000)
        let base = 1;
        if (amount >= 1000 && amount % 1000 === 0) base = 1000;
        else if (amount >= 100 && amount % 100 === 0) base = 100;
        else if (amount >= 10 && amount % 10 === 0) base = 10;

        const qty = amount / base;

        // Click Base Stake button
        const modalButtons = Array.from(document.querySelectorAll('.van-popup button, .van-popup div'));
        const baseBtn = modalButtons.find(el => el.textContent.trim() === String(base));
        if (baseBtn) baseBtn.click();

        // 3. Set precise quantity multiplier
        const input = document.querySelector('.van-popup input');
        if (!input) throw new Error("Quantity input not found inside modal");

        input.value = String(qty);
        input.dispatchEvent(new Event('input', { bubbles: true }));

        await sleep(300); // Allow framework to update Total Amount

        // 4. Confirm Order
        const confirmBtns = Array.from(document.querySelectorAll('.van-popup div, .van-popup button'));
        const confirmBtn = confirmBtns.find(el => el.textContent.includes('Total amount'));

        if (!confirmBtn) throw new Error("Confirm 'Total amount' button not found");
        confirmBtn.click();

        await sleep(600); // Wait for API response modal overlay
    }
})();
