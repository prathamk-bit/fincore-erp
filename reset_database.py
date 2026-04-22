"""
Reset Database Script for FreshBite Foods ERP

This script deletes the existing database and creates a fresh one
with the Food & Beverage industry demo data.

Run this script from the erp_system directory:
    python reset_database.py
"""

import os
import sys

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, "erp_system.db")

print("=" * 60)
print("FreshBite Foods ERP - Database Reset")
print("=" * 60)

# Delete the database file if it exists
if os.path.exists(db_path):
    try:
        os.remove(db_path)
        print(f"✓ Deleted old database: {db_path}")
    except Exception as e:
        print(f"✗ Error deleting database: {e}")
        print("\nMake sure the application is not running!")
        sys.exit(1)
else:
    print(f"✓ No existing database found at: {db_path}")

print("\n" + "=" * 60)
print("Database deleted successfully!")
print("=" * 60)
print("\nNow restart your application:")
print("  python -m uvicorn backend.main:app --reload")
print("\nThe new Food & Beverage data will be loaded automatically.")
print("=" * 60)
