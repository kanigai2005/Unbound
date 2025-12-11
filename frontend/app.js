function app() {
    return {
        apiKey: localStorage.getItem('gateway_key') || '',
        user: {},
        commandInput: '',
        sessionLogs: [],
        history: [],
        rules: [],
        adminLogs: [],
        approvals: [],
        newRulePattern: '',
        newRuleAction: 'AUTO_REJECT',
        newUserName: '',
        lastCreatedUser: null,

        async init() {
            const path = window.location.pathname;
            if (!this.apiKey && path !== '/login.html') {
                window.location.href = '/login.html';
            } else if (this.apiKey && path === '/login.html') {
                window.location.href = '/';
            } else if (this.apiKey) {
                await this.loadData();
                if(this.user.role === 'admin') {
                    // Poll for new data every 5 seconds
                    setInterval(() => this.refreshAdminData(), 5000);
                }
            }
        },

        logout() {
            localStorage.removeItem('gateway_key');
            window.location.href = '/login.html';
        },

        async api(endpoint, method = 'GET', body = null) {
            try {
                const opts = {
                    method,
                    headers: { 'X-API-Key': this.apiKey, 'Content-Type': 'application/json' }
                };
                if (body) opts.body = JSON.stringify(body);
                const res = await fetch('/api' + endpoint, opts);
                if (res.status === 401) { this.logout(); return; }
                if (!res.ok) {
                    const err = await res.json();
                    alert(err.detail || 'Error');
                    throw new Error(err);
                }
                return await res.json();
            } catch (e) { console.error(e); return null; }
        },

        async loadData() {
            this.user = await this.api('/me');
            if(this.user) {
                this.history = await this.api('/history');
                if (this.user.role === 'admin') {
                    this.rules = await this.api('/admin/rules');
                    this.adminLogs = await this.api('/admin/audit');
                    this.approvals = await this.api('/admin/approvals');
                }
            }
        },

        async refreshAdminData() {
            if (this.user.role === 'admin') {
                this.adminLogs = await this.api('/admin/audit');
                this.approvals = await this.api('/admin/approvals');
            }
        },

        async submitCommand() {
            if (!this.commandInput) return;
            const cmd = this.commandInput;
            this.commandInput = '';
            
            const res = await this.api('/commands', 'POST', { command_text: cmd });
            if (res) {
                this.user.credits = res.new_balance;
                
                let color = 'text-red-400';
                if(res.status === 'executed') color = 'text-green-400';
                if(res.status === 'pending') color = 'text-yellow-400';

                this.sessionLogs.unshift({ cmd: cmd, msg: res.message, color: color });
                this.loadData();
            }
        },

        async addRule() {
            if (!this.newRulePattern) return;
            const res = await this.api('/admin/rules', 'POST', { pattern: this.newRulePattern, action: this.newRuleAction });
            if (res) { this.newRulePattern = ''; this.loadData(); }
        },

        async deleteRule(id) {
            if(!confirm("Delete this rule?")) return;
            const res = await this.api(`/admin/rules/${id}`, 'DELETE');
            if (res) this.loadData();
        },

        async createUser() {
            if (!this.newUserName) return;
            const res = await this.api('/admin/users', 'POST', { username: this.newUserName, role: 'member' });
            if (res) { this.lastCreatedUser = res.api_key; this.newUserName = ''; }
        },

        // NEW: Manage Approvals
        async manageApproval(id, action) {
            const res = await this.api(`/admin/approvals/${id}/${action}`, 'POST');
            if(res) {
                // Remove from local list immediately for snappiness
                this.approvals = this.approvals.filter(a => a.id !== id);
                this.refreshAdminData();
            }
        },

        // --- Helpers ---
        formatDate(isoStr) { return new Date(isoStr).toLocaleTimeString(); },
        
        getActionColor(action) {
            if(action === 'AUTO_ACCEPT') return 'text-green-400';
            if(action === 'REQUIRE_APPROVAL') return 'text-yellow-400';
            return 'text-red-400';
        },
        
        getStatusClass(status) {
            if(status === 'executed') return 'text-green-500';
            if(status === 'pending_approval') return 'text-yellow-500';
            return 'text-red-500';
        }
    }
}