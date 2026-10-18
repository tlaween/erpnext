# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import tempfile
from pathlib import Path
from unittest.mock import Mock

import frappe

from erpnext.accounts.doctype.chart_of_accounts_importer.chart_of_accounts_importer import (
	build_forest,
	map_matching_account_defaults,
	validate_accounts,
	validate_columns,
	validate_missing_roots,
)
from erpnext.tests.utils import ERPNextTestSuite

# columns: account_name, parent_account, account_number, parent_account_number,
#          is_group, account_type, root_type, account_currency
ROOT = ["Assets", "Assets", "", "", 1, "", "Asset", "INR"]
CHILD = ["Cash", "Assets", "", "", 0, "Cash", "Asset", "INR"]


class TestChartofAccountsImporter(ERPNextTestSuite):
	"""The importer parses an uploaded CoA into a nested tree and validates its
	shape. These cover the parsing/validation helpers without a file upload."""

	def test_validate_columns_rejects_blank_file(self):
		self.assertRaises(frappe.ValidationError, validate_columns, [])

	def test_validate_columns_requires_eight_columns(self):
		self.assertRaises(frappe.ValidationError, validate_columns, [["a", "b", "c"]])
		# the standard template width passes
		validate_columns([ROOT])

	def test_build_forest_nests_child_under_parent(self):
		forest = build_forest([ROOT, CHILD])
		self.assertIn("Assets", forest)
		self.assertIn("Cash", forest["Assets"])

	def test_build_forest_rejects_unknown_parent(self):
		orphan = ["Cash", "Missing Parent", "", "", 0, "Cash", "Asset", "INR"]
		self.assertRaises(frappe.ValidationError, build_forest, [orphan])

	def test_build_forest_requires_account_name(self):
		nameless = ["", "Assets", "", "", 0, "Cash", "Asset", "INR"]
		self.assertRaises(frappe.ValidationError, build_forest, [ROOT, nameless])

	def test_validate_accounts_handles_utf8_bom_and_self_parent_roots(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			file_path = Path(temp_dir) / "coa.csv"
			file_path.write_text(
				"\ufeffAccount Name,Parent Account,Account Number,Parent Account Number,"
				"Is Group,Account Type,Root Type,Account Currency\n"
				"Assets,Assets,,,1,,Asset,INR\n"
				"Liabilities,Liabilities,,,1,,Liability,INR\n"
				"Equity,Equity,,,1,,Equity,INR\n"
				"Income,Income,,,1,,Income,INR\n"
				"Expenses,Expenses,,,1,,Expense,INR\n",
				encoding="utf-8",
			)
			file_doc = Mock()
			file_doc.get_full_path.return_value = str(file_path)

			result = validate_accounts(file_doc, "csv")

		self.assertEqual(result, [True, 5])

	def test_map_matching_account_defaults_requires_unique_identity(self):
		source_defaults = {
			"default_bank_account": "source-bank",
			"default_cash_account": "source-cash",
			"default_income_account": "source-income",
			"default_expense_account": None,
		}
		source_accounts = [
			frappe._dict(
				name="source-bank",
				account_number="100",
				account_type="Bank",
				root_type="Asset",
				is_group=0,
			),
			frappe._dict(
				name="source-cash",
				account_number="101",
				account_type="Cash",
				root_type="Asset",
				is_group=0,
			),
			frappe._dict(
				name="source-income",
				account_number="400",
				account_type="Income Account",
				root_type="Income",
				is_group=0,
			),
		]
		target_accounts = [
			frappe._dict(
				name="target-bank",
				account_number="100",
				account_type="Bank",
				root_type="Asset",
				is_group=0,
			),
			frappe._dict(
				name="target-cash",
				account_number="101",
				account_type="Cash",
				root_type="Asset",
				is_group=0,
			),
			frappe._dict(
				name="target-income-one",
				account_number="400",
				account_type="Income Account",
				root_type="Income",
				is_group=0,
			),
			frappe._dict(
				name="target-income-two",
				account_number="400",
				account_type="Income Account",
				root_type="Income",
				is_group=0,
			),
		]

		self.assertEqual(
			map_matching_account_defaults(source_defaults, source_accounts, target_accounts),
			{"default_bank_account": "target-bank", "default_cash_account": "target-cash"},
		)

	def test_validate_missing_roots_requires_all_root_types(self):
		present = ("Asset", "Liability", "Expense", "Income")  # Equity missing
		self.assertRaises(
			frappe.ValidationError,
			validate_missing_roots,
			[{"root_type": rt} for rt in present],
		)
		# all five root types present -> no error
		validate_missing_roots(
			[{"root_type": rt} for rt in ("Asset", "Liability", "Expense", "Income", "Equity")]
		)
