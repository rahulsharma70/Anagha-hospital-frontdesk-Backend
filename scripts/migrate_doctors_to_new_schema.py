#!/usr/bin/env python3
"""
Migration script to move doctors from users table to doctors table
This script migrates existing doctors to the new schema structure
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database import get_supabase

def migrate_doctors():
    """Migrate doctors from users table to doctors table"""
    supabase = get_supabase()
    if not supabase:
        print("❌ Database not configured")
        return False
    
    print("=" * 60)
    print("MIGRATING DOCTORS TO NEW SCHEMA")
    print("=" * 60)
    
    try:
        # Step 1: Get all doctors from users table
        print("\n1. Fetching doctors from users table...")
        doctors_from_users = supabase.table("users").select("*").eq("role", "doctor").execute()
        
        if not doctors_from_users.data:
            print("   ℹ️  No doctors found in users table")
            return True
        
        print(f"   ✅ Found {len(doctors_from_users.data)} doctors in users table")
        
        # Step 2: Migrate each doctor
        migrated = 0
        skipped = 0
        errors = 0
        
        for user_doctor in doctors_from_users.data:
            user_id = user_doctor.get("id")
            name = user_doctor.get("name")
            mobile = user_doctor.get("mobile")
            hospital_id = user_doctor.get("hospital_id")
            
            print(f"\n   Migrating doctor: {name} (ID: {user_id})")
            
            # Check if doctor already exists in doctors table
            existing = supabase.table("doctors").select("id").eq("user_id", user_id).execute()
            if existing.data:
                print(f"      ⏭️  Doctor already exists in doctors table (ID: {existing.data[0]['id']})")
                skipped += 1
                continue
            
            # Check if doctor exists by name and mobile
            existing_by_name = supabase.table("doctors").select("id").eq("name", name).eq("mobile", mobile).execute()
            if existing_by_name.data:
                print(f"      ⏭️  Doctor already exists by name/mobile (ID: {existing_by_name.data[0]['id']})")
                skipped += 1
                continue
            
            # Check hospital_id is set
            if not hospital_id:
                print(f"      ⚠️  Warning: Doctor {name} has no hospital_id, skipping migration")
                errors += 1
                continue
            
            # Verify hospital exists
            hospital_check = supabase.table("hospitals").select("id").eq("id", hospital_id).execute()
            if not hospital_check.data:
                print(f"      ⚠️  Warning: Hospital ID {hospital_id} not found, skipping migration")
                errors += 1
                continue
            
            # Step 3: Create doctor record in doctors table
            try:
                doctor_record = {
                    "user_id": user_id,  # Link to users table for authentication
                    "hospital_id": hospital_id,
                    "name": name,
                    "mobile": mobile,
                    "email": user_doctor.get("email"),
                    "degree": user_doctor.get("degree"),
                    "institute_name": user_doctor.get("institute_name"),
                    "specialization": None,  # Can be set later
                    "experience1": user_doctor.get("experience1"),
                    "experience2": user_doctor.get("experience2"),
                    "experience3": user_doctor.get("experience3"),
                    "experience4": user_doctor.get("experience4"),
                    "is_active": user_doctor.get("is_active", True),
                    "source": "migrated"
                }
                
                result = supabase.table("doctors").insert(doctor_record).execute()
                
                if result.data:
                    doctor_id = result.data[0]["id"]
                    print(f"      ✅ Successfully migrated (New Doctor ID: {doctor_id})")
                    migrated += 1
                else:
                    print(f"      ❌ Failed to insert doctor record")
                    errors += 1
                    
            except Exception as e:
                print(f"      ❌ Error migrating doctor: {e}")
                errors += 1
        
        # Summary
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"   Total doctors found: {len(doctors_from_users.data)}")
        print(f"   ✅ Successfully migrated: {migrated}")
        print(f"   ⏭️  Skipped (already exists): {skipped}")
        print(f"   ❌ Errors: {errors}")
        print("=" * 60)
        
        if migrated > 0:
            print("\n✅ Migration completed successfully!")
            print("\n⚠️  IMPORTANT: After migration, you should:")
            print("   1. Verify all doctors are visible in doctors table")
            print("   2. Test appointment booking with migrated doctors")
            print("   3. Optionally remove role='doctor' from users table (keep users for auth)")
        else:
            print("\nℹ️  No new doctors were migrated (all already exist or have errors)")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate_doctors()
    sys.exit(0 if success else 1)

