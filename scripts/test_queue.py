import asyncio
import sys
import os
from datetime import datetime

# 1. Setup Path to find 'app' (matching your exact template)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.job_queue import JobQueue, JobStatus, JobPriority

# Using your verified working chat ID from your other test script
TEST_CHAT_ID = 4

async def main():
    print(f"--- Starting Queue Integration Test for ID: {TEST_CHAT_ID} ---")
    
    # 2. Setup database session
    async with AsyncSessionLocal() as session:
        
        # 3. Clean up any active, stale test jobs for this ID
        stmt = select(JobQueue).where(
            JobQueue.user_id == TEST_CHAT_ID,
            JobQueue.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])
        )
        existing = (await session.execute(stmt)).scalars().first()
        if existing:
            print(f"⚠️ An active job (ID: {existing.id}) already exists. Removing it to start fresh...")
            await session.delete(existing)
            await session.commit()

        # 4. Enqueue a new VIP High-Priority Job
        new_job = JobQueue(
            user_id=TEST_CHAT_ID,
            priority=JobPriority.HIGH.value,
            status=JobStatus.PENDING,
            source="eurobot"
        )
        session.add(new_job)
        await session.commit()
        job_id = new_job.id
        print(f"✅ Job {job_id} successfully created as 'PENDING'.")

    print("\n🔍 Monitoring job state changes... (Watch your FastAPI server terminal logs!)")
    print("-------------------------------------------------------------------------")

    # 5. Monitor Job Status Lifecycle
    for i in range(60):
        await asyncio.sleep(1)
        async with AsyncSessionLocal() as session:
            # Bypass SQLAlchemy cache to fetch fresh database state on each check
            stmt_poll = select(JobQueue).where(JobQueue.id == job_id).execution_options(populate_existing=True)
            job = (await session.execute(stmt_poll)).scalars().first()
            
            if not job:
                print("❌ Job was deleted unexpectedly.")
                return
                
            time_str = datetime.now().strftime('%H:%M:%S')
            # Fixed: Removed '.value' because job.status is now a standard string
            print(
                f"[{time_str}] "
                f"Status: {job.status.upper()} | "
                f"Attempts: {job.attempts}/{job.max_attempts} | "
                f"Error: {job.error_message or 'None'}"
            )
            
            # If the job has reached a terminal state, finish the test
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                print("-------------------------------------------------------------------------")
                print(f"🎉 Test Finished. Job ended in status: {job.status.upper()}")
                break

if __name__ == "__main__":
    if TEST_CHAT_ID == 4 and False:  # Change False to True if you want a safety check
        print("⚠️ Please verify TEST_CHAT_ID matches an existing database user.")
    else:
        asyncio.run(main())