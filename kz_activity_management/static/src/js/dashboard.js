/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const EMPTY_FILTERS = {
    activity_type_id: "",
    user_id: "",
    supervisor_id: "",
    customer_id: "",
    priority: "",
    res_model: "",
    date_from: "",
    date_to: "",
};

export class ActivityDashboard extends Component {
    static template = "kz_activity_management.ActivityDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.sequence = 0;
        this.alive = true;

        this.cards = [
            { key: "all", label: _t("All Activities"), css: "o_card_all" },
            { key: "planned", label: _t("Planned & Today"), css: "o_card_planned" },
            { key: "completed", label: _t("Completed"), css: "o_card_completed" },
            { key: "overdue", label: _t("Overdue"), css: "o_card_overdue" },
            { key: "cancelled", label: _t("Cancelled"), css: "o_card_cancelled" },
        ];

        this.statuses = {
            overdue: { label: _t("Overdue"), css: "text-bg-danger" },
            today: { label: _t("Today"), css: "text-bg-warning" },
            planned: { label: _t("Planned"), css: "text-bg-info" },
            done: { label: _t("Done"), css: "text-bg-success" },
            cancelled: { label: _t("Cancelled"), css: "text-bg-secondary" },
        };

        this.state = useState({
            filters: { ...EMPTY_FILTERS },
            activeCard: "all",
            data: {
                counts: {},
                domains: {},
                views: {},
                options: {},
            },
            table: {
                records: [],
                total: 0,
                limit: 10,
                page: 0,
            },
            loading: true,
            error: "",
            rowPending: false,
        });

        this.dropdownOptions = useState({
            users: [],
            supervisors: [],
            customers: [],
        });

        onWillStart(async () => {
            await Promise.all([
                this.loadData(),
                this.loadDropdownOptions(),
            ]);
        });

        onWillUnmount(() => {
            this.alive = false;
            this.sequence++;
        });
    }

    get activeCardLabel() {
        return this.cards.find(
            card => card.key === this.state.activeCard
        ).label;
    }

    get pagerStart() {
        const { total, limit, page } = this.state.table;
        return total ? page * limit + 1 : 0;
    }

    get pagerEnd() {
        const { total, limit, page } = this.state.table;
        return Math.min((page + 1) * limit, total);
    }

    get hasPrev() {
        return this.state.table.page > 0;
    }

    get hasNext() {
        return this.pagerEnd < this.state.table.total;
    }

    get hasActiveFilters() {
        return Object.values(this.state.filters).some(Boolean);
    }

    getStars(priority) {
        return "★".repeat(Number(priority) || 0) || _t("Normal");
    }

    async loadDropdownOptions() {
        try {
            const [users, supervisors, customers] = await Promise.all([
                this.orm.call(
                    "mail.activity",
                    "get_dashboard_filter_options",
                    [],
                    { kind: "user_id", query: "" }
                ),
                this.orm.call(
                    "mail.activity",
                    "get_dashboard_filter_options",
                    [],
                    { kind: "supervisor_id", query: "" }
                ),
                this.orm.call(
                    "mail.activity",
                    "get_dashboard_filter_options",
                    [],
                    { kind: "customer_id", query: "" }
                ),
            ]);

            if (!this.alive) {
                return;
            }

            this.dropdownOptions.users = users || [];
            this.dropdownOptions.supervisors = supervisors || [];
            this.dropdownOptions.customers = customers || [];

        } catch (error) {
            if (this.alive) {
                this.notification.add(
                    _t("Unable to load dashboard filter options."),
                    { type: "warning" }
                );
            }
        }
    }

    async loadData() {
        const sequence = ++this.sequence;

        const request = {
            filters: { ...this.state.filters },
            card_key: this.state.activeCard,
            page: this.state.table.page,
        };

        this.state.loading = true;
        this.state.error = "";

        try {
            const snapshot = await this.orm.call(
                "mail.activity",
                "get_dashboard_snapshot",
                [],
                request
            );

            if (!this.alive || sequence !== this.sequence) {
                return;
            }

            this.state.data = snapshot.data;
            this.state.table = snapshot.table;

        } catch (error) {
            if (this.alive && sequence === this.sequence) {
                this.state.error =
                    error.data?.message ||
                    error.message ||
                    _t("Activities could not be loaded. Please retry.");
            }

        } finally {
            if (this.alive && sequence === this.sequence) {
                this.state.loading = false;
            }
        }
    }

    async loadTable() {
        return this.loadData();
    }

    async onFilterChange(key, ev) {
        this.state.filters[key] = ev.target.value;
        this.state.table.page = 0;
        await this.loadData();
    }

    async onClearFilters() {
        Object.assign(this.state.filters, EMPTY_FILTERS);
        this.state.table.page = 0;
        await this.loadData();
    }

    async onSelectCard(card) {
        this.state.activeCard = card.key;
        this.state.table.page = 0;
        await this.loadData();
    }

    async onPrevPage() {
        if (!this.state.loading && this.hasPrev) {
            this.state.table.page--;
            await this.loadData();
        }
    }

    async onNextPage() {
        if (!this.state.loading && this.hasNext) {
            this.state.table.page++;
            await this.loadData();
        }
    }

    onNewActivity() {
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("Schedule Activity"),
                res_model: "mail.activity.schedule",
                views: [[false, "form"]],
                target: "new",
                context: {},
            },
            {
                onClose: () => this.loadData(),
            }
        );
    }

    onOpenFullList() {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: this.activeCardLabel,
            res_model: "mail.activity",
            views: [
                [this.state.data.views.list, "list"],
                [this.state.data.views.form, "form"],
            ],
            domain: this.state.data.domains[this.state.activeCard],
            context: { active_test: false },
        });
    }

    async openRowWizard(method, record) {
        if (this.state.rowPending || this.state.loading) {
            return;
        }

        this.state.rowPending = true;

        try {
            const action = await this.orm.call(
                "mail.activity",
                method,
                [[record.id]]
            );

            await this.action.doAction(action, {
                onClose: () => this.loadData(),
            });

        } finally {
            if (this.alive) {
                this.state.rowPending = false;
            }
        }
    }

    onRowDone(record) {
        return this.openRowWizard("action_feedback_wizard", record);
    }

    onRowCancel(record) {
        return this.openRowWizard("action_cancel_wizard", record);
    }

    onRowView(record) {
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "mail.activity",
                res_id: record.id,
                views: [[this.state.data.views.form, "form"]],
                context: { active_test: false },
            },
            {
                onClose: () => this.loadData(),
            }
        );
    }

    async onRowOrigin(record) {
        const action = await this.orm.call(
            "mail.activity",
            "action_open_document",
            [[record.id]]
        );

        return this.action.doAction(action);
    }
}

registry.category("actions").add(
    "kz_activity_management.dashboard",
    ActivityDashboard
);
