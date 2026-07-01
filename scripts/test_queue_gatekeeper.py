import asyncio
import sys
import os
from datetime import datetime, timezone  # <-- Added timezone import
from sqlalchemy import select, delete

# 1. Setup Path to find 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.job_queue import JobQueue, JobStatus, JobPriority

# ==============================================================================
# TEST CONFIGURATION (Define your test variables at the very top)
# ==============================================================================
TEST_CHAT_ID = 4  # Change this to any valid user ID in your DB


async def main():
    print(f"--- Starting Concurrency Gatekeeper Test for ID: {TEST_CHAT_ID} ---")
    
    # Clean up and setup the test environment
    async with AsyncSessionLocal() as session:
        # Wipe out any existing jobs for this user to ensure clean results
        stmt_delete = delete(JobQueue).where(JobQueue.user_id == TEST_CHAT_ID)
        await session.execute(stmt_delete)
        await session.commit()
        print("🧹 Cleaned up existing queue jobs for this user.")

        # Step 1: Create Job 1 directly in 'processing' status.
        # This simulates a running task (e.g., executing on another worker).
        job_1 = JobQueue(
            user_id=TEST_CHAT_ID,
            priority=JobPriority.MEDIUM.value,
            status=JobStatus.PROCESSING,
            source="eurobot",
            attempts=1
        )
        session.add(job_1)
        await session.flush()
        job_1_id = job_1.id

        # Step 2: Create Job 2 in 'pending' status.
        # This simulates a new update arriving while Job 1 is still processing.
        job_2 = JobQueue(
            user_id=TEST_CHAT_ID,
            priority=JobPriority.HIGH.value,  # VIP High priority
            status=JobStatus.PENDING,
            source="eurobot"
        )
        session.add(job_2)
        await session.commit()
        job_2_id = job_2.id

        print(f"✅ Job 1 created as active: ID {job_1_id} [PROCESSING]")
        print(f"✅ Job 2 created in queue:  ID {job_2_id} [PENDING]")

    # Phase 2: Verify the Concurrency Block (Polling for 10 seconds)
    print("\n⏳ Phase 1: Verifying that Job 2 is being IGNORED by the worker...")
    print("-------------------------------------------------------------------------")
    
    for i in range(10):
        await asyncio.sleep(1)
        async with AsyncSessionLocal() as session:
            # Query status of both jobs
            stmt_job1 = select(JobQueue).where(JobQueue.id == job_1_id).execution_options(populate_existing=True)
            stmt_job2 = select(JobQueue).where(JobQueue.id == job_2_id).execution_options(populate_existing=True)
            
            j1 = (await session.execute(stmt_job1)).scalars().first()
            j2 = (await session.execute(stmt_job2)).scalars().first()
            
            time_str = datetime.now().strftime('%H:%M:%S')
            print(
                f"[{time_str}] "
                f"Job 1 (Active): {j1.status.upper()} | "
                f"Job 2 (Waiting): {j2.status.upper()}"
            )
            
            # If Job 2 is picked up while Job 1 is processing, the test has failed.
            if j2.status == JobStatus.PROCESSING:
                print("-------------------------------------------------------------------------")
                print("❌ TEST FAILED: Worker picked up Job 2 while Job 1 was still processing!")
                return

    # Phase 3: Release the Lock (Simulate Job 1 completing)
    print("\n🔓 Phase 2: Simulating Job 1 completing. Releasing the sequential lock...")
    print("-------------------------------------------------------------------------")
    async with AsyncSessionLocal() as session:
        j1 = await session.get(JobQueue, job_1_id)
        if j1:
            j1.status = JobStatus.COMPLETED
            j1.completed_at = datetime.now(timezone.utc)
            await session.commit()
            print("✅ Job 1 marked as COMPLETED in the database.")

    # Phase 4: Verify the Pickup (Polling for 20 seconds)
    print("\n⏳ Phase 3: Verifying that the worker now safely picks up Job 2...")
    print("-------------------------------------------------------------------------")
    
    for i in range(20):
        await asyncio.sleep(1)
        async with AsyncSessionLocal() as session:
            stmt_job2 = select(JobQueue).where(JobQueue.id == job_2_id).execution_options(populate_existing=True)
            j2 = (await session.execute(stmt_job2)).scalars().first()
            
            time_str = datetime.now().strftime('%H:%M:%S')
            print(f"[{time_str}] Job 2 Status: {j2.status.upper()}")
            
            if j2.status == JobStatus.COMPLETED:
                print("-------------------------------------------------------------------------")
                print("✅ TEST PASSED: Job 2 waited safely, was picked up, and completed sequentially!")
                break
    else:
        print("-------------------------------------------------------------------------")
        print("❌ TEST FAILED: Job 2 was never picked up by the worker.")

if __name__ == "__main__":
    asyncio.run(main())