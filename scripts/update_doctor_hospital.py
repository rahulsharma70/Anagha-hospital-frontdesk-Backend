#!/usr/bin/env python3
"""
Quick script to update a doctor's hospital association
Usage: python scripts/update_doctor_hospital.py <doctor_id> <hospital_id>
Example: python scripts/update_doctor_hospital.py 2 1
"""

import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.database import get_supabase

def update_doctor_hospital(doctor_id: int, hospital_id: int):
    """Update doctor's hospital_id"""
    supabase = get_supabase()
    if not supabase:
        print("❌ Database not configured")
        return False
    
    try:
        # Verify doctor exists in doctors table
        doctor_result = supabase.table("doctors").select("id, name").eq("id", doctor_id).eq("is_active", True).execute()
        if not doctor_result.data:
            print(f"❌ Doctor with ID {doctor_id} not found or is not active")
            return False
        
        doctor = doctor_result.data[0]
        print(f"📋 Doctor: {doctor.get('name')} (Doctor ID: {doctor_id})")
        
        # Verify hospital exists
        hospital_result = supabase.table("hospitals").select("id, name").eq("id", hospital_id).execute()
        if not hospital_result.data:
            print(f"❌ Hospital with ID {hospital_id} not found")
            return False
        
        hospital = hospital_result.data[0]
        print(f"🏥 Hospital: {hospital.get('name')} (ID: {hospital_id})")
        
        # Update doctor's hospital_id in doctors table
        update_result = supabase.table("doctors").update({"hospital_id": hospital_id}).eq("id", doctor_id).execute()
        
        if update_result.data:
            print(f"✅ Successfully associated doctor {doctor.get('name')} with hospital {hospital.get('name')}")
            return True
        else:
            print("❌ Failed to update doctor hospital")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/update_doctor_hospital.py <doctor_id> <hospital_id>")
        print("Example: python scripts/update_doctor_hospital.py 2 1")
        sys.exit(1)
    
    try:
        doctor_id = int(sys.argv[1])
        hospital_id = int(sys.argv[2])
    except ValueError:
        print("❌ Error: doctor_id and hospital_id must be integers")
        sys.exit(1)
    
    success = update_doctor_hospital(doctor_id, hospital_id)
    sys.exit(0 if success else 1)

