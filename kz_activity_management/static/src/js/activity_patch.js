import { Activity } from "@mail/core/web/activity";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { useState } from "@odoo/owl";

patch(Activity.prototype, {
    setup() {
        super.setup(...arguments);
        this.managementState = useState({pending: false});
    },
    async unlink() {
        if (!(await user.hasGroup("kz_activity_management.group_activity_employee"))) {
            return super.unlink(...arguments);
        }
        const action = await this.env.services.orm.call("mail.activity", "action_cancel_wizard", [[this.props.activity.id]]);
        await this.env.services.action.doAction(action, {onClose: async () => {
            this.props.onActivityChanged(this.thread);
            await this.thread.fetchNewMessages();
            this.env.bus.trigger("ACTIVITY_MANAGEMENT_CHANGED");
        }});
    },
    async managementTimer(method) {
        if (this.managementState.pending) { return; }
        this.managementState.pending = true;
        try {
            await this.env.services.orm.call("mail.activity", method, [[this.props.activity.id]]);
            this.props.onActivityChanged(this.thread);
            this.env.bus.trigger("ACTIVITY_MANAGEMENT_CHANGED");
        } finally { this.managementState.pending = false; }
    },
    async managementShare() {
        const action = await this.env.services.orm.call("mail.activity", "action_share_whatsapp", [[this.props.activity.id]]);
        return this.env.services.action.doAction(action);
    },
});
