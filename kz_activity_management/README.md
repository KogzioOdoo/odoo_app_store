# Activity Management for Odoo 19

**Technical name:** `kz_activity_management`  
**Version:** `19.0.1.1.0`  
**License:** LGPL-3  
**Publisher:** Kogzio Solutions

A practical activity-management workspace for Odoo 19. Plan customer follow-ups, coordinate team responsibilities, track work, and monitor deadlines from a central dashboard—while retaining Odoo's native activity, business-document, and chatter workflows.

Designed for **Odoo 19 Community and Enterprise** using standard Odoo dependencies. Community runtime testing is documented; Enterprise runtime testing should be verified separately before making a tested-compatibility claim.

## Key features

### Dashboard and daily work

- Five status cards: **All Activities**, **Planned & Today**, **Completed**, **Overdue**, and **Cancelled**.
- Activity table with filtering, pagination, configurable records per page, and quick **View** / **Origin** actions.
- Filter and navigate activities by relevant criteria such as activity type, assignee, supervisor, customer, priority, linked document, and deadline.
- My Activities and Team Activities views, with access determined by role and permitted company.
- Create activities through the module or the existing Odoo business-document scheduling flow.
- Activity priority and colored, company-aware tags.

### Assignment, supervision, and access

- Assign a separate activity to each selected person (**Individual**) or manage a single activity shared by multiple participants (**Shared**).
- Supervisor/team relationships and employee, supervisor, and manager access scopes.
- Server-side activity access checks, including direct-link access; native Odoo source-document permissions still apply.
- Company-aware activity visibility and tag configuration.
- Optional, explicitly enabled portal activity access with scoped activity viewing and supported completion workflows.

### Activity lifecycle and history

- Mark activities **Done** with completion feedback; use **Done & Schedule Next** where supported by the native workflow.
- Cancel with a reason, reopen an activity, and retain an audit-style history of completion, cancellation, reopening, and reassignment events.
- Inspect the actor, responsible person, event time, and event details in activity history.
- Work with activities from Odoo chatter, with extended details and supported inline actions while preserving native workflows.

### Time tracking

- Start and stop per-user activity timers.
- Review recorded work sessions and durations in **Time Tracking History**.
- Set **Estimated Hours** and review calculated **Time Spent** and **Remaining Hours**.
- Access running-timer information from the module's timer controls.

### Recurring activities

- Configure recurring activities by interval and unit: **days, weeks, months, or years**, with an optional end date.
- Generate the next activity after the current recurring activity is completed, through the scheduled recurrence job.
- Preserve relevant assignment and linked-document context when creating the next occurrence.
- Track whether the next occurrence has been created and display recurrence errors when attention is needed.

### Reminders and notifications

- Set a date and time for an activity reminder.
- Scheduled **Activity Alarms** can broadcast a popup reminder; pending reminders can remain in the work bell until acknowledged.
- Queue **due-today** and **overdue/missed** activity emails using Odoo scheduled actions.
- Track due/overdue queue flags and notification errors to support operational troubleshooting.
- Configure **Due and Overdue Emails**, **Reminder Popups**, and dashboard table limits in Settings.

**Important:** A queued email is not proof of delivery. Actual delivery requires a working Odoo outgoing mail server and valid recipient addresses. The bell's due-work count should not be described as a general unread-message inbox.

### Chatter, sharing, and reporting

- Display additional activity details within Odoo chatter and use supported activity actions there.
- Share activity information through a **user-confirmed WhatsApp link**; the user controls whether and to whom information is sent.
- Review activities through supported **List, Graph, and Pivot** reporting views.
- Use Contacts mass scheduling where the corresponding source action is available; this is not a general-purpose dynamic mass-action designer.
- Contextual field help and user-facing guidance for the module's custom settings and workflows.

## Installation

1. Copy the `kz_activity_management` directory into an Odoo addons path.
2. Restart Odoo and update the Apps list.
3. Search for **Activity Management** and install the module.
4. Configure users, supervisors, companies, and module settings as needed.
5. Configure Odoo outgoing email if you intend to deliver due/overdue notifications.

Install using the Odoo command line, if preferred:

```bash
odoo-bin -c odoo.conf -d YOUR_DB -i kz_activity_management --stop-after-init
```

For an existing installation, **upgrade rather than uninstalling**:

```bash
odoo-bin -c odoo.conf -d YOUR_DB -u kz_activity_management --stop-after-init
```

Back up the database **and filestore** before upgrading. Test upgrades on a staging copy, particularly when migrating existing timers, tags, scheduled jobs, and email templates.

## Dependencies and compatibility

- **Odoo:** 19.0
- **Editions:** Community and Enterprise design target; confirm Enterprise behavior in the deployment environment.
- **Direct addon dependencies described by the project:** `mail`, `portal`; standard `web` functionality is used through Odoo's dependency stack.
- CRM, Sales, Contacts, and other source-document applications are optional integrations subject to their own installed modules and access rights.

Confirm the exact dependency list and version against the shipping `__manifest__.py` before submission.

## Quick start

1. Open **Activity Management** and review the dashboard's five status cards.
2. Open **Activities** to create or find a task, then choose its activity type, assignee, supervisor, deadline, priority, and related document.
3. For multiple participants, choose **Individual** or **Shared** assignment as appropriate.
4. Optionally set estimated hours, a reminder, or a recurrence rule.
5. Use **Start Timer** / **Stop Timer** to record work.
6. Complete the activity with feedback, or cancel with a reason. Review its history afterward.
7. Supervisors can review authorized team activities; managers can use the permitted reporting and configuration options.

## Scheduled actions

The module uses scheduled actions for recurring work and notifications, including:

| Scheduled action | Purpose |
| --- | --- |
| Activity Management: Create Recurring Activity | Creates the next eligible recurring activity after completion |
| Activity Management: Activity Alarms | Processes scheduled reminder broadcasts |
| Activity Management: Due and Missed Notifications | Queues due-today and overdue notification emails |

Scheduled jobs must be enabled and allowed to run. Avoid repeatedly triggering them in a production database merely for testing.

## Roles and security

| Role | Intended scope |
| --- | --- |
| Employee | Activities assigned to or otherwise legitimately accessible by that user |
| Supervisor | Own activities and authorized team activities |
| Manager | Broader activity oversight and delegated configuration, subject to company and native Odoo permissions |
| Enabled portal user | Only the supported, explicitly authorized portal activity scope |

UI visibility is not a substitute for access control. Odoo's server-side rules and permissions on both activities and linked source documents remain relevant. Do not assume unrestricted cross-company access for managers.

## Verification and release notes

Functional checks carried out during development included dashboard navigation, employee/team activity visibility, timers, completion/cancellation/reopening and history, individual/shared assignment, recurrence creation and duplicate prevention, due/overdue email queueing, and denial of an unauthorized direct activity URL. These checks do **not** establish that every role, company combination, portal route, or deployment has been exhaustively tested.

**Known operational distinctions:**

- Actual SMTP email delivery was not established in the local test environment; queued messages were observed.
- The native scheduling flow and source-document permissions should be checked in the target database.
- The module does not claim a general-purpose mass-action designer, before/after-N-day email rule editor, bulk-completion editor, or custom Kanban/Calendar view where those features are not implemented.
- Version, screenshots, guides, and final compatibility claims must match the actual shipping source code.

## Support and privacy

**Kogzio Solutions**  
Email: [info@kogzio.com](mailto:info@kogzio.com)  
Website: [https://www.kogzio.com/](https://www.kogzio.com/)

The module is described as using Odoo's configured mail infrastructure, without a vendor telemetry or activation service. WhatsApp sharing opens a prefilled link containing activity context; review the information before choosing to send it.

For installation or usage questions, contact the publisher with the Odoo version, module version, and relevant error details (excluding passwords or other secrets).
