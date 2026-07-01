import asyncio
import sys
import os
from sqlalchemy import select, delete, case  # <-- Added case import

# 1. Setup Path to find 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.job_queue import JobQueue, JobStatus, JobPriority

# ==============================================================================
# TEST CONFIGURATION (Define your test variables at the very top)
# ==============================================================================
TEST_CHAT_ID = 4  # Change this to any valid user ID in your DB


async def main():
    print(f"--- Starting Database Job Merging Test for ID: {TEST_CHAT_ID} ---")
    
    # Setup clean testing state
    async with AsyncSessionLocal() as session:
        # Wipe out any existing jobs for this user first
        stmt_delete = delete(JobQueue).where(JobQueue.user_id == TEST_CHAT_ID)
        await session.execute(stmt_delete)
        await session.commit()
        print("🧹 Cleaned up existing queue jobs for this user.")

    # 1. Enqueue Job A: Eurobot (Medium Priority)
    print("\n1. Simulating Eurobot Upsert (Inserting MEDIUM priority 'eurobot' job)...")
    async with AsyncSessionLocal() as session:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy import func
        
        stmt_a = (
            pg_insert(JobQueue)
            .values(
                user_id=TEST_CHAT_ID,
                priority=JobPriority.MEDIUM.value,
                status=JobStatus.PENDING,
                source="eurobot"
            )
            .on_conflict_do_update(
                index_elements=[JobQueue.user_id],
                # Fixed: Aligned to match the database's new pending-only index exactly
                index_where=(JobQueue.status == JobStatus.PENDING),
                set_={
                    "priority": func.greatest(JobQueue.priority, JobPriority.MEDIUM.value),
                    "updated_at": func.now()
                }
            )
        )
        await session.execute(stmt_a)
        await session.commit()
        print("✅ Eurobot job inserted successfully.")

    # 2. Enqueue Job B: Hilfenbot (High Priority / VIP)
    print("\n2. Simulating Hilfenbot VIP Request (Conflict on index; upgrading to HIGH and source='both')...")
    async with AsyncSessionLocal() as session:
        stmt_b = (
            pg_insert(JobQueue)
            .values(
                user_id=TEST_CHAT_ID,
                priority=JobPriority.HIGH.value,
                status=JobStatus.PENDING,
                source="hilfenbot"
            )
            .on_conflict_do_update(
                index_elements=[JobQueue.user_id],
                index_where=(JobQueue.status == JobStatus.PENDING),  # Aligned with database
                set_={
                    "priority": func.greatest(JobQueue.priority, JobPriority.HIGH.value),
                    # Merge source dynamically using PostgreSQL CASE statement
                    "source": case(
                        (JobQueue.source != "hilfenbot", "both"),
                        else_=JobQueue.source
                    ),
                    "updated_at": func.now()
                }
            )
        )
        await session.execute(stmt_b)
        await session.commit()
        print("✅ Hilfenbot conflict check completed.")

    # 3. Verify the final merged row in the Database
    print("\n3. Querying the database to check the merged job state...")
    print("-------------------------------------------------------------------------")
    async with AsyncSessionLocal() as session:
        stmt_verify = select(JobQueue).where(JobQueue.user_id == TEST_CHAT_ID)
        jobs = (await session.execute(stmt_verify)).scalars().all()
        
        print(f"Total active jobs in database for User {TEST_CHAT_ID}: {len(jobs)}")
        
        for job in jobs:
            print(
                f"Job ID: {job.id} | "
                f"Status: {job.status.upper()} | "
                f"Source: {job.source.upper()} | "
                f"Priority: {job.priority} (Expected: 3/HIGH)"
            )
            
        print("-------------------------------------------------------------------------")
        
        if len(jobs) == 1:
            merged_job = jobs[0]
            if merged_job.source == "both" and merged_job.priority == 3:
                print("✅ TEST PASSED: Database successfully merged the jobs into a single 'BOTH' source at 'HIGH' priority!")
            else:
                print("❌ TEST FAILED: Row merged, but priority or source attributes are incorrect.")
        else:
            print("❌ TEST FAILED: Database failed to merge tasks; duplicate rows exist.")

if __name__ == "__main__":
    asyncio.run(main())