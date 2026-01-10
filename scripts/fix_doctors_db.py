#!/usr/bin/env python3
"""
Fix doctors database issues:
1. List all doctors in users table
2. List all doctors in doctors table
3. Show hospital associations
4. Optionally sync data or fix hospital_id
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database import get_supabase

def check_doctors():
    """Check doctors in both tables"""
    supabase = get_supabase()
    if not supabase:
        print("❌ Database not configured")
        return
    
    print("=" * 60)
    print("DOCTORS IN DOCTORS TABLE (web backend uses this now)")
    print("=" * 60)
    
    try:
        doctors_table = supabase.table("doctors").select("*").execute()
        if doctors_table.data:
            for doc in doctors_table.data:
                print(f"\nDoctor ID: {doc.get('id')}")
                print(f"  User ID: {doc.get('user_id', 'N/A')} (for auth)")
                print(f"  Name: {doc.get('name', 'N/A')}")
                print(f"  Mobile: {doc.get('mobile', 'N/A')}")
                print(f"  Hospital ID: {doc.get('hospital_id', 'N/A')} {'⚠️ MISSING' if not doc.get('hospital_id') else ''}")
                print(f"  Active: {doc.get('is_active', 'N/A')}")
                print(f"  Degree: {doc.get('degree', 'N/A')}")
                print(f"  Specialization: {doc.get('specialization', 'N/A')}")
                print(f"  Source: {doc.get('source', 'N/A')}")
        else:
            print("  No doctors found in doctors table")
    except Exception as e:
        print(f"❌ Error fetching from doctors table: {e}")
    
    print("\n" + "=" * 60)
    print("HOSPITALS AVAILABLE")
    print("=" * 60)
    
    try:
        hospitals = supabase.table("hospitals").select("id, name, status").execute()
        if hospitals.data:
            for hosp in hospitals.data:
                print(f"  ID: {hosp.get('id')}, Name: {hosp.get('name')}, Status: {hosp.get('status')}")
        else:
            print("  No hospitals found")
    except Exception as e:
        print(f"❌ Error fetching hospitals: {e}")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print("1. Doctors without hospital_id need to be associated with a hospital")
    print("2. Use: python scripts/update_doctor_hospital.py <doctor_id> <hospital_id>")
    print("3. Or update via Supabase dashboard directly")
    print("=" * 60)

if __name__ == "__main__":
    check_doctors()

