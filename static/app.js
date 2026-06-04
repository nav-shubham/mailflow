// DOM Elements
const navItems = document.querySelectorAll('.nav-item');
const viewPanels = document.querySelectorAll('.view-panel');
const pageTitle = document.getElementById('page-title');
const pageSubtitle = document.getElementById('page-subtitle');
const scanBtn = document.getElementById('scan-btn');

// Stats Elements
const statAccounts = document.getElementById('stat-accounts');
const statLookback = document.getElementById('stat-lookback');
const statEmails = document.getElementById('stat-emails');

// Dashboard View Elements
const scanProgressBarContainer = document.getElementById('scan-progress-bar-container');
const scanProgressTitle = document.getElementById('scan-progress-title');
const scanProgressRatio = document.getElementById('scan-progress-ratio');
const scanProgressFill = document.getElementById('scan-progress-fill');
const scanProgressSubtext = document.getElementById('scan-progress-subtext');

const recentScansBanner = document.getElementById('recent-scans-banner');
const recentScansText = document.getElementById('recent-scans-text');
const freshScanBannerBtn = document.getElementById('fresh-scan-banner-btn');

const searchInput = document.getElementById('search-input');
const accountFilter = document.getElementById('account-filter');
const sortSelect = document.getElementById('sort-select');
const exportExcelBtn = document.getElementById('export-excel-btn');

const emailList = document.getElementById('email-list');
const emailListContainer = document.getElementById('email-list-container');
const emptyState = document.getElementById('empty-state');

// Settings View Elements
const settingEmail1 = document.getElementById('setting-email-1');
const settingEmail1Pwd = document.getElementById('setting-email-1-pwd');
const settingEmail2 = document.getElementById('setting-email-2');
const settingEmail2Pwd = document.getElementById('setting-email-2-pwd');
const settingLookback = document.getElementById('setting-lookback');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const togglePwdBtns = document.querySelectorAll('.btn-toggle-pwd');

// App State Cache
let emailsData = [];
let appConfig = {};
let isScanning = false;
let statusInterval = null;

// ==========================================
// TOAST NOTIFICATIONS
// ==========================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ==========================================
// ROUTING / VIEW NAVIGATION
// ==========================================
navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const target = item.getAttribute('data-target');
        
        // Update nav active state
        navItems.forEach(nav => nav.classList.remove('active'));
        item.classList.add('active');
        
        // Update view panels
        viewPanels.forEach(panel => panel.classList.remove('active'));
        document.getElementById(target).classList.add('active');
        
        // Update page header labels
        if (target === 'dashboard-view') {
            pageTitle.innerText = "Dashboard";
            pageSubtitle.innerText = "Scan, filter, and review recent emails across your accounts";
            scanBtn.classList.remove('hidden');
        } else if (target === 'settings-view') {
            pageTitle.innerText = "Settings";
            pageSubtitle.innerText = "Configure email accounts and scan windows";
            scanBtn.classList.add('hidden');
        }
    });
});

// Toggle password fields visibility
togglePwdBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const inputId = btn.getAttribute('data-target');
        const input = document.getElementById(inputId);
        if (input.type === 'password') {
            input.type = 'text';
            btn.innerText = '🙈';
        } else {
            input.type = 'password';
            btn.innerText = '👁️';
        }
    });
});

// ==========================================
// DATA FORMATTING HELPERS
// ==========================================
function parseSender(fromStr) {
    // Extracts Name and Email from From header string
    // e.g. "John Doe <john.doe@gmail.com>"
    const match = fromStr.match(/(.*)<(.*)>/);
    if (match) {
        return {
            name: match[1].trim().replace(/^["']|["']$/g, ''),
            email: match[2].trim()
        };
    }
    
    // Check if it's just an email
    if (fromStr.includes('@')) {
        return {
            name: fromStr.split('@')[0],
            email: fromStr
        };
    }
    
    return {
        name: fromStr,
        email: ''
    };
}

// ==========================================
// RENDER DATA GRID
// ==========================================
function renderEmailsGrid() {
    // 1. Apply client-side search and filters
    const query = searchInput.value.toLowerCase().trim();
    const accountFilterVal = accountFilter.value;
    const sortVal = sortSelect.value;
    
    let filtered = emailsData.filter(email => {
        // Account filter
        if (accountFilterVal !== 'all' && email.account !== accountFilterVal) {
            return false;
        }
        
        // Keyword filter
        if (query) {
            const subjectMatch = email.subject.toLowerCase().includes(query);
            const fromMatch = email.from_str.toLowerCase().includes(query);
            const accountMatch = email.account.toLowerCase().includes(query);
            return subjectMatch || fromMatch || accountMatch;
        }
        
        return true;
    });
    
    // 2. Sort emails
    filtered.sort((a, b) => {
        const dateA = new Date(`${a.date_ist}T${a.time_ist}`);
        const dateB = new Date(`${b.date_ist}T${b.time_ist}`);
        return sortVal === 'newest' ? dateB - dateA : dateA - dateB;
    });
    
    // 3. Render cards
    emailList.innerHTML = '';
    
    if (filtered.length === 0) {
        emailListContainer.classList.add('hidden');
        emptyState.classList.remove('hidden');
        if (query || accountFilterVal !== 'all') {
            emptyState.querySelector('h2').innerText = "No matching emails";
            emptyState.querySelector('p').innerText = "Try adjusting your search keywords or account filter options.";
        } else {
            emptyState.querySelector('h2').innerText = "No emails loaded";
            emptyState.querySelector('p').innerText = "Click \"Scan Emails\" at the top to fetch the latest messages.";
        }
        return;
    }
    
    emailListContainer.classList.remove('hidden');
    emptyState.classList.add('hidden');
    
    // Clean Nordic colors for avatars
    const colors = [
        '#0ea5e9', // Ice blue
        '#6366f1', // Indigo
        '#3b82f6', // Slate blue
        '#0d9488', // Teal
        '#0891b2', // Cyan
        '#475569', // Slate gray
        '#2563eb', // Royal blue
        '#4f46e5'  // Deep indigo
    ];
    
    filtered.forEach((em) => {
        const sender = parseSender(em.from_str);
        const card = document.createElement('div');
        card.className = 'email-card';
        
        // Generate avatar initials and color
        const initials = (sender.name || 'U').charAt(0).toUpperCase();
        const colorIndex = initials.charCodeAt(0) % colors.length;
        const avatarBg = colors[colorIndex];
        
        // Style badges per account
        const isAccount1 = em.account === appConfig.email_1;
        const badgeClass = isAccount1 ? 'badge-account-1' : 'badge-account-2';
        
        card.innerHTML = `
            <div class="email-card-left">
                <div class="avatar" style="background: ${avatarBg};">
                    ${initials}
                </div>
            </div>
            <div class="email-card-middle">
                <div class="email-sender-info">
                    <span class="sender-name">${sender.name || 'Unknown Sender'}</span>
                    ${sender.email ? `<span class="sender-email">&lt;${sender.email}&gt;</span>` : ''}
                    <span class="badge ${badgeClass}" title="${em.account}">${em.account}</span>
                </div>
                <div class="email-subject-wrapper">
                    <a href="${em.gmail_link}" target="_blank" class="email-card-subject" title="Open in Gmail">
                        ${em.subject || '(No Subject)'}
                    </a>
                </div>
            </div>
            <div class="email-card-right">
                <div class="email-time-info">
                    <div class="email-date">${em.date_ist}</div>
                    <div class="email-time">${em.time_ist}</div>
                </div>
                <div class="email-actions">
                    <a href="${em.gmail_link}" target="_blank" class="btn btn-outline btn-sm">Open ↗</a>
                </div>
            </div>
        `;
        
        emailList.appendChild(card);
    });
    
    // Update emails count stats
    statEmails.innerText = filtered.length;
}

// ==========================================
// CONFIGURATION AND INITIAL LOAD
// ==========================================
async function fetchConfig() {
    try {
        const res = await fetch('/api/config');
        if (!res.ok) throw new Error("Could not load config API");
        const data = await res.json();
        
        appConfig = data;
        
        // Populate settings inputs
        settingEmail1.value = data.email_1 || '';
        settingEmail1Pwd.value = data.email_1_password || '';
        settingEmail2.value = data.email_2 || '';
        settingEmail2Pwd.value = data.email_2_password || '';
        settingLookback.value = data.lookback_hours || 48;
        
        // Update stats
        let activeCount = 0;
        if (data.email_1) activeCount++;
        if (data.email_2) activeCount++;
        statAccounts.innerText = `${activeCount} / 2`;
        statLookback.innerText = `${data.lookback_hours} Hours`;
        
        // Populate accounts selector
        accountFilter.innerHTML = '<option value="all">All Accounts</option>';
        if (data.email_1) {
            accountFilter.innerHTML += `<option value="${data.email_1}">Account 1 (${data.email_1})</option>`;
        }
        if (data.email_2) {
            accountFilter.innerHTML += `<option value="${data.email_2}">Account 2 (${data.email_2})</option>`;
        }
    } catch (e) {
        showToast(`Failed to load config: ${e.message}`, 'error');
    }
}

async function fetchStatus(showNotification = false) {
    try {
        const res = await fetch('/api/emails/status');
        if (!res.ok) throw new Error("Status endpoint error");
        const state = await res.json();
        
        emailsData = state.emails || [];
        isScanning = state.status === 'scanning';
        
        // Update progress bar
        if (isScanning) {
            scanProgressBarContainer.classList.remove('hidden');
            scanBtn.disabled = true;
            scanBtn.querySelector('.btn-text').innerText = "Scanning...";
            
            const total = state.total_accounts || 1;
            const processed = state.processed_accounts || 0;
            const pct = Math.round((processed / total) * 100);
            
            scanProgressFill.style.width = `${pct}%`;
            scanProgressTitle.innerText = `Scanning Accounts... (${pct}%)`;
            scanProgressRatio.innerText = `${processed}/${total} Accounts`;
            scanProgressSubtext.innerText = state.current_status_msg || "Connecting...";
        } else {
            scanProgressBarContainer.classList.add('hidden');
            scanBtn.disabled = false;
            scanBtn.querySelector('.btn-text').innerText = "Scan Emails";
            
            if (statusInterval) {
                clearInterval(statusInterval);
                statusInterval = null;
                
                if (state.status === 'completed') {
                    showToast(state.current_status_msg || "Scan completed successfully!", "success");
                } else if (state.status === 'error') {
                    showToast(state.error_message || "Scan failed.", "error");
                }
            }
        }
        
        // Render emails
        renderEmailsGrid();
        
        // Display last scanned banner
        if (state.last_scanned_at) {
            recentScansBanner.classList.remove('hidden');
            recentScansText.innerText = `Showing emails cached from the last scan on ${state.last_scanned_at}.`;
        } else {
            recentScansBanner.classList.add('hidden');
        }
        
    } catch (e) {
        console.error("Error fetching status:", e);
    }
}

// ==========================================
// ACTIONS
// ==========================================
async function saveConfigHandler() {
    const payload = {
        email_1: settingEmail1.value.trim(),
        email_1_password: settingEmail1Pwd.value.trim(),
        email_2: settingEmail2.value.trim(),
        email_2_password: settingEmail2Pwd.value.trim(),
        lookback_hours: parseInt(settingLookback.value) || 48
    };
    
    saveSettingsBtn.disabled = true;
    saveSettingsBtn.innerText = "Saving...";
    
    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || "Failed to save settings");
        
        showToast("Configuration saved successfully!", "success");
        await fetchConfig();
    } catch (e) {
        showToast(e.message, "error");
    } finally {
        saveSettingsBtn.disabled = false;
        saveSettingsBtn.innerText = "Save Configuration";
    }
}

async function triggerScan() {
    if (isScanning) return;
    
    try {
        const res = await fetch('/api/emails/scan', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || "Failed to trigger scan");
        
        showToast("Email scan started in background...", "info");
        isScanning = true;
        
        // Start polling status
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(() => fetchStatus(true), 1000);
        await fetchStatus();
    } catch (e) {
        showToast(e.message, "error");
    }
}

async function triggerExport() {
    if (emailsData.length === 0) {
        showToast("No email data to export. Please run a scan first.", "error");
        return;
    }
    
    exportExcelBtn.disabled = true;
    exportExcelBtn.innerText = "Exporting...";
    
    try {
        const res = await fetch('/api/emails/export', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || "Failed to export data");
        
        showToast(`Excel report successfully updated! Saved to ${data.path}`, "success");
    } catch (e) {
        showToast(e.message, "error");
    } finally {
        exportExcelBtn.disabled = false;
        exportExcelBtn.innerHTML = "<span>📊</span> Export Excel Report";
    }
}

// ==========================================
// INTERACTIVE HANDLERS
// ==========================================
scanBtn.addEventListener('click', triggerScan);
freshScanBannerBtn.addEventListener('click', triggerScan);
saveSettingsBtn.addEventListener('click', saveConfigHandler);
exportExcelBtn.addEventListener('click', triggerExport);

searchInput.addEventListener('input', renderEmailsGrid);
accountFilter.addEventListener('change', renderEmailsGrid);
sortSelect.addEventListener('change', renderEmailsGrid);

// Initial Load
(async function init() {
    await fetchConfig();
    await fetchStatus();
    
    // If the server was already scanning, resume polling
    if (isScanning) {
        statusInterval = setInterval(() => fetchStatus(true), 1000);
    }
})();
