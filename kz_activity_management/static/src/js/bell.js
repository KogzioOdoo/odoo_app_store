import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { user } from "@web/core/user";
import { useService, useBus } from "@web/core/utils/hooks";
import { deserializeDateTime } from "@web/core/l10n/dates";

export class ActivityBell extends Component {
    static template = "kz_activity_management.ActivityBell";
    static components = { Dropdown };
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.bus = useService("bus_service");
        this.state = useState({allowed: false, count: 0, timers: [], now: Date.now(), error: false, pending: false});
        this.alive = true;
        this.refresh = () => this.loadCount();
        useBus(this.env.bus, "ACTIVITY_MANAGEMENT_CHANGED", this.refresh);
        onWillStart(async () => {
            this.state.allowed = await user.hasGroup("kz_activity_management.group_activity_employee");
            if (this.state.allowed) { await this.loadCount(); }
        });
        onMounted(() => {
            if (this.state.allowed) {
                this.interval = setInterval(this.refresh, 30000);
                this.clock = setInterval(() => { this.state.now = Date.now(); }, 1000);
                this.bus.subscribe("mail.activity/updated", this.refresh);
            }
        });
        onWillUnmount(() => {
            this.alive = false;
            clearInterval(this.interval); clearInterval(this.clock);
            if (this.state.allowed) { this.bus.unsubscribe("mail.activity/updated", this.refresh); }
        });
    }
    async loadCount() {
        if (!this.state.allowed) { return; }
        try {
            const [count, timers] = await Promise.all([
                this.orm.call("mail.activity", "get_bell_count", []),
                this.orm.call("mail.activity", "get_running_timers", []),
            ]);
            if (this.alive) { this.state.count = count; this.state.timers = timers; this.state.error = false; }
        } catch {
            // A visible refresh indicator retains the last known value. This is
            // network/UI recovery, not suppression of a business-operation error.
            if (this.alive) { this.state.error = true; }
        }
    }
    elapsed(timer) {
        const seconds = Math.max(0, Math.floor((this.state.now - deserializeDateTime(timer.start).toMillis()) / 1000));
        return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map(v => String(v).padStart(2, "0")).join(":");
    }
    async onClick() { await this.action.doAction(await this.orm.call("mail.activity", "action_open_bell_activity", [])); }
    openTimer(timer) {
        return this.action.doAction({type: "ir.actions.act_window", res_model: "mail.activity", res_id: timer.activity_id,
            views: [[timer.form_view_id, "form"]], context: {active_test: false}});
    }
    async stopTimer(timer) {
        if (this.state.pending) { return; }
        this.state.pending = true;
        try { await this.orm.call("mail.activity", "action_stop_timer", [[timer.activity_id]]); await this.loadCount(); }
        finally { if (this.alive) { this.state.pending = false; } }
    }
}
registry.category("systray").add("kz_activity_management.bell", {Component: ActivityBell}, {sequence: 20});
