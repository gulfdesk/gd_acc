# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

import json

import frappe

WORKSPACE_NAME = "Accommodation Management"

# Must be an id from Frappe's icon set, otherwise the workspace shows no icon.
WORKSPACE_ICON = "organization"

CARDS = [
	(
		"Dashboard",
		[("Page", "accommodation-dashboard", "Accommodation Dashboard")],
	),
	(
		"Masters",
		[
			("DocType", "Accommodation Location", "Locations"),
			("DocType", "Accommodation Site", "Accommodation Sites"),
			("DocType", "Accommodation Floor", "Floors"),
			("DocType", "Accommodation Room", "Rooms"),
			("DocType", "Accommodation Bed", "Beds"),
			("DocType", "Accommodation Item", "Accommodation Items"),
		],
	),
	(
		"Operations",
		[
			("DocType", "Accommodation Entitlement", "Accommodation Entitlement"),
			("DocType", "Accommodation Allocation", "Accommodation Allocation"),
			("DocType", "Accommodation Transfer", "Accommodation Transfer"),
			("DocType", "Bed Status History", "Bed Status History"),
			("DocType", "Accommodation Asset Assignment", "Asset Assignment"),
			("DocType", "Accommodation Maintenance", "Maintenance"),
		],
	),
	(
		"Setup",
		[("DocType", "Accommodation Bulk Setup", "Bulk Setup")],
	),
	(
		"Reports",
		[
			("Report", "Accommodation Occupancy", "Occupancy"),
			("Report", "Bed Availability", "Bed Availability"),
			("Report", "Employee Accommodation", "Employee Accommodation"),
			("Report", "Accommodation History", "Accommodation History"),
			("Report", "Bed Status History Report", "Bed Status History"),
			("Report", "Accommodation Asset Assignment Report", "Asset Assignment"),
			("Report", "Accommodation Maintenance Report", "Maintenance"),
		],
	),
]


def execute():
	"""Create the Accommodation Management workspace.

	Append-only and idempotent: links an administrator has added or reordered
	are left alone, and only missing entries are added back.
	"""
	workspace = get_or_create_workspace()
	existing = {(link.link_type, link.link_to) for link in workspace.links if link.type == "Link"}
	existing_cards = {link.label for link in workspace.links if link.type == "Card Break"}

	for card_label, links in CARDS:
		new_links = [link for link in links if (link[0], link[1]) not in existing and link_exists(link)]
		if not new_links and card_label in existing_cards:
			continue

		if card_label not in existing_cards:
			workspace.append("links", {"type": "Card Break", "label": card_label})
			existing_cards.add(card_label)

		for link_type, link_to, label in new_links:
			workspace.append(
				"links",
				{
					"type": "Link",
					"link_type": link_type,
					"link_to": link_to,
					"label": label,
					"is_query_report": 1 if link_type == "Report" else 0,
					"onboard": 0,
				},
			)

	workspace.icon = WORKSPACE_ICON
	workspace.content = json.dumps(build_content(workspace))
	workspace.flags.ignore_permissions = True
	workspace.save()


def link_exists(link):
	link_type, link_to, _label = link
	if link_type == "DocType":
		return frappe.db.exists("DocType", link_to)
	if link_type == "Report":
		return frappe.db.exists("Report", link_to)
	if link_type == "Page":
		return frappe.db.exists("Page", link_to)
	return False


def build_content(workspace):
	content = json.loads(workspace.content or "[]")
	card_names = {block.get("data", {}).get("card_name") for block in content if block.get("type") == "card"}

	if not any(block.get("type") == "header" for block in content):
		content.insert(
			0,
			{
				"id": frappe.generate_hash(length=10),
				"type": "header",
				"data": {
					"text": f'<span class="h4"><b>{WORKSPACE_NAME}</b></span>',
					"col": 12,
				},
			},
		)

	for link in workspace.links:
		if link.type != "Card Break" or link.label in card_names:
			continue

		content.append(
			{
				"id": frappe.generate_hash(length=10),
				"type": "card",
				"data": {"card_name": link.label, "col": 4},
			}
		)
		card_names.add(link.label)

	return content


def get_or_create_workspace():
	if frappe.db.exists("Workspace", WORKSPACE_NAME):
		return frappe.get_doc("Workspace", WORKSPACE_NAME)

	workspace = frappe.new_doc("Workspace")
	workspace.update(
		{
			"label": WORKSPACE_NAME,
			"title": WORKSPACE_NAME,
			"type": "Workspace",
			"module": "GD Accomodation",
			"icon": WORKSPACE_ICON,
			"public": 1,
			"content": "[]",
		}
	)
	workspace.flags.ignore_permissions = True
	workspace.insert()
	return workspace
