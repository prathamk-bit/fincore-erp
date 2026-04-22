/* FinCore ERP — Minimalist UI (Stripe/Linear Inspired) */

// === 1. State ===
const state = { token: localStorage.getItem('fincore_token'), user: JSON.parse(localStorage.getItem('fincore_user') || 'null'), currentPage: 'dashboard' };

// === 2. API ===
async function api(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
    const silent403 = options.silent403; delete options.silent403;
    const response = await fetch(`/api${endpoint}`, { ...options, headers });
    if (response.status === 401) { logout(); return; }
    if (response.status === 403) {
        const err = await response.json().catch(() => ({ detail: 'Access denied' }));
        if (!silent403) showAlert(err.detail || 'Access denied', 'warning');
        throw new Error(err.detail || 'Access denied');
    }
    if (!response.ok) { const err = await response.json().catch(() => ({ detail: 'Request failed' })); throw new Error(err.detail || 'Request failed'); }
    return response.json();
}

// === 3. Router ===
const pageRenderers = {
    'dashboard': renderDashboard, 'accounts': renderAccounts, 'journal-entries': renderJournalEntries,
    'ledger': renderLedger, 'trial-balance': renderTrialBalance, 'income-statement': renderIncomeStatement,
    'balance-sheet': renderBalanceSheet, 'cash-flow': renderCashFlow, 'transactions': renderTransactions,
    'employees': renderEmployees, 'departments': renderDepartments, 'designations': renderDesignations,
    'payroll': renderPayroll, 'items': renderItems, 'categories': renderCategories, 'warehouses': renderWarehouses,
    'stock-ledger': renderStockLedger, 'inventory-adjustments': renderInventoryAdjustments,
    'purchase-orders': renderPurchaseOrders, 'suppliers': renderSuppliers, 'users': renderUsers
};
const pageTitles = {
    'dashboard': 'Dashboard', 'accounts': 'Chart of Accounts', 'journal-entries': 'Journal Entries',
    'ledger': 'General Ledger', 'trial-balance': 'Trial Balance', 'income-statement': 'Income Statement',
    'balance-sheet': 'Balance Sheet', 'cash-flow': 'Cash Flow Statement', 'transactions': 'Transactions',
    'employees': 'Employees', 'departments': 'Departments', 'designations': 'Designations', 'payroll': 'Payroll',
    'items': 'Inventory Items', 'categories': 'Categories', 'warehouses': 'Warehouses', 'stock-ledger': 'Stock Ledger',
    'inventory-adjustments': 'Adjustments', 'purchase-orders': 'Purchase Orders', 'suppliers': 'Suppliers', 'users': 'User Management'
};

function navigateTo(page) {
    state.currentPage = page;
    document.querySelectorAll('.nav-item').forEach(i => i.classList.toggle('active', i.dataset.page === page));
    const t = document.querySelector('.topbar-title');
    if (t) t.innerHTML = `<h2>${pageTitles[page] || page}</h2><div class="breadcrumb">Home / ${pageTitles[page] || page}</div>`;
    const renderer = pageRenderers[page];
    if (renderer) renderer();
}

// === 4. Auth ===
async function login(username, password) {
    try {
        const data = await api('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
        if (!data) return;
        state.token = data.access_token;
        localStorage.setItem('fincore_token', data.access_token);
        const user = await api('/auth/me');
        if (!user) return;
        state.user = user;
        localStorage.setItem('fincore_user', JSON.stringify(user));
        showApp(); navigateTo('dashboard');
        showAlert('Welcome back, ' + user.username + '!', 'success');
        initAssistant();
    } catch (err) {
        const el = document.querySelector('.login-error');
        if (el) { el.textContent = err.message; el.style.display = 'block'; }
    }
}
function logout() { state.token = null; state.user = null; localStorage.removeItem('fincore_token'); localStorage.removeItem('fincore_user'); showLoginPage(); }
async function checkAuth() {
    try { const user = await api('/auth/me'); if (!user) return; state.user = user; localStorage.setItem('fincore_user', JSON.stringify(user)); showApp(); navigateTo('dashboard'); initAssistant(); } catch { logout(); }
}

// === 5. Layout ===
function showLoginPage() {
    document.getElementById('app').innerHTML = `
    <div class="login-container">
        <div class="login-card">
            <div class="login-brand">
                <div class="brand-mark">◆</div>
                <h1>FinCore</h1>
                <p>Finance-Centric ERP System</p>
            </div>
            <div class="login-box">
                <div class="login-error" style="display:none;"></div>
                <form id="login-form">
                    <div class="form-group"><label>Username</label><input type="text" id="login-username" placeholder="Enter username" required></div>
                    <div class="form-group"><label>Password</label><input type="password" id="login-password" placeholder="Enter password" required></div>
                    <button type="submit" class="btn-login">Sign In</button>
                </form>
            </div>
            <div class="login-creds">
                <h4>Demo Credentials</h4>
                <div class="cred-row"><span class="cred-role">Admin</span><span>admin / <code>admin123</code></span></div>
                <div class="cred-row"><span class="cred-role">Accountant</span><span>accountant / <code>acc123</code></span></div>
                <div class="cred-row"><span class="cred-role">HR Manager</span><span>hr_manager / <code>hr123</code></span></div>
                <div class="cred-row"><span class="cred-role">Inventory</span><span>inventory_manager / <code>inv123</code></span></div>
            </div>
        </div>
    </div>`;
    document.getElementById('login-form').addEventListener('submit', e => { e.preventDefault(); login(document.getElementById('login-username').value, document.getElementById('login-password').value); });
}

function showApp() {
    const user = state.user;
    const initials = user ? user.username.substring(0, 2).toUpperCase() : 'U';
    document.getElementById('app').innerHTML = `
    <div class="app-layout">
        <div class="sidebar-overlay" id="sidebar-overlay"></div>
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-brand"><div class="brand-icon">◆</div><div><div class="brand-name">FinCore</div><div class="brand-sub">ERP System</div></div></div>
            <div class="sidebar-scroll"><nav id="sidebar-nav">${buildSidebarNav()}</nav></div>
            <div class="sidebar-user"><div class="user-avatar">${initials}</div><div><div class="user-name">${esc(user?.username || 'User')}</div><div class="user-role">${esc(user?.role || '')}</div></div></div>
            <button class="btn-logout" id="btn-logout">↩ Sign Out</button>
        </aside>
        <div class="main-area">
            <header class="topbar">
                <button class="topbar-toggle" id="sidebar-toggle">☰</button>
                <div class="topbar-title"><h2>Dashboard</h2><div class="breadcrumb">Home / Dashboard</div></div>
                <div class="topbar-search"><input type="text" placeholder="Search…"></div>
                <div class="topbar-actions"></div>
            </header>
            <div class="content" id="main-content"></div>
        </div>
    </div>
    <div class="modal-overlay" id="modal-overlay"><div class="modal" id="modal-container"></div></div>
    <div class="alert-container" id="alert-container"></div>`;

    document.getElementById('btn-logout').addEventListener('click', logout);
    document.querySelectorAll('.nav-item').forEach(i => i.addEventListener('click', () => { navigateTo(i.dataset.page); closeSidebar(); }));
    document.getElementById('sidebar-toggle').addEventListener('click', toggleSidebar);
    document.getElementById('sidebar-overlay').addEventListener('click', closeSidebar);
    document.getElementById('modal-overlay').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });
}

// === 6. Sidebar ===
function buildSidebarNav() {
    const role = state.user?.role || '';
    const s = [];
    s.push({ t: 'Overview', items: [{ p: 'dashboard', i: '⌂', l: 'Dashboard' }] });
    if (['admin', 'accountant'].includes(role)) {
        s.push({ t: 'Accounting', items: [
            { p: 'accounts', i: '◈', l: 'Chart of Accounts' }, { p: 'journal-entries', i: '☰', l: 'Journal Entries' },
            { p: 'ledger', i: '▤', l: 'General Ledger' }, { p: 'trial-balance', i: '⚖', l: 'Trial Balance' }
        ]});
        s.push({ t: 'Reports', items: [
            { p: 'income-statement', i: '↗', l: 'Income Statement' }, { p: 'balance-sheet', i: '☷', l: 'Balance Sheet' }, { p: 'cash-flow', i: '⇄', l: 'Cash Flow' }
        ]});
        s.push({ t: 'Finance', items: [{ p: 'transactions', i: '⟐', l: 'Transactions' }] });
    }
    if (['admin', 'hr_manager'].includes(role)) {
        s.push({ t: 'Human Resources', items: [
            { p: 'employees', i: '⚇', l: 'Employees' }, { p: 'departments', i: '⊞', l: 'Departments' },
            { p: 'designations', i: '◇', l: 'Designations' }, { p: 'payroll', i: '₹', l: 'Payroll' }
        ]});
    }
    if (['admin', 'inventory_manager'].includes(role)) {
        s.push({ t: 'Inventory', items: [
            { p: 'items', i: '▦', l: 'Items' }, { p: 'categories', i: '⊟', l: 'Categories' },
            { p: 'warehouses', i: '⌂', l: 'Warehouses' }, { p: 'stock-ledger', i: '▤', l: 'Stock Ledger' },
            { p: 'inventory-adjustments', i: '⟳', l: 'Adjustments' }
        ]});
        s.push({ t: 'Procurement', items: [
            { p: 'purchase-orders', i: '✦', l: 'Purchase Orders' }, { p: 'suppliers', i: '⊕', l: 'Suppliers' }
        ]});
    }
    if (role === 'admin') s.push({ t: 'Admin', items: [{ p: 'users', i: '⚙', l: 'Users' }] });

    return s.map(sec => `<div class="nav-group"><div class="nav-group-label">${sec.t}</div>${sec.items.map(it => `<div class="nav-item" data-page="${it.p}"><span class="nav-icon">${it.i}</span><span class="nav-label">${it.l}</span></div>`).join('')}</div>`).join('');
}

function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); document.getElementById('sidebar-overlay').classList.toggle('active'); }
function closeSidebar() { document.getElementById('sidebar').classList.remove('open'); document.getElementById('sidebar-overlay').classList.remove('active'); }

// === 7. Helpers ===
function showAlert(message, type = 'info') {
    const c = document.getElementById('alert-container'); if (!c) return;
    const a = document.createElement('div');
    a.className = `alert alert-${type}`; a.innerHTML = `<span>${message}</span><button class="alert-close" onclick="this.parentElement.remove()">×</button>`;
    c.appendChild(a); setTimeout(() => { if (a.parentElement) a.remove(); }, 4000);
}

function showModal(title, content, footer = '') {
    const m = document.getElementById('modal-container');
    m.innerHTML = `<div class="modal-header"><h3>${title}</h3><button class="modal-close" onclick="closeModal()">×</button></div><div class="modal-body">${content}</div>${footer ? `<div class="modal-footer">${footer}</div>` : ''}`;
    document.getElementById('modal-overlay').classList.add('active');
}
function showModalLg(title, content, footer = '') { document.getElementById('modal-container').classList.add('modal-lg'); showModal(title, content, footer); }
function closeModal() { document.getElementById('modal-overlay').classList.remove('active'); const m = document.getElementById('modal-container'); m.classList.remove('modal-lg'); m.innerHTML = ''; }

function fmtCur(n) { return (parseFloat(n) || 0).toLocaleString('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }); }
function fmtDate(d) { if (!d) return '—'; return new Date(d).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' }); }
function esc(s) { if (!s) return ''; return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function showLoading() { const m = document.getElementById('main-content'); if (m) m.innerHTML = '<div class="loading">Loading…</div>'; }
function tip(text) { return `<i class="info-tip" data-tip="${esc(text)}">i</i>`; }

function statusBadge(status) {
    const map = { draft: 'neutral', pending: 'warning', approved: 'info', posted: 'success', processed: 'info', paid: 'success', received: 'success', cancelled: 'danger', active: 'success', inactive: 'neutral' };
    return `<span class="badge badge-${map[status] || 'neutral'}">${status}</span>`;
}

// === 8. Dashboard ===
async function renderDashboard() {
    showLoading();
    try {
        const stats = await api('/dashboard/stats');
        const role = state.user?.role;
        const isFinance = ['admin', 'accountant'].includes(role);
        let recent = [];
        if (isFinance) { try { recent = await api('/dashboard/recent-journal-entries'); } catch {} }

        const main = document.getElementById('main-content');
        main.innerHTML = `<div class="fade-up">
        ${isFinance ? `<div class="stats-grid stagger">
            <div class="stat-card fade-up"><div class="stat-label">Net Position ${tip('Total Assets minus Total Liabilities')}</div><div class="stat-value">${fmtCur(stats.net_position)}</div><div class="stat-sub">${parseFloat(stats.net_position) >= 0 ? '<span class="stat-trend up">↑ Positive</span>' : '<span class="stat-trend down">↓ Negative</span>'}</div></div>
            <div class="stat-card fade-up"><div class="stat-label">Net Income ${tip('Revenue minus Expenses. Shows profitability')}</div><div class="stat-value">${fmtCur(stats.net_income)}</div><div class="stat-sub">${parseFloat(stats.net_income) >= 0 ? '<span class="stat-trend up">↑ Profit</span>' : '<span class="stat-trend down">↓ Loss</span>'}</div></div>
            <div class="stat-card fade-up"><div class="stat-label">Total Revenue ${tip('Sum of all income from sales and services')}</div><div class="stat-value">${fmtCur(stats.total_revenue)}</div><div class="stat-sub">All income streams</div></div>
            <div class="stat-card fade-up"><div class="stat-label">Total Expenses ${tip('Sum of all costs including salaries, purchases, operations')}</div><div class="stat-value">${fmtCur(stats.total_expenses)}</div><div class="stat-sub">All cost centers</div></div>
        </div>` : ''}
        <div class="stats-row stagger">
            <div class="stat-mini fade-up"><div class="stat-icon-box blue">⚇</div><div><div class="stat-value">${stats.total_employees || 0}</div><div class="stat-label">Employees</div></div></div>
            <div class="stat-mini fade-up"><div class="stat-icon-box green">▦</div><div><div class="stat-value">${stats.total_items || 0}</div><div class="stat-label">Inventory Items</div></div></div>
            <div class="stat-mini fade-up"><div class="stat-icon-box amber">✦</div><div><div class="stat-value">${stats.total_purchase_orders || 0}</div><div class="stat-label">Purchase Orders</div></div></div>
        </div>
        ${isFinance ? `<div class="dash-grid">
            <div class="card fade-up"><div class="card-header"><h3>Recent Journal Entries</h3><button class="btn btn-ghost btn-sm" onclick="navigateTo('journal-entries')">View All →</button></div>
            <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Entry #</th><th>Date</th><th>Description</th><th class="text-right">Amount</th><th>Status</th></tr></thead>
            <tbody>${recent.length ? recent.slice(0, 8).map(je => `<tr><td class="cell-primary">${esc(je.entry_number)}</td><td>${fmtDate(je.date)}</td><td>${esc(je.description?.substring(0, 40))}</td><td class="text-right mono">${fmtCur(je.total_debit)}</td><td>${statusBadge(je.status || 'posted')}</td></tr>`).join('') : '<tr><td colspan="5" class="text-center text-muted" style="padding:24px">No entries yet</td></tr>'}</tbody></table></div></div></div>
            <div class="card fade-up"><div class="card-header"><h3>System Health</h3></div><div class="card-body">
                <div style="text-align:center;padding:12px 0">
                    <div style="display:inline-flex;flex-direction:column;align-items:center;gap:8px">
                        <div class="health-score-circle ${stats.is_balanced ? 'excellent' : 'poor'}"><span class="value">${stats.is_balanced ? '✓' : '!'}</span><span class="label">Balance</span></div>
                        <span style="font-size:0.8125rem;font-weight:600;color:${stats.is_balanced ? 'var(--success)' : 'var(--danger)'}">${stats.is_balanced ? 'Books Balanced' : 'Imbalanced'}</span>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">
                    <div style="background:var(--surface-hover);padding:12px;border-radius:var(--radius);text-align:center"><div style="font-size:0.6875rem;color:var(--text-muted);margin-bottom:4px">Accounts</div><div style="font-size:1.125rem;font-weight:700">${stats.total_accounts || 0}</div></div>
                    <div style="background:var(--surface-hover);padding:12px;border-radius:var(--radius);text-align:center"><div style="font-size:0.6875rem;color:var(--text-muted);margin-bottom:4px">Journal Entries</div><div style="font-size:1.125rem;font-weight:700">${stats.total_journal_entries || 0}</div></div>
                </div>
            </div></div>
        </div>` : '<div class="card"><div class="card-body"><div class="empty-state"><div class="empty-icon">📊</div><h3>Welcome to FinCore</h3><p>Use the sidebar to navigate to your modules.</p></div></div></div>'}
        </div>`;
    } catch (err) { document.getElementById('main-content').innerHTML = `<div class="card"><div class="card-body"><div class="empty-state"><h3>Error loading dashboard</h3><p>${esc(err.message)}</p></div></div></div>`; }
}

// === 9. Chart of Accounts ===
async function renderAccounts() {
    showLoading();
    try {
        const accounts = await api('/accounting/accounts');
        const main = document.getElementById('main-content');
        const types = ['asset', 'liability', 'equity', 'revenue', 'expense'];
        main.innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Chart of Accounts ${tip('Master list of all financial accounts used to classify transactions')}</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateAccountModal()">+ Add Account</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Sub-Type</th><th class="text-right">Balance</th><th>Status</th></tr></thead>
        <tbody>${accounts.map(a => `<tr><td class="cell-primary mono">${esc(a.code)}</td><td>${esc(a.name)}</td><td><span class="badge-flat ${a.account_type === 'asset' ? 'blue' : a.account_type === 'revenue' ? 'green' : a.account_type === 'expense' ? 'red' : a.account_type === 'liability' ? 'amber' : 'indigo'}">${a.account_type}</span></td><td class="text-muted">${esc(a.sub_type || '—')}</td><td class="text-right mono">${fmtCur(a.balance)}</td><td>${a.is_active ? '<span class="badge badge-success">Active</span>' : '<span class="badge badge-neutral">Inactive</span>'}</td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateAccountModal() {
    showModal('New Account', `
        <form id="form-account">
            <div class="form-row"><div class="form-group"><label>Account Code <span class="req">*</span></label><input type="text" id="acc-code" required></div>
            <div class="form-group"><label>Account Name <span class="req">*</span></label><input type="text" id="acc-name" required></div></div>
            <div class="form-row"><div class="form-group"><label>Type <span class="req">*</span></label><select id="acc-type"><option value="asset">Asset</option><option value="liability">Liability</option><option value="equity">Equity</option><option value="revenue">Revenue</option><option value="expense">Expense</option></select></div>
            <div class="form-group"><label>Sub-Type</label><input type="text" id="acc-subtype" placeholder="Optional"></div></div>
            <div class="form-group"><label>Description</label><textarea id="acc-desc" rows="2" placeholder="Optional description"></textarea></div>
        </form>`, `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createAccount()">Create Account</button>`);
}

async function createAccount() {
    try {
        await api('/accounting/accounts', { method: 'POST', body: JSON.stringify({
            code: document.getElementById('acc-code').value, name: document.getElementById('acc-name').value,
            account_type: document.getElementById('acc-type').value, sub_type: document.getElementById('acc-subtype').value || null,
            description: document.getElementById('acc-desc').value || null
        })});
        closeModal(); showAlert('Account created', 'success'); renderAccounts();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 10. Journal Entries ===
async function renderJournalEntries() {
    showLoading();
    try {
        const entries = await api('/accounting/journal-entries');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Journal Entries ${tip('Double-entry bookkeeping records. Each entry must have equal debits and credits')}</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateJEModal()">+ New Entry</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Entry #</th><th>Date</th><th>Description</th><th class="text-right">Debit</th><th class="text-right">Credit</th><th>Status</th><th></th></tr></thead>
        <tbody>${entries.map(je => `<tr><td class="cell-primary">${esc(je.entry_number)}</td><td>${fmtDate(je.date)}</td><td>${esc(je.description?.substring(0, 50))}</td><td class="text-right mono">${fmtCur(je.total_debit)}</td><td class="text-right mono">${fmtCur(je.total_credit)}</td><td>${statusBadge(je.status)}</td>
        <td><div class="tbl-actions"><button class="btn-icon" onclick="viewJE(${je.id})" title="View">⊙</button>${je.status === 'draft' ? `<button class="btn-icon" onclick="postJE(${je.id})" title="Post">✓</button>` : ''}</div></td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

async function viewJE(id) {
    try {
        const je = await api(`/accounting/journal-entries/${id}`);
        showModalLg(`Journal Entry — ${je.entry_number}`, `
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px">
                <div><span class="text-muted" style="font-size:0.75rem">Date</span><div style="font-weight:600">${fmtDate(je.date)}</div></div>
                <div><span class="text-muted" style="font-size:0.75rem">Status</span><div>${statusBadge(je.status)}</div></div>
                <div><span class="text-muted" style="font-size:0.75rem">Total</span><div style="font-weight:600">${fmtCur(je.total_debit)}</div></div>
            </div>
            <div style="margin-bottom:12px"><span class="text-muted" style="font-size:0.75rem">Description</span><div>${esc(je.description)}</div></div>
            <table class="tbl"><thead><tr><th>Account</th><th class="text-right">Debit</th><th class="text-right">Credit</th></tr></thead>
            <tbody>${(je.lines || []).map(l => `<tr><td class="cell-primary">${esc(l.account_name || l.account_code || 'Account #' + l.account_id)}</td><td class="text-right mono">${parseFloat(l.debit) > 0 ? fmtCur(l.debit) : '—'}</td><td class="text-right mono">${parseFloat(l.credit) > 0 ? fmtCur(l.credit) : '—'}</td></tr>`).join('')}
            </tbody><tfoot><tr><td class="cell-primary">Total</td><td class="text-right mono">${fmtCur(je.total_debit)}</td><td class="text-right mono">${fmtCur(je.total_credit)}</td></tr></tfoot></table>`);
    } catch (err) { showAlert(err.message, 'error'); }
}

async function postJE(id) {
    try { await api(`/accounting/journal-entries/${id}/post`, { method: 'POST' }); showAlert('Entry posted', 'success'); renderJournalEntries(); } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateJEModal() {
    let lineCount = 2;
    const getLinesHTML = () => {
        let h = '';
        for (let i = 0; i < lineCount; i++) h += `<div class="form-row cols-3" id="je-line-${i}"><div class="form-group"><label>Account ID</label><input type="number" id="je-acc-${i}" required></div><div class="form-group"><label>Debit</label><input type="number" step="0.01" id="je-dr-${i}" value="0"></div><div class="form-group"><label>Credit</label><input type="number" step="0.01" id="je-cr-${i}" value="0"></div></div>`;
        return h;
    };
    showModalLg('New Journal Entry', `
        <form id="form-je">
            <div class="form-row"><div class="form-group"><label>Date <span class="req">*</span></label><input type="date" id="je-date" required></div><div class="form-group"><label>Description <span class="req">*</span></label><input type="text" id="je-desc" required></div></div>
            <h4 style="margin:16px 0 8px;font-size:0.8125rem">Line Items</h4>
            <div id="je-lines">${getLinesHTML()}</div>
            <button type="button" class="btn btn-ghost btn-sm" onclick="addJELine()" style="margin-top:8px">+ Add Line</button>
        </form>`, `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createJE()">Create Entry</button>`);
    window._jeLineCount = lineCount;
}

function addJELine() {
    const i = window._jeLineCount++;
    const div = document.createElement('div'); div.className = 'form-row cols-3'; div.id = `je-line-${i}`;
    div.innerHTML = `<div class="form-group"><label>Account ID</label><input type="number" id="je-acc-${i}" required></div><div class="form-group"><label>Debit</label><input type="number" step="0.01" id="je-dr-${i}" value="0"></div><div class="form-group"><label>Credit</label><input type="number" step="0.01" id="je-cr-${i}" value="0"></div>`;
    document.getElementById('je-lines').appendChild(div);
}

async function createJE() {
    const lines = [];
    for (let i = 0; i < window._jeLineCount; i++) {
        const acc = document.getElementById(`je-acc-${i}`);
        if (!acc) continue;
        lines.push({ account_id: parseInt(acc.value), debit: document.getElementById(`je-dr-${i}`).value || '0', credit: document.getElementById(`je-cr-${i}`).value || '0' });
    }
    try {
        await api('/accounting/journal-entries', { method: 'POST', body: JSON.stringify({ date: document.getElementById('je-date').value, description: document.getElementById('je-desc').value, lines }) });
        closeModal(); showAlert('Journal entry created', 'success'); renderJournalEntries();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 11. General Ledger ===
async function renderLedger() {
    showLoading();
    try {
        const accounts = await api('/accounting/accounts');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>General Ledger ${tip('All posted journal entry lines for a specific account with running balance')}</h3></div>
        <div class="card-body"><div class="form-row"><div class="form-group"><label>Select Account</label><select id="ledger-account" onchange="loadLedger()"><option value="">Choose an account…</option>${accounts.map(a => `<option value="${a.id}">${esc(a.code)} — ${esc(a.name)}</option>`).join('')}</select></div></div>
        <div id="ledger-data"></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

async function loadLedger() {
    const accId = document.getElementById('ledger-account').value;
    const el = document.getElementById('ledger-data');
    if (!accId) { el.innerHTML = ''; return; }
    el.innerHTML = '<div class="loading">Loading…</div>';
    try {
        const data = await api(`/accounting/ledger/${accId}`);
        const entries = data.entries || data;
        el.innerHTML = `<div class="table-wrap"><table class="tbl"><thead><tr><th>Date</th><th>Entry #</th><th>Description</th><th class="text-right">Debit</th><th class="text-right">Credit</th><th class="text-right">Balance</th></tr></thead>
        <tbody>${Array.isArray(entries) && entries.length ? entries.map(e => `<tr><td>${fmtDate(e.date)}</td><td class="cell-primary">${esc(e.entry_number || '')}</td><td>${esc(e.description || '')}</td><td class="text-right mono">${parseFloat(e.debit) > 0 ? fmtCur(e.debit) : '—'}</td><td class="text-right mono">${parseFloat(e.credit) > 0 ? fmtCur(e.credit) : '—'}</td><td class="text-right mono font-bold">${fmtCur(e.running_balance ?? e.balance ?? 0)}</td></tr>`).join('') : '<tr><td colspan="6" class="text-center text-muted" style="padding:24px">No ledger entries found</td></tr>'}</tbody></table></div>`;
    } catch (err) { el.innerHTML = `<div class="empty-state"><p>${esc(err.message)}</p></div>`; }
}

// === 12. Trial Balance ===
async function renderTrialBalance() {
    showLoading();
    try {
        const tb = await api('/accounting/trial-balance');
        const accs = tb.entries || tb.accounts || [];
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Trial Balance ${tip('Report listing all accounts with debit and credit totals. Must be balanced')}</h3><div class="card-actions">${tb.is_balanced ? '<span class="badge badge-success">Balanced</span>' : '<span class="badge badge-danger">Imbalanced</span>'}</div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Code</th><th>Account Name</th><th>Type</th><th class="text-right">Debit</th><th class="text-right">Credit</th></tr></thead>
        <tbody>${accs.map(a => `<tr><td class="mono">${esc(a.account_code || a.code)}</td><td class="cell-primary">${esc(a.account_name || a.name)}</td><td><span class="badge-flat ${a.account_type === 'asset' ? 'blue' : a.account_type === 'revenue' ? 'green' : a.account_type === 'expense' ? 'red' : a.account_type === 'liability' ? 'amber' : 'indigo'}">${a.account_type}</span></td><td class="text-right mono">${fmtCur(a.debit_balance || a.debit)}</td><td class="text-right mono">${fmtCur(a.credit_balance || a.credit)}</td></tr>`).join('')}</tbody>
        <tfoot><tr><td colspan="3" class="cell-primary">Total</td><td class="text-right mono">${fmtCur(tb.total_debits)}</td><td class="text-right mono">${fmtCur(tb.total_credits)}</td></tr></tfoot></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 13. Income Statement ===
async function renderIncomeStatement() {
    showLoading();
    try {
        const data = await api('/accounting/reports/income-statement?start_date=2025-01-01&end_date=2025-12-31');
        const revItems = (data.revenue_section?.line_items || data.revenue_accounts || []);
        const expItems = (data.expense_section?.line_items || data.expense_accounts || []);
        document.getElementById('main-content').innerHTML = `<div class="fade-up"><div class="card"><div class="card-header"><h3>Income Statement ${tip('Revenue minus Expenses. Positive net income means profit')}</h3></div>
        <div class="card-body">
            <div class="report-header"><h2>Income Statement</h2><p>For the period Jan 1, 2025 — Dec 31, 2025</p></div>
            <div class="report-section"><h4>Revenue</h4><table class="tbl"><tbody>${revItems.map(a => `<tr><td>${esc(a.account_name || a.name)}</td><td class="text-right mono">${fmtCur(a.amount || a.balance)}</td></tr>`).join('') || '<tr><td colspan="2" class="text-muted">No revenue accounts</td></tr>'}</tbody><tfoot><tr><td class="cell-primary">Total Revenue</td><td class="text-right mono">${fmtCur(data.total_revenue)}</td></tr></tfoot></table></div>
            <div class="report-section"><h4>Expenses</h4><table class="tbl"><tbody>${expItems.map(a => `<tr><td>${esc(a.account_name || a.name)}</td><td class="text-right mono">${fmtCur(a.amount || a.balance)}</td></tr>`).join('') || '<tr><td colspan="2" class="text-muted">No expense accounts</td></tr>'}</tbody><tfoot><tr><td class="cell-primary">Total Expenses</td><td class="text-right mono">${fmtCur(data.total_expenses)}</td></tr></tfoot></table></div>
            <div style="background:${parseFloat(data.net_income) >= 0 ? 'var(--success-light)' : 'var(--danger-light)'};padding:16px 20px;border-radius:var(--radius);display:flex;justify-content:space-between;align-items:center;margin-top:24px"><span style="font-weight:700;font-size:1rem">Net Income</span><span style="font-weight:700;font-size:1.25rem;color:${parseFloat(data.net_income) >= 0 ? 'var(--success)' : 'var(--danger)'}">${fmtCur(data.net_income)}</span></div>
        </div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 14. Balance Sheet ===
async function renderBalanceSheet() {
    showLoading();
    try {
        const data = await api('/accounting/reports/balance-sheet');
        const assetItems = (data.assets_section?.line_items || data.assets || []);
        const liabItems = (data.liabilities_section?.line_items || data.liabilities || []);
        const eqItems = (data.equity_section?.line_items || data.equity || []);
        document.getElementById('main-content').innerHTML = `<div class="fade-up"><div class="card"><div class="card-header"><h3>Balance Sheet ${tip('Snapshot of financial position. Assets = Liabilities + Equity')}</h3><div class="card-actions">${data.is_balanced ? '<span class="badge badge-success">A = L + E</span>' : '<span class="badge badge-danger">Imbalanced</span>'}</div></div>
        <div class="card-body">
            <div class="report-header"><h2>Balance Sheet</h2><p>As of ${fmtDate(data.as_of_date || new Date().toISOString())}</p></div>
            <div class="report-section"><h4>Assets</h4><table class="tbl"><tbody>${assetItems.map(a => `<tr><td>${esc(a.account_name || a.name)}</td><td class="text-right mono">${fmtCur(a.balance || a.amount)}</td></tr>`).join('')}</tbody><tfoot><tr><td class="cell-primary">Total Assets</td><td class="text-right mono">${fmtCur(data.total_assets)}</td></tr></tfoot></table></div>
            <div class="report-section"><h4>Liabilities</h4><table class="tbl"><tbody>${liabItems.map(a => `<tr><td>${esc(a.account_name || a.name)}</td><td class="text-right mono">${fmtCur(a.balance || a.amount)}</td></tr>`).join('')}</tbody><tfoot><tr><td class="cell-primary">Total Liabilities</td><td class="text-right mono">${fmtCur(data.total_liabilities)}</td></tr></tfoot></table></div>
            <div class="report-section"><h4>Equity</h4><table class="tbl"><tbody>${eqItems.map(a => `<tr><td>${esc(a.account_name || a.name)}</td><td class="text-right mono">${fmtCur(a.balance || a.amount)}</td></tr>`).join('')}</tbody><tfoot><tr><td class="cell-primary">Total Equity</td><td class="text-right mono">${fmtCur(data.total_equity)}</td></tr></tfoot></table></div>
            <div style="background:var(--surface-hover);padding:16px 20px;border-radius:var(--radius);display:flex;justify-content:space-between;margin-top:20px"><span style="font-weight:700">Liabilities + Equity</span><span class="mono font-bold">${fmtCur(data.liabilities_and_equity)}</span></div>
        </div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 15. Cash Flow ===
async function renderCashFlow() {
    showLoading();
    try {
        const data = await api('/accounting/reports/cash-flow?start_date=2025-01-01&end_date=2025-12-31');
        const sections = [
            { title: 'Operating Activities', items: data.operating_activities?.line_items || data.operating_activities || [], total: data.operating_activities?.section_total || data.total_operating },
            { title: 'Investing Activities', items: data.investing_activities?.line_items || data.investing_activities || [], total: data.investing_activities?.section_total || data.total_investing },
            { title: 'Financing Activities', items: data.financing_activities?.line_items || data.financing_activities || [], total: data.financing_activities?.section_total || data.total_financing }
        ];
        document.getElementById('main-content').innerHTML = `<div class="fade-up"><div class="card"><div class="card-header"><h3>Cash Flow Statement ${tip('Cash movements: Operating, Investing, and Financing activities')}</h3></div>
        <div class="card-body">
            <div class="report-header"><h2>Cash Flow Statement</h2><p>For the period Jan 1, 2025 — Dec 31, 2025</p></div>
            ${sections.map(s => `<div class="report-section"><h4>${s.title}</h4><table class="tbl"><tbody>${s.items.length ? s.items.map(i => `<tr><td>${esc(i.name || i.description)}</td><td class="text-right mono">${fmtCur(i.amount || i.balance)}</td></tr>`).join('') : '<tr><td colspan="2" class="text-muted">No items</td></tr>'}</tbody>${s.total !== undefined ? `<tfoot><tr><td class="cell-primary">Total</td><td class="text-right mono">${fmtCur(s.total)}</td></tr></tfoot>` : ''}</table></div>`).join('')}
            <div style="background:var(--accent-light);padding:16px 20px;border-radius:var(--radius);display:flex;justify-content:space-between;margin-top:20px"><span style="font-weight:700;color:var(--accent)">Net Cash Flow</span><span class="mono font-bold" style="color:var(--accent)">${fmtCur(data.net_cash_flow)}</span></div>
        </div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 16. Financial Transactions ===
async function renderTransactions() {
    showLoading();
    try {
        const txns = await api('/finance/transactions');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Financial Transactions</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateTxnModal()">+ New Transaction</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Date</th><th>Type</th><th>Category</th><th>Description</th><th class="text-right">Amount</th><th>JE</th></tr></thead>
        <tbody>${txns.map(t => `<tr><td>${fmtDate(t.transaction_date)}</td><td><span class="badge-flat ${t.transaction_type === 'income' ? 'green' : 'red'}">${t.transaction_type}</span></td><td class="cell-primary">${esc(t.category)}</td><td>${esc(t.description?.substring(0, 40))}</td><td class="text-right mono">${fmtCur(t.amount)}</td><td>${t.journal_entry_id ? '<span class="badge badge-success">Linked</span>' : '—'}</td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateTxnModal() {
    showModal('New Transaction', `
        <form id="form-txn">
            <div class="form-row"><div class="form-group"><label>Date <span class="req">*</span></label><input type="date" id="txn-date" required></div>
            <div class="form-group"><label>Type <span class="req">*</span></label><select id="txn-type"><option value="income">Income</option><option value="expense">Expense</option></select></div></div>
            <div class="form-row"><div class="form-group"><label>Category <span class="req">*</span></label><input type="text" id="txn-cat" required></div>
            <div class="form-group"><label>Amount <span class="req">*</span></label><input type="number" step="0.01" id="txn-amt" required></div></div>
            <div class="form-group"><label>Description</label><input type="text" id="txn-desc"></div>
        </form>`, `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createTxn()">Create</button>`);
}

async function createTxn() {
    try {
        await api('/finance/transactions', { method: 'POST', body: JSON.stringify({
            transaction_date: document.getElementById('txn-date').value, transaction_type: document.getElementById('txn-type').value,
            category: document.getElementById('txn-cat').value, amount: document.getElementById('txn-amt').value,
            description: document.getElementById('txn-desc').value
        })});
        closeModal(); showAlert('Transaction created', 'success'); renderTransactions();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 17. Employees ===
async function renderEmployees() {
    showLoading();
    try {
        const emps = await api('/hr/employees');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Employees</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateEmployeeModal()">+ Add Employee</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Code</th><th>Name</th><th>Department</th><th>Designation</th><th class="text-right">Salary</th><th>Status</th><th></th></tr></thead>
        <tbody>${emps.map(e => `<tr><td class="cell-primary mono">${esc(e.employee_code)}</td><td>${esc(e.first_name)} ${esc(e.last_name)}</td><td>${esc(e.department_name || '—')}</td><td>${esc(e.designation_name || '—')}</td><td class="text-right mono">${fmtCur(e.salary)}</td><td>${statusBadge(e.status || 'active')}</td>
        <td><div class="tbl-actions"><button class="btn-icon" onclick="showEditEmployeeModal(${e.id})" title="Edit">✎</button></div></td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateEmployeeModal() {
    showModal('New Employee', `
        <form id="form-emp">
            <div class="form-row"><div class="form-group"><label>First Name <span class="req">*</span></label><input type="text" id="emp-fname" required></div>
            <div class="form-group"><label>Last Name <span class="req">*</span></label><input type="text" id="emp-lname" required></div></div>
            <div class="form-row"><div class="form-group"><label>Email <span class="req">*</span></label><input type="email" id="emp-email" required></div>
            <div class="form-group"><label>Phone</label><input type="text" id="emp-phone"></div></div>
            <div class="form-row"><div class="form-group"><label>Department ID</label><input type="number" id="emp-dept"></div>
            <div class="form-group"><label>Designation ID</label><input type="number" id="emp-desg"></div></div>
            <div class="form-row"><div class="form-group"><label>Salary <span class="req">*</span></label><input type="number" step="0.01" id="emp-salary" required></div>
            <div class="form-group"><label>Date of Joining</label><input type="date" id="emp-doj"></div></div>
        </form>`, `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createEmployee()">Create</button>`);
}

async function createEmployee() {
    try {
        await api('/hr/employees', { method: 'POST', body: JSON.stringify({
            first_name: document.getElementById('emp-fname').value, last_name: document.getElementById('emp-lname').value,
            email: document.getElementById('emp-email').value, phone: document.getElementById('emp-phone').value || null,
            department_id: parseInt(document.getElementById('emp-dept').value) || null,
            designation_id: parseInt(document.getElementById('emp-desg').value) || null,
            salary: document.getElementById('emp-salary').value,
            date_of_joining: document.getElementById('emp-doj').value || new Date().toISOString().split('T')[0]
        })});
        closeModal(); showAlert('Employee created', 'success'); renderEmployees();
    } catch (err) { showAlert(err.message, 'error'); }
}

async function showEditEmployeeModal(id) {
    try {
        const e = await api(`/hr/employees/${id}`);
        showModal('Edit Employee', `
            <form id="form-emp-edit">
                <div class="form-row"><div class="form-group"><label>First Name</label><input type="text" id="edit-fname" value="${esc(e.first_name)}"></div>
                <div class="form-group"><label>Last Name</label><input type="text" id="edit-lname" value="${esc(e.last_name)}"></div></div>
                <div class="form-row"><div class="form-group"><label>Email</label><input type="email" id="edit-email" value="${esc(e.email)}"></div>
                <div class="form-group"><label>Salary</label><input type="number" step="0.01" id="edit-salary" value="${e.salary}"></div></div>
            </form>`, `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="updateEmployee(${id})">Save</button>`);
    } catch (err) { showAlert(err.message, 'error'); }
}

async function updateEmployee(id) {
    try {
        await api(`/hr/employees/${id}`, { method: 'PUT', body: JSON.stringify({
            first_name: document.getElementById('edit-fname').value, last_name: document.getElementById('edit-lname').value,
            email: document.getElementById('edit-email').value, salary: document.getElementById('edit-salary').value
        })});
        closeModal(); showAlert('Employee updated', 'success'); renderEmployees();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 18. Departments ===
async function renderDepartments() {
    showLoading();
    try {
        const depts = await api('/hr/departments');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Departments</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateDeptModal()">+ Add</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Name</th><th>Code</th><th>Description</th></tr></thead>
        <tbody>${depts.map(d => `<tr><td class="cell-primary">${esc(d.name)}</td><td class="mono">${esc(d.code || '—')}</td><td class="text-muted">${esc(d.description || '—')}</td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateDeptModal() {
    showModal('New Department', `
        <form id="form-dept"><div class="form-group"><label>Name <span class="req">*</span></label><input type="text" id="dept-name" required></div>
        <div class="form-group"><label>Code</label><input type="text" id="dept-code"></div>
        <div class="form-group"><label>Description</label><textarea id="dept-desc" rows="2"></textarea></div></form>`,
    `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createDept()">Create</button>`);
}

async function createDept() {
    try {
        await api('/hr/departments', { method: 'POST', body: JSON.stringify({ name: document.getElementById('dept-name').value, code: document.getElementById('dept-code').value || null, description: document.getElementById('dept-desc').value || null }) });
        closeModal(); showAlert('Department created', 'success'); renderDepartments();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 19. Designations ===
async function renderDesignations() {
    showLoading();
    try {
        const desgs = await api('/hr/designations');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Designations</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateDesgModal()">+ Add</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Title</th><th>Level</th><th>Description</th></tr></thead>
        <tbody>${desgs.map(d => `<tr><td class="cell-primary">${esc(d.title)}</td><td>${esc(d.level || '—')}</td><td class="text-muted">${esc(d.description || '—')}</td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateDesgModal() {
    showModal('New Designation', `
        <form><div class="form-group"><label>Title <span class="req">*</span></label><input type="text" id="desg-title" required></div>
        <div class="form-group"><label>Level</label><input type="text" id="desg-level"></div>
        <div class="form-group"><label>Description</label><textarea id="desg-desc" rows="2"></textarea></div></form>`,
    `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createDesg()">Create</button>`);
}

async function createDesg() {
    try {
        await api('/hr/designations', { method: 'POST', body: JSON.stringify({ title: document.getElementById('desg-title').value, level: document.getElementById('desg-level').value || null, description: document.getElementById('desg-desc').value || null }) });
        closeModal(); showAlert('Designation created', 'success'); renderDesignations();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 20. Payroll ===
async function renderPayroll() {
    showLoading();
    try {
        const payrolls = await api('/hr/payrolls');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Payroll</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreatePayrollModal()">+ Run Payroll</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Employee</th><th>Period</th><th class="text-right">Gross</th><th class="text-right">Deductions</th><th class="text-right">Net</th><th>Status</th><th></th></tr></thead>
        <tbody>${payrolls.map(p => `<tr><td class="cell-primary">${esc(p.employee_name || 'Emp #' + p.employee_id)}</td><td>${fmtDate(p.pay_period_start)} — ${fmtDate(p.pay_period_end)}</td><td class="text-right mono">${fmtCur(p.gross_salary)}</td><td class="text-right mono">${fmtCur(p.total_deductions)}</td><td class="text-right mono font-bold">${fmtCur(p.net_salary)}</td><td>${statusBadge(p.status)}</td>
        <td><div class="tbl-actions">${p.status === 'draft' ? `<button class="btn-icon" onclick="processPayroll(${p.id})" title="Process">▶</button><button class="btn-icon danger" onclick="cancelPayroll(${p.id})" title="Cancel">✕</button>` : ''}${p.status === 'processed' ? `<button class="btn-icon" onclick="payPayroll(${p.id})" title="Pay">₹</button>` : ''}</div></td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

async function processPayroll(id) { try { await api(`/hr/payrolls/${id}/process`, { method: 'POST' }); showAlert('Payroll processed', 'success'); renderPayroll(); } catch (err) { showAlert(err.message, 'error'); } }
async function payPayroll(id) { try { await api(`/hr/payrolls/${id}/pay`, { method: 'POST' }); showAlert('Payroll paid', 'success'); renderPayroll(); } catch (err) { showAlert(err.message, 'error'); } }
async function cancelPayroll(id) { try { await api(`/hr/payrolls/${id}/cancel`, { method: 'POST' }); showAlert('Payroll cancelled', 'success'); renderPayroll(); } catch (err) { showAlert(err.message, 'error'); } }

function showCreatePayrollModal() {
    showModalLg('Run Payroll', `
        <form id="form-payroll">
            <div class="form-row"><div class="form-group"><label>Employee ID <span class="req">*</span></label><input type="number" id="pr-emp" required></div>
            <div class="form-group"><label>Period Start <span class="req">*</span></label><input type="date" id="pr-start" required></div></div>
            <div class="form-row"><div class="form-group"><label>Period End <span class="req">*</span></label><input type="date" id="pr-end" required></div><div class="form-group"></div></div>
            <h4 style="margin:16px 0 8px;font-size:0.8125rem">Components</h4>
            <div id="pr-components">
                <div class="form-row cols-3"><div class="form-group"><label>Name</label><input type="text" id="prc-name-0" value="Basic Salary"></div><div class="form-group"><label>Type</label><select id="prc-type-0"><option value="earnings">Earnings</option><option value="deductions">Deductions</option></select></div><div class="form-group"><label>Amount</label><input type="number" step="0.01" id="prc-amt-0"></div></div>
            </div>
            <button type="button" class="btn btn-ghost btn-sm" onclick="addPayrollComponent()" style="margin-top:8px">+ Add Component</button>
        </form>`, `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createPayroll()">Create</button>`);
    window._prCompCount = 1;
}

function addPayrollComponent() {
    const i = window._prCompCount++;
    const div = document.createElement('div'); div.className = 'form-row cols-3';
    div.innerHTML = `<div class="form-group"><label>Name</label><input type="text" id="prc-name-${i}"></div><div class="form-group"><label>Type</label><select id="prc-type-${i}"><option value="earnings">Earnings</option><option value="deductions">Deductions</option></select></div><div class="form-group"><label>Amount</label><input type="number" step="0.01" id="prc-amt-${i}"></div>`;
    document.getElementById('pr-components').appendChild(div);
}

async function createPayroll() {
    const components = [];
    for (let i = 0; i < window._prCompCount; i++) {
        const name = document.getElementById(`prc-name-${i}`);
        if (!name || !name.value) continue;
        components.push({ component_name: name.value, component_type: document.getElementById(`prc-type-${i}`).value, amount: document.getElementById(`prc-amt-${i}`).value });
    }
    try {
        await api('/hr/payrolls', { method: 'POST', body: JSON.stringify({
            employee_id: parseInt(document.getElementById('pr-emp').value),
            pay_period_start: document.getElementById('pr-start').value,
            pay_period_end: document.getElementById('pr-end').value, components
        })});
        closeModal(); showAlert('Payroll created', 'success'); renderPayroll();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 21. Inventory Items ===
async function renderItems() {
    showLoading();
    try {
        const items = await api('/inventory/items');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Inventory Items</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateItemModal()">+ Add Item</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Code</th><th>Name</th><th>Category</th><th class="text-right">Unit Price</th><th class="text-right">Stock</th><th class="text-right">Value</th><th>Reorder</th></tr></thead>
        <tbody>${items.map(i => `<tr><td class="cell-primary mono">${esc(i.code)}</td><td>${esc(i.name)}</td><td>${esc(i.category_name || '—')}</td><td class="text-right mono">${fmtCur(i.unit_price)}</td><td class="text-right">${parseFloat(i.current_stock)}</td><td class="text-right mono">${fmtCur(i.stock_value)}</td><td>${parseFloat(i.current_stock) <= parseFloat(i.reorder_level || 0) ? '<span class="badge badge-danger">Low</span>' : '<span class="badge badge-success">OK</span>'}</td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateItemModal() {
    showModal('New Item', `
        <form><div class="form-row"><div class="form-group"><label>Code <span class="req">*</span></label><input type="text" id="item-code" required></div>
        <div class="form-group"><label>Name <span class="req">*</span></label><input type="text" id="item-name" required></div></div>
        <div class="form-row"><div class="form-group"><label>Category ID</label><input type="number" id="item-cat"></div>
        <div class="form-group"><label>Unit Price <span class="req">*</span></label><input type="number" step="0.01" id="item-price" required></div></div>
        <div class="form-row"><div class="form-group"><label>Unit</label><input type="text" id="item-unit" value="pcs"></div>
        <div class="form-group"><label>Reorder Level</label><input type="number" id="item-reorder" value="10"></div></div></form>`,
    `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createItem()">Create</button>`);
}

async function createItem() {
    try {
        await api('/inventory/items', { method: 'POST', body: JSON.stringify({
            code: document.getElementById('item-code').value, name: document.getElementById('item-name').value,
            category_id: parseInt(document.getElementById('item-cat').value) || null,
            unit_price: document.getElementById('item-price').value, unit: document.getElementById('item-unit').value || 'pcs',
            reorder_level: parseInt(document.getElementById('item-reorder').value) || 10
        })});
        closeModal(); showAlert('Item created', 'success'); renderItems();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 22. Categories ===
async function renderCategories() {
    showLoading();
    try {
        const cats = await api('/inventory/categories');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Item Categories</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateCatModal()">+ Add</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Name</th><th>Description</th></tr></thead>
        <tbody>${cats.map(c => `<tr><td class="cell-primary">${esc(c.name)}</td><td class="text-muted">${esc(c.description || '—')}</td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateCatModal() {
    showModal('New Category', `<form><div class="form-group"><label>Name <span class="req">*</span></label><input type="text" id="cat-name" required></div><div class="form-group"><label>Description</label><textarea id="cat-desc" rows="2"></textarea></div></form>`,
    `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createCat()">Create</button>`);
}

async function createCat() {
    try {
        await api('/inventory/categories', { method: 'POST', body: JSON.stringify({ name: document.getElementById('cat-name').value, description: document.getElementById('cat-desc').value || null }) });
        closeModal(); showAlert('Category created', 'success'); renderCategories();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 23. Warehouses ===
async function renderWarehouses() {
    showLoading();
    try {
        const whs = await api('/inventory/warehouses');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Warehouses</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateWhModal()">+ Add</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Name</th><th>Location</th><th>Description</th></tr></thead>
        <tbody>${whs.map(w => `<tr><td class="cell-primary">${esc(w.name)}</td><td>${esc(w.location || '—')}</td><td class="text-muted">${esc(w.description || '—')}</td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateWhModal() {
    showModal('New Warehouse', `<form><div class="form-group"><label>Name <span class="req">*</span></label><input type="text" id="wh-name" required></div><div class="form-group"><label>Location</label><input type="text" id="wh-loc"></div><div class="form-group"><label>Description</label><textarea id="wh-desc" rows="2"></textarea></div></form>`,
    `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createWh()">Create</button>`);
}

async function createWh() {
    try {
        await api('/inventory/warehouses', { method: 'POST', body: JSON.stringify({ name: document.getElementById('wh-name').value, location: document.getElementById('wh-loc').value || null, description: document.getElementById('wh-desc').value || null }) });
        closeModal(); showAlert('Warehouse created', 'success'); renderWarehouses();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 24. Stock Ledger ===
async function renderStockLedger() {
    showLoading();
    try {
        const data = await api('/inventory/stock-ledger');
        const entries = Array.isArray(data) ? data : (data.entries || []);
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Stock Ledger</h3></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Date</th><th>Item</th><th>Type</th><th class="text-right">Qty</th><th>Warehouse</th><th>Reference</th></tr></thead>
        <tbody>${entries.length ? entries.map(e => `<tr><td>${fmtDate(e.created_at || e.date)}</td><td class="cell-primary">${esc(e.item_name || 'Item #' + e.item_id)}</td><td><span class="badge-flat ${e.transaction_type === 'in' || e.transaction_type === 'increase' ? 'green' : 'red'}">${e.transaction_type}</span></td><td class="text-right">${e.quantity}</td><td>${esc(e.warehouse_name || '—')}</td><td class="text-muted">${esc(e.reference || '—')}</td></tr>`).join('') : '<tr><td colspan="6" class="text-center text-muted" style="padding:24px">No stock movements yet</td></tr>'}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 25. Inventory Adjustments ===
async function renderInventoryAdjustments() {
    showLoading();
    try {
        const items = await api('/inventory/items');
        const whs = await api('/inventory/warehouses');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Inventory Adjustments</h3></div>
        <div class="card-body">
            <form id="form-adj">
                <div class="form-row cols-4">
                    <div class="form-group"><label>Item</label><select id="adj-item">${items.map(i => `<option value="${i.id}">${esc(i.code)} — ${esc(i.name)}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Warehouse</label><select id="adj-wh">${whs.map(w => `<option value="${w.id}">${esc(w.name)}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Type</label><select id="adj-type"><option value="increase">Increase</option><option value="decrease">Decrease</option></select></div>
                    <div class="form-group"><label>Quantity</label><input type="number" id="adj-qty" required></div>
                </div>
                <div class="form-group"><label>Reason</label><input type="text" id="adj-reason"></div>
                <button type="button" class="btn btn-primary" onclick="createAdjustment()">Submit Adjustment</button>
            </form>
        </div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

async function createAdjustment() {
    try {
        await api('/inventory/adjustments', { method: 'POST', body: JSON.stringify({
            item_id: parseInt(document.getElementById('adj-item').value), warehouse_id: parseInt(document.getElementById('adj-wh').value),
            adjustment_type: document.getElementById('adj-type').value, quantity: document.getElementById('adj-qty').value,
            reason: document.getElementById('adj-reason').value || null
        })});
        showAlert('Adjustment applied', 'success'); renderInventoryAdjustments();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 26. Purchase Orders ===
async function renderPurchaseOrders() {
    showLoading();
    try {
        const pos = await api('/procurement/purchase-orders');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Purchase Orders</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreatePOModal()">+ New PO</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>PO #</th><th>Supplier</th><th>Date</th><th class="text-right">Total</th><th>Status</th><th></th></tr></thead>
        <tbody>${pos.map(po => `<tr><td class="cell-primary">${esc(po.po_number)}</td><td>${esc(po.supplier_name || 'Supplier #' + po.supplier_id)}</td><td>${fmtDate(po.order_date)}</td><td class="text-right mono">${fmtCur(po.total_amount)}</td><td>${statusBadge(po.status)}</td>
        <td><div class="tbl-actions"><button class="btn-icon" onclick="viewPO(${po.id})" title="View">⊙</button>${po.status === 'draft' ? `<button class="btn-icon" onclick="approvePO(${po.id})" title="Approve">✓</button>` : ''}${po.status === 'approved' ? `<button class="btn-icon" onclick="receivePO(${po.id})" title="Receive">↓</button>` : ''}</div></td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

async function viewPO(id) {
    try {
        const po = await api(`/procurement/purchase-orders/${id}`);
        showModalLg(`Purchase Order — ${po.po_number}`, `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
                <div><span class="text-muted" style="font-size:0.75rem">Supplier</span><div style="font-weight:600">${esc(po.supplier_name || '')}</div></div>
                <div><span class="text-muted" style="font-size:0.75rem">Status</span><div>${statusBadge(po.status)}</div></div>
            </div>
            <table class="tbl"><thead><tr><th>Item</th><th class="text-right">Qty</th><th class="text-right">Unit Price</th><th class="text-right">Total</th></tr></thead>
            <tbody>${(po.items || []).map(i => `<tr><td class="cell-primary">${esc(i.item_name || 'Item #' + i.item_id)}</td><td class="text-right">${i.quantity}</td><td class="text-right mono">${fmtCur(i.unit_price)}</td><td class="text-right mono">${fmtCur(i.total_price || parseFloat(i.quantity) * parseFloat(i.unit_price))}</td></tr>`).join('')}</tbody>
            <tfoot><tr><td colspan="3" class="cell-primary">Total</td><td class="text-right mono">${fmtCur(po.total_amount)}</td></tr></tfoot></table>`);
    } catch (err) { showAlert(err.message, 'error'); }
}

async function approvePO(id) { try { await api(`/procurement/purchase-orders/${id}/approve`, { method: 'POST' }); showAlert('PO approved', 'success'); renderPurchaseOrders(); } catch (err) { showAlert(err.message, 'error'); } }

async function receivePO(id) {
    try {
        const whs = await api('/inventory/warehouses');
        if (!whs.length) { showAlert('No warehouses available', 'warning'); return; }
        await api(`/procurement/purchase-orders/${id}/receive?warehouse_id=${whs[0].id}`, { method: 'POST' });
        showAlert('PO received & inventory updated', 'success'); renderPurchaseOrders();
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreatePOModal() {
    showModalLg('New Purchase Order', `
        <form id="form-po">
            <div class="form-row"><div class="form-group"><label>Supplier ID <span class="req">*</span></label><input type="number" id="po-supplier" required></div>
            <div class="form-group"><label>Order Date</label><input type="date" id="po-date" required></div></div>
            <div class="form-group"><label>Expected Delivery</label><input type="date" id="po-delivery"></div>
            <h4 style="margin:16px 0 8px;font-size:0.8125rem">Items</h4>
            <div id="po-items">
                <div class="form-row cols-3"><div class="form-group"><label>Item ID</label><input type="number" id="poi-id-0"></div><div class="form-group"><label>Quantity</label><input type="number" id="poi-qty-0"></div><div class="form-group"><label>Unit Price</label><input type="number" step="0.01" id="poi-price-0"></div></div>
            </div>
            <button type="button" class="btn btn-ghost btn-sm" onclick="addPOItem()" style="margin-top:8px">+ Add Item</button>
        </form>`, `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createPO()">Create PO</button>`);
    window._poItemCount = 1;
}

function addPOItem() {
    const i = window._poItemCount++;
    const div = document.createElement('div'); div.className = 'form-row cols-3';
    div.innerHTML = `<div class="form-group"><label>Item ID</label><input type="number" id="poi-id-${i}"></div><div class="form-group"><label>Quantity</label><input type="number" id="poi-qty-${i}"></div><div class="form-group"><label>Unit Price</label><input type="number" step="0.01" id="poi-price-${i}"></div>`;
    document.getElementById('po-items').appendChild(div);
}

async function createPO() {
    const items = [];
    for (let i = 0; i < window._poItemCount; i++) {
        const id = document.getElementById(`poi-id-${i}`);
        if (!id || !id.value) continue;
        items.push({ item_id: parseInt(id.value), quantity: document.getElementById(`poi-qty-${i}`).value, unit_price: document.getElementById(`poi-price-${i}`).value });
    }
    try {
        await api('/procurement/purchase-orders', { method: 'POST', body: JSON.stringify({
            supplier_id: parseInt(document.getElementById('po-supplier').value), order_date: document.getElementById('po-date').value,
            expected_delivery_date: document.getElementById('po-delivery').value || null, items
        })});
        closeModal(); showAlert('Purchase order created', 'success'); renderPurchaseOrders();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 27. Suppliers ===
async function renderSuppliers() {
    showLoading();
    try {
        const sups = await api('/procurement/suppliers');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>Suppliers</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateSupplierModal()">+ Add</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Name</th><th>Contact</th><th>Email</th><th>Phone</th></tr></thead>
        <tbody>${sups.map(s => `<tr><td class="cell-primary">${esc(s.name)}</td><td>${esc(s.contact_person || '—')}</td><td>${esc(s.email || '—')}</td><td>${esc(s.phone || '—')}</td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateSupplierModal() {
    showModal('New Supplier', `
        <form><div class="form-group"><label>Name <span class="req">*</span></label><input type="text" id="sup-name" required></div>
        <div class="form-row"><div class="form-group"><label>Contact Person</label><input type="text" id="sup-contact"></div><div class="form-group"><label>Email</label><input type="email" id="sup-email"></div></div>
        <div class="form-row"><div class="form-group"><label>Phone</label><input type="text" id="sup-phone"></div><div class="form-group"><label>Address</label><input type="text" id="sup-addr"></div></div></form>`,
    `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createSupplier()">Create</button>`);
}

async function createSupplier() {
    try {
        await api('/procurement/suppliers', { method: 'POST', body: JSON.stringify({
            name: document.getElementById('sup-name').value, contact_person: document.getElementById('sup-contact').value || null,
            email: document.getElementById('sup-email').value || null, phone: document.getElementById('sup-phone').value || null,
            address: document.getElementById('sup-addr').value || null
        })});
        closeModal(); showAlert('Supplier created', 'success'); renderSuppliers();
    } catch (err) { showAlert(err.message, 'error'); }
}

// === 28. Users ===
async function renderUsers() {
    showLoading();
    try {
        const users = await api('/auth/users');
        document.getElementById('main-content').innerHTML = `<div class="fade-up">
        <div class="card"><div class="card-header"><h3>User Management</h3><div class="card-actions"><button class="btn btn-primary btn-sm" onclick="showCreateUserModal()">+ Add User</button></div></div>
        <div class="card-body flush"><div class="table-wrap"><table class="tbl"><thead><tr><th>Username</th><th>Role</th><th>Status</th><th></th></tr></thead>
        <tbody>${users.map(u => `<tr><td class="cell-primary">${esc(u.username)}</td><td><span class="badge badge-primary">${esc(u.role)}</span></td><td>${u.is_active ? '<span class="badge badge-success">Active</span>' : '<span class="badge badge-neutral">Inactive</span>'}</td>
        <td><div class="tbl-actions"><button class="btn-icon" onclick="showEditUserModal(${u.id}, '${esc(u.username)}', '${esc(u.role)}', ${u.is_active})" title="Edit">✎</button></div></td></tr>`).join('')}</tbody></table></div></div></div></div>`;
    } catch (err) { showAlert(err.message, 'error'); }
}

function showCreateUserModal() {
    showModal('New User', `<form><div class="form-group"><label>Username <span class="req">*</span></label><input type="text" id="user-name" required></div>
        <div class="form-group"><label>Password <span class="req">*</span></label><input type="password" id="user-pass" required></div>
        <div class="form-group"><label>Role <span class="req">*</span></label><select id="user-role"><option value="admin">Admin</option><option value="accountant">Accountant</option><option value="hr_manager">HR Manager</option><option value="inventory_manager">Inventory Manager</option></select></div></form>`,
    `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="createUser()">Create</button>`);
}

async function createUser() {
    try {
        await api('/auth/users', { method: 'POST', body: JSON.stringify({ username: document.getElementById('user-name').value, password: document.getElementById('user-pass').value, role: document.getElementById('user-role').value }) });
        closeModal(); showAlert('User created', 'success'); renderUsers();
    } catch (err) { showAlert(err.message, 'error'); }
}

function showEditUserModal(id, username, role, isActive) {
    showModal('Edit User', `<form><div class="form-group"><label>Username</label><input type="text" id="eu-name" value="${username}"></div>
        <div class="form-group"><label>New Password (leave blank to keep)</label><input type="password" id="eu-pass"></div>
        <div class="form-group"><label>Role</label><select id="eu-role"><option value="admin" ${role === 'admin' ? 'selected' : ''}>Admin</option><option value="accountant" ${role === 'accountant' ? 'selected' : ''}>Accountant</option><option value="hr_manager" ${role === 'hr_manager' ? 'selected' : ''}>HR Manager</option><option value="inventory_manager" ${role === 'inventory_manager' ? 'selected' : ''}>Inventory Manager</option></select></div></form>`,
    `<button class="btn btn-outline" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="updateUser(${id})">Save</button>`);
}

async function updateUser(id) {
    const data = { username: document.getElementById('eu-name').value, role: document.getElementById('eu-role').value };
    const pw = document.getElementById('eu-pass').value;
    if (pw) data.password = pw;
    try { await api(`/auth/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }); closeModal(); showAlert('User updated', 'success'); renderUsers(); } catch (err) { showAlert(err.message, 'error'); }
}

// === 29. AI Assistant ===
let assistantOpen = false;
let assistantTab = 'chat';

function initAssistant() {
    // Create FAB
    if (document.getElementById('assistant-fab')) return;
    const fab = document.createElement('button');
    fab.id = 'assistant-fab'; fab.className = 'assistant-fab'; fab.innerHTML = '✦'; fab.title = 'AI Assistant';
    fab.addEventListener('click', toggleAssistant);
    document.body.appendChild(fab);

    // Create panel
    const panel = document.createElement('div');
    panel.id = 'assistant-panel'; panel.className = 'assistant-panel';
    panel.innerHTML = `
        <div class="assistant-header"><h4>✦ FinCore Assistant</h4><button class="close-btn" onclick="toggleAssistant()">×</button></div>
        <div class="assistant-tabs">
            <div class="assistant-tab active" data-tab="chat" onclick="switchAssistantTab('chat')">Chat</div>
            <div class="assistant-tab" data-tab="insights" onclick="switchAssistantTab('insights')">Insights</div>
            <div class="assistant-tab" data-tab="summary" onclick="switchAssistantTab('summary')">Summary</div>
        </div>
        <div class="assistant-body" id="assistant-body">
            <div class="chat-container" id="chat-container">
                <div class="chat-welcome">
                    <div class="welcome-icon">✦</div>
                    <h5>How can I help?</h5>
                    <p>Ask me about your finances, inventory, or operations.</p>
                    <div class="quick-actions">
                        <button class="quick-action-btn" onclick="askAssistant('What is pending?')">What's pending?</button>
                        <button class="quick-action-btn" onclick="askAssistant('How is revenue?')">Revenue status</button>
                        <button class="quick-action-btn" onclick="askAssistant('Show anomalies')">Find anomalies</button>
                    </div>
                </div>
            </div>
        </div>
        <div class="assistant-input-area">
            <input type="text" id="assistant-input" placeholder="Ask anything…" onkeydown="if(event.key==='Enter')askAssistant()">
            <button onclick="askAssistant()">Send</button>
        </div>`;
    document.body.appendChild(panel);
}

function toggleAssistant() {
    assistantOpen = !assistantOpen;
    const panel = document.getElementById('assistant-panel');
    if (panel) panel.classList.toggle('active', assistantOpen);
}

function switchAssistantTab(tab) {
    assistantTab = tab;
    document.querySelectorAll('.assistant-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    if (tab === 'insights') loadInsights();
    else if (tab === 'summary') loadSummary();
    else showChatView();
}

function showChatView() {
    const body = document.getElementById('assistant-body');
    const chatEl = document.getElementById('chat-container');
    if (chatEl) body.innerHTML = chatEl.outerHTML;
}

async function loadInsights() {
    const body = document.getElementById('assistant-body');
    body.innerHTML = '<div class="assistant-loading">Loading insights…</div>';
    try {
        const data = await api('/assistant/insights');
        const insights = data.insights || [];
        body.innerHTML = insights.length ? insights.map(i => {
            const type = (i.type || i.category || '').toLowerCase();
            const cls = type.includes('warning') || type.includes('risk') ? 'warning' : type.includes('success') || type.includes('positive') ? 'success' : 'info';
            const icon = cls === 'warning' ? '⚠' : cls === 'success' ? '✓' : 'ℹ';
            return `<div class="insight-item ${cls}"><span class="icon">${icon}</span><div><div>${esc(i.message || i.insight)}</div>${i.action ? `<div class="insight-action">${esc(i.action)}</div>` : ''}</div></div>`;
        }).join('') : '<div class="assistant-empty"><div class="icon">✓</div><p>No insights — everything looks good!</p></div>';
    } catch (err) { body.innerHTML = `<div class="assistant-empty"><p>${esc(err.message)}</p></div>`; }
}

async function loadSummary() {
    const body = document.getElementById('assistant-body');
    body.innerHTML = '<div class="assistant-loading">Loading summary…</div>';
    try {
        const data = await api('/assistant/summary');
        body.innerHTML = `
            <div class="summary-card"><h5>Financial Overview</h5>
                <div class="summary-grid">
                    <div class="summary-item"><div class="label">Revenue</div><div class="value text-success">${fmtCur(data.total_revenue || 0)}</div></div>
                    <div class="summary-item"><div class="label">Expenses</div><div class="value text-danger">${fmtCur(data.total_expenses || 0)}</div></div>
                    <div class="summary-item"><div class="label">Net</div><div class="value">${fmtCur(data.net_income || 0)}</div></div>
                </div>
            </div>
            <div class="summary-card"><h5>Operations</h5>
                <div class="summary-grid">
                    <div class="summary-item"><div class="label">Employees</div><div class="value">${data.total_employees || 0}</div></div>
                    <div class="summary-item"><div class="label">Items</div><div class="value">${data.total_items || 0}</div></div>
                    <div class="summary-item"><div class="label">POs</div><div class="value">${data.total_purchase_orders || 0}</div></div>
                </div>
            </div>
            <div class="health-score"><div class="health-score-circle ${data.is_balanced ? 'excellent' : 'poor'}"><span class="value">${data.is_balanced ? '✓' : '!'}</span><span class="label">Health</span></div></div>`;
    } catch (err) { body.innerHTML = `<div class="assistant-empty"><p>${esc(err.message)}</p></div>`; }
}

async function askAssistant(message) {
    const input = document.getElementById('assistant-input');
    const msg = message || (input ? input.value.trim() : '');
    if (!msg) return;
    if (input) input.value = '';

    // Switch to chat tab
    if (assistantTab !== 'chat') switchAssistantTab('chat');

    const body = document.getElementById('assistant-body');
    // Remove welcome if present
    const welcome = body.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    // Add user message
    body.innerHTML += `<div class="chat-message user"><div class="msg-avatar">U</div><div class="msg-content">${esc(msg)}</div></div>`;
    body.innerHTML += `<div class="chat-message assistant loading" id="assistant-typing"><div class="msg-avatar">✦</div><div class="msg-content"><span class="typing-indicator"><span>●</span><span>●</span><span>●</span></span></div></div>`;
    body.scrollTop = body.scrollHeight;

    try {
        const data = await api('/assistant/chat', { method: 'POST', body: JSON.stringify({ message: msg }) });
        const typing = document.getElementById('assistant-typing');
        if (typing) typing.remove();

        const response = data.response || data.message || 'No response';
        body.innerHTML += `<div class="chat-message assistant"><div class="msg-avatar">✦</div><div class="msg-content">${response}</div></div>`;
        body.scrollTop = body.scrollHeight;
    } catch (err) {
        const typing = document.getElementById('assistant-typing');
        if (typing) typing.remove();
        body.innerHTML += `<div class="chat-message assistant"><div class="msg-avatar">✦</div><div class="msg-content">Sorry, I couldn't process that request.</div></div>`;
    }
}

// === 30. Init ===
document.addEventListener('DOMContentLoaded', () => {
    if (state.token) { checkAuth(); } else { showLoginPage(); }
});
