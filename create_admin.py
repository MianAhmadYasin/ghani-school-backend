"""
Create Admin User Script
Run this script to create an admin user for first-time setup
"""

import os
import sys
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_admin_user():
    """Create an admin user in Supabase"""
    
    # Get credentials
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
        sys.exit(1)
    
    # Create Supabase client
    supabase = create_client(supabase_url, supabase_service_key)
    
    # Get admin details
    print("\n🔐 Create Admin User")
    print("=" * 50)
    
    email = input("Enter admin email (default: admin@school.com): ") or "admin@school.com"
    password = input("Enter admin password (min 6 chars): ")
    
    if len(password) < 6:
        print("❌ Error: Password must be at least 6 characters")
        sys.exit(1)
    
    full_name = input("Enter full name (default: Admin User): ") or "Admin User"
    phone = input("Enter phone (optional): ") or None
    address = input("Enter address (optional): ") or None
    
    print("\n⏳ Creating admin user...")
    
    try:
        # Create auth user
        auth_response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "full_name": full_name,
                "role": "admin"
            }
        })
        
        if not auth_response.user:
            print("❌ Error: Failed to create auth user")
            sys.exit(1)
        
        user_id = auth_response.user.id
        print(f"✅ Auth user created: {user_id}")
        
        # Create profile
        profile_data = {
            "user_id": user_id,
            "full_name": full_name,
            "phone": phone,
            "address": address,
        }
        
        profile_response = supabase.table("profiles").insert(profile_data).execute()
        
        if profile_response.data:
            print(f"✅ Profile created")
        else:
            print("⚠️ Warning: Profile creation may have failed")
        
        print("\n" + "=" * 50)
        print("✅ Admin user created successfully!")
        print("=" * 50)
        print(f"\nLogin Credentials:")
        print(f"  Email: {email}")
        print(f"  Password: {password}")
        print(f"\nYou can now login at: http://localhost:3000/login")
        print()
        
    except Exception as e:
        print(f"\n❌ Error creating admin user: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    create_admin_user()

