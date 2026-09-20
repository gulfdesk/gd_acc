# Copyright (c) 2026, Rahmed-dev and contributors
# For license information, please see license.txt

from gd_acc.gd_accomodation.setup import create_accommodation_roles


def execute():
	"""Create accommodation roles before the doctypes that grant them permissions."""
	create_accommodation_roles()
