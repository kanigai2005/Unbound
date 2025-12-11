function app() {
    return {
        apiKey: localStorage.getItem('gateway_key') || '',
        user: {},
        commandInput: '',
        sessionLogs: [],
        history: [],
        rules: [],
        adminLogs: [],
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
                    setInterval(() => this.refreshAdminLogs(), 5000);
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
                }
            }
        },

        async refreshAdminLogs() {
            if (this.user.role === 'admin') {
                this.adminLogs = await this.api('/admin/audit');
            }
        },

        async submitCommand() {
            if (!this.commandInput) return;
            const cmd = this.commandInput;
            this.commandInput = '';
            
            const res = await this.api('/commands', 'POST', { command_text: cmd });
            if (res) {
                this.user.credits = res.new_balance;
                let color = res.status === 'executed' ? 'text-green-400' : 'text-red-400';
                this.sessionLogs.unshift({ cmd: cmd, msg: res.message, color: color });
                this.loadData();
            }
        },

        async addRule() {
            if (!this.newRulePattern) return;
            const res = await this.api('/admin/rules', 'POST', { pattern: this.newRulePattern, action: this.newRuleAction });
            if (res) { this.newRulePattern = ''; this.loadData(); }
        },

        // NEW: Delete Rule Logic
        async deleteRule(id) {
            if(!confirm("Are you sure you want to delete this rule?")) return;
            const res = await this.api(`/admin/rules/${id}`, 'DELETE');
            if (res) this.loadData();
        },

        async createUser() {
            if (!this.newUserName) return;
            const res = await this.api('/admin/users', 'POST', { username: this.newUserName, role: 'member' });
            if (res) { this.lastCreatedUser = res.api_key; this.newUserName = ''; }
        },

        formatDate(isoStr) {
            return new Date(isoStr).toLocaleTimeString();
        }
    }
}