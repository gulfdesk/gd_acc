## GD Accommodation Management — Migration Notes

Context for reviewers: the `gd_accomodation` module was ported from `akbm_erp` into this
standalone Frappe v16 app (`gd_acc`). This note summarizes what moved and what to check.

### What was ported
- Full `gd_accomodation` module, including doctypes:
  accommodation_allocation, accommodation_asset_assignment, accommodation_assigned_item,
  accommodation_bed, accommodation_bulk_setup, accommodation_bulk_setup_floor,
  accommodation_entitlement, accommodation_floor, accommodation_item, accommodation_location,
  accommodation_maintenance, accommodation_room, accommodation_site, accommodation_transfer,
  bed_status_history, gd_acc_settings
- Supporting `accommodation_utils.py`, `api.py`, and the Employee custom script
  (`custom/employee.js`)

### Dependencies
- Requires `hrms` (declared in `hooks.py` via `required_apps`)

### Review / test checklist
- [ ] Fresh Frappe v16 site: `bench get-app` + `bench install-app gd_acc` succeeds
- [ ] All accommodation doctypes load in the desk without migration errors
- [ ] Accommodation allocation/transfer flows behave the same as in `akbm_erp`
- [ ] Employee custom script (accommodation fields on Employee) renders correctly
- [ ] No regressions in HRMS features this module hooks into
