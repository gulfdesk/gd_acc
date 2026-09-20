app_name = "gd_acc"
app_title = "GD Accommodation Management"
app_publisher = "Gulf Desks"
app_description = "Employee accommodation and housing management"
app_email = "shahidkaleem@gulfdesks.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["frappe/hrms"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "gd_acc",
# 		"logo": "/assets/gd_acc/logo.png",
# 		"title": "GD Accommodation Management",
# 		"route": "/gd_acc",
# 		"has_permission": "gd_acc.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/gd_acc/css/gd_acc.css"
app_include_js = "accommodation.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/gd_acc/css/gd_acc.css"
# web_include_js = "/assets/gd_acc/js/gd_acc.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "gd_acc/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Employee": "gd_accomodation/custom/employee.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "gd_acc/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "gd_acc.utils.jinja_methods",
# 	"filters": "gd_acc.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "gd_acc.install.before_install"
after_install = "gd_acc.gd_accomodation.setup.setup_accommodation"
after_migrate = "gd_acc.gd_accomodation.setup.setup_accommodation"

# Uninstallation
# ------------

# before_uninstall = "gd_acc.uninstall.before_uninstall"
# after_uninstall = "gd_acc.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "gd_acc.utils.before_app_install"
# after_app_install = "gd_acc.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "gd_acc.utils.before_app_uninstall"
# after_app_uninstall = "gd_acc.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "gd_acc.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "gd_acc.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["gd_acc.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Employee": {
		"validate": "gd_acc.gd_accomodation.employee_hooks.validate_accommodation_status",
		"on_update": "gd_acc.gd_accomodation.employee_hooks.handle_accommodation_status_change",
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"gd_acc.tasks.all"
# 	],
# 	"daily": [
# 		"gd_acc.tasks.daily"
# 	],
# 	"hourly": [
# 		"gd_acc.tasks.hourly"
# 	],
# 	"weekly": [
# 		"gd_acc.tasks.weekly"
# 	],
# 	"monthly": [
# 		"gd_acc.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "gd_acc.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "gd_acc.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "gd_acc.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "gd_acc.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["gd_acc.utils.before_request"]
# after_request = ["gd_acc.utils.after_request"]

# Job Events
# ----------
# before_job = ["gd_acc.utils.before_job"]
# after_job = ["gd_acc.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"gd_acc.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

