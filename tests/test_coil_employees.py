"""Test qm_coil/employees.py (SQLite :memory:)."""

from __future__ import annotations

import unittest

from qm_coil.db import open_db
from qm_coil.employees import (
    add_or_update_employee,
    bulk_import_employees,
    count_employees,
    delete_employee,
    get_employee_by_nik,
    list_employees,
    parse_employee_line,
)


class EmployeesTest(unittest.TestCase):
    def test_add_baru_dan_get(self):
        conn = open_db(":memory:")
        result = add_or_update_employee("12345678", "Budi Santoso", "1", conn)
        self.assertEqual(result, {"created": True, "updated": False})
        emp = get_employee_by_nik("12345678", conn)
        self.assertEqual(emp["name"], "Budi Santoso")
        self.assertEqual(emp["createdBy"], "1")

    def test_add_nik_sama_mengupdate(self):
        conn = open_db(":memory:")
        add_or_update_employee("12345678", "Budi", "1", conn)
        result = add_or_update_employee("12345678", "Budi Santoso", "2", conn)
        self.assertEqual(result, {"created": False, "updated": True})
        emp = get_employee_by_nik("12345678", conn)
        self.assertEqual(emp["name"], "Budi Santoso")
        self.assertEqual(emp["createdBy"], "2")

    def test_parse_line_format_valid(self):
        for line in [
            "12345678,Budi Santoso",
            "12345678;Budi Santoso",
            "12345678\tBudi Santoso",
            "12345678 Budi Santoso",
        ]:
            with self.subTest(line=line):
                parsed = parse_employee_line(line)
                self.assertEqual(parsed["nik"], "12345678")
                self.assertEqual(parsed["name"], "Budi Santoso")

    def test_parse_line_tidak_valid(self):
        self.assertIn("error", parse_employee_line(""))
        self.assertIn("error", parse_employee_line("tanpa-nik"))
        self.assertIn("error", parse_employee_line("1234567,Budi"))  # NIK 7 digit
        self.assertIn("error", parse_employee_line("12345678,A"))  # nama pendek

    def test_bulk_import(self):
        conn = open_db(":memory:")
        text = (
            "12345678,Budi Santoso\n"
            "87654321;Ani Wijaya\n"
            "baris-rusak\n"
            "12345678,Budi Update\n"
        )
        result = bulk_import_employees(text, "1", conn)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(count_employees(conn), 2)
        self.assertEqual(get_employee_by_nik("12345678", conn)["name"], "Budi Update")

    def test_list_count_delete(self):
        conn = open_db(":memory:")
        add_or_update_employee("12345678", "Budi", conn=conn)
        add_or_update_employee("87654321", "Ani", conn=conn)
        self.assertEqual(count_employees(conn), 2)
        names = [e["name"] for e in list_employees(conn=conn)]
        self.assertEqual(names, ["Ani", "Budi"])  # urut nama
        self.assertTrue(delete_employee("12345678", conn))
        self.assertFalse(delete_employee("12345678", conn))
        self.assertEqual(count_employees(conn), 1)


if __name__ == "__main__":
    unittest.main()
