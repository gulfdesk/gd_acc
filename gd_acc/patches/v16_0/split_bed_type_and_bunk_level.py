import frappe

# Old Bed Type -> Bunk Level. Every other old type (Double, Other) becomes Single.
LEVELS = {"Bunk Lower": "Lower", "Bunk Middle": "Middle", "Bunk Upper": "Upper"}


def execute():
	"""Bed Type is now Single or Bunk, and a bunk bed keeps its level in Bunk Level."""
	for bed in frappe.get_all("Accommodation Bed", fields=["name", "bed_type", "bunk_level"]):
		is_bunk = bed.bed_type in LEVELS or bed.bed_type == "Bunk"
		level = (LEVELS.get(bed.bed_type) or bed.bunk_level) if is_bunk else None
		bed_type = "Bunk" if is_bunk else "Single"
		frappe.db.set_value(
			"Accommodation Bed",
			bed.name,
			{
				"bed_type": bed_type,
				"bunk_level": level,
				"bed_type_label": f"Bunk {level}" if is_bunk and level else bed_type,
			},
			update_modified=False,
		)
