from odoo import fields, models

class ActivityFeedbackWizard(models.TransientModel):
    _name = 'activity.feedback.wizard'
    _description = 'Activity Feedback Wizard'

    activity_id = fields.Many2one('mail.activity', string='Activity', required=True, ondelete='cascade')
    feedback = fields.Text(string='Feedback')

    def action_done(self):
        self.ensure_one()
        self.activity_id.action_feedback(feedback=self.feedback)
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': self.env._('Activity Completed'), 'message': self.env._('Feedback and completion history have been saved.'), 'type': 'success', 'next': {'type': 'ir.actions.act_window_close'}}}

    def action_done_schedule_next(self):
        self.ensure_one()
        return self.activity_id.action_feedback_schedule_next(
            feedback=self.feedback)
