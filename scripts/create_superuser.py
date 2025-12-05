import asyncio
import sys
import os

# --- PATH HACK: Add the project root to Python path ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.admin import Admin
from app.core.security import get_password_hash

async def create_admin():
    print("--- Create Superuser ---")
    username = input("Enter username: ")
    password = input("Enter password: ")

    async with AsyncSessionLocal() as session:
        # 1. Check if user exists
        # (Note: We are lazy here and don't import the Repo, just raw SQL for the script)
        from sqlalchemy import select
        result = await session.execute(select(Admin).where(Admin.username == username))
        if result.scalars().first():
            print("Error: That username already exists.")
            return

        # 2. Create the Admin
        new_admin = Admin(
            username=username,
            password_hash=get_password_hash(password) # <--- Hashing happens here
        )
        
        session.add(new_admin)
        await session.commit()
        print(f"✅ Success! Admin '{username}' created.")

if __name__ == "__main__":
    asyncio.run(create_admin())