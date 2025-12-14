import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.admin import Admin
from app.core.security import get_password_hash

async def create_superuser():
    print("\n--- 🛡️  Create Superuser 🛡️  ---")
    
    # 1. Get Inputs
    username = input("Enter username: ").strip()
    if not username:
        print("❌ Error: Username cannot be empty.")
        return

    password = input("Enter password: ").strip()
    if len(password) < 4:
        print("❌ Error: Password is too short.")
        return

    # 2. Database Operation
    async with AsyncSessionLocal() as session:
        # Check for existing user
        query = select(Admin).where(Admin.username == username)
        result = await session.execute(query)
        existing_admin = result.scalars().first()

        if existing_admin:
            print(f"❌ Error: Admin '{username}' already exists.")
            return

        # Create new Superuser
        new_admin = Admin(
            username=username,
            password_hash=get_password_hash(password),
            is_active=True,
            is_superadmin=True,   # <--- Grants permission to manage other admins
            has_all_rights=True   # <--- Grants permission to manage everything else
        )
        
        session.add(new_admin)
        await session.commit()
        
        print(f"✅ Success! Superuser '{username}' created.")

if __name__ == "__main__":
    try:
        asyncio.run(create_superuser())
    except KeyboardInterrupt:
        print("\nCancelled.")