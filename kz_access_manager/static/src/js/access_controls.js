/** @odoo-module **/
import { onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { Chatter } from "@mail/chatter/web_portal/chatter";

// Data permissions are enforced in Python. These patches only remove matching
// presentation controls, using the caller's effective flags from the server.
function filterItems(items, flags) {
    const result = { ...items };
    if (flags.no_archive) {
        delete result.archive;
        delete result.unarchive;
    }
    if (flags.no_duplicate) {
        delete result.duplicate;
    }
    if (flags.no_export) {
        delete result.export;
    }
    if (flags.no_import) {
        delete result.import;
    }
    return result;
}

for (const Controller of [FormController, ListController]) {
    patch(Controller.prototype, {
        setup() {
            super.setup(...arguments);
            this.amFlags = {};
            const amOrm = useService("orm");
            onWillStart(async () => {
                this.amFlags = await amOrm.call(this.props.resModel, "am_ui_policy", []);
            });
        },
        getStaticActionMenuItems() {
            return filterItems(super.getStaticActionMenuItems(...arguments), this.amFlags || {});
        },
    });
}

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        this.amState = useState({ flags: {} });
        const amOrm = useService("orm");
        let generation = 0;
        const refresh = async (model) => {
            const current = ++generation;
            const flags = await amOrm.call(model, "am_ui_policy", []);
            if (current === generation) {
                this.amState.flags = flags;
            }
        };
        onWillStart(() => refresh(this.props.threadModel));
        onWillUpdateProps((nextProps) => {
            if (nextProps.threadModel !== this.props.threadModel) {
                return refresh(nextProps.threadModel);
            }
        });
    },
    get amFlags() {
        return this.amState.flags;
    },
});

if (session.am_hide_debug) {
    for (const [category, key] of [
        ["systray", "web.debug_mode_menu"],
        ["systray", "web.debug_mode"],
        ["user_menuitems", "debug"],
    ]) {
        try {
            registry.category(category).remove(key);
        } catch {
            // Entry name differs between versions; the server also clears debug mode.
        }
    }
    const url = new URL(window.location.href);
    if (url.searchParams.has("debug")) {
        url.searchParams.delete("debug");
        window.history.replaceState({}, "", url.toString());
    }
}
