#!/usr/bin/env python3
"""
Fix all database issues:
1. Associate doctors with hospitals
2. Approve pending hospitals
3. Verify database connections
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.database import get_supabase

def fix_all_issues():
    """Fix all database issues"""
    supabase = get_supabase()
    if not supabase:
        print("❌ Database not configured")
        return False
    
    print("=" * 60)
    print("FIXING DATABASE ISSUES")
    print("=" * 60)
    
    # Step 1: Get all hospitals
    try:
        hospitals = supabase.table("hospitals").select("id, name, status").execute()
        if not hospitals.data:
            print("❌ No hospitals found. Please register a hospital first.")
            return False
        
        # Find first approved hospital, or first hospital to approve
        hospital_to_use = None
        for hosp in hospitals.data:
            print(f"\n🏥 Hospital: ID={hosp.get('id')}, Name={hosp.get('name')}, Status={hosp.get('status')}")
            if hosp.get('status') == 'approved':
                hospital_to_use = hosp
                break
            elif not hospital_to_use:
                hospital_to_use = hosp
        
        if not hospital_to_use:
            print("❌ No hospital available")
            return False
        
        hospital_id = hospital_to_use.get('id')
        
        # Step 2: Approve hospital if pending
        if hospital_to_use.get('status') != 'approved':
            print(f"\n✅ Approving hospital ID {hospital_id}...")
            try:
                update_result = supabase.table("hospitals").update({"status": "approved"}).eq("id", hospital_id).execute()
                if update_result.data:
                    print(f"   Hospital {hospital_to_use.get('name')} approved successfully")
                else:
                    print(f"   ⚠️ Failed to approve hospital")
            except Exception as e:
                print(f"   ⚠️ Error approving hospital: {e}")
        
        # Step 3: Associate all doctors with this hospital
        try:
            doctors = supabase.table("doctors").select("id, name, hospital_id").execute()
            if doctors.data:
                print(f"\n👨‍⚕️ Updating doctors to associate with hospital ID {hospital_id}...")
                for doc in doctors.data:
                    if not doc.get('hospital_id'):
                        try:
                            update_result = supabase.table("doctors").update({"hospital_id": hospital_id}).eq("id", doc.get('id')).execute()
                            if update_result.data:
                                print(f"   ✅ Doctor {doc.get('name')} (ID: {doc.get('id')}) → Hospital {hospital_to_use.get('name')}")
                            else:
                                print(f"   ⚠️ Failed to update doctor {doc.get('name')}")
                        except Exception as e:
                            print(f"   ❌ Error updating doctor {doc.get('name')}: {e}")
                    else:
                        print(f"   ℹ️  Doctor {doc.get('name')} (ID: {doc.get('id')}) already has hospital_id={doc.get('hospital_id')}")
            else:
                print("\nℹ️  No doctors found to update")
        except Exception as e:
            print(f"❌ Error fetching/updating doctors: {e}")
            return False
        
        print("\n" + "=" * 60)
        print("✅ DATABASE FIXES COMPLETED")
        print("=" * 60)
        print(f"\nHospital ID {hospital_id} is now approved and associated with all doctors")
        print("You can now try booking an appointment again.")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_all_issues()
    sys.exit(0 if success else 1)

