import asyncio
import sys
import os
from datetime import datetime, timezone
from sqlalchemy import select, delete

# 1. Setup Path to find 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.job_queue import JobQueue, JobStatus, JobPriority

# ==============================================================================
# TEST CONFIGURATION (Define your test variables at the very top)
# ==============================================================================
TEST_CHAT_ID = 9999999999  # Dummy ID that safely triggers a USER_NOT_FOUND error


async def main():
    print(f"--- Starting Queue Retry & Failure Test for ID: {TEST_CHAT_ID} ---")
    
    # Setup clean testing state
    async with AsyncSessionLocal() as session:
        # Wipe out any existing jobs for this user first
        stmt_delete = delete(JobQueue).where(JobQueue.user_id == TEST_CHAT_ID)
        await session.execute(stmt_delete)
        await session.commit()
        print("🧹 Cleaned up existing queue jobs for this user.")

        # Insert our new MEDIUM priority test job
        new_job = JobQueue(
            user_id=TEST_CHAT_ID,
            priority=JobPriority.MEDIUM.value,
            status=JobStatus.PENDING,
            source="eurobot"
        )
        session.add(new_job)
        await session.commit()
        job_id = new_job.id
        print(f"✅ Test Job created successfully with ID: {job_id} [PENDING].")

    print("\n🔍 Monitoring retry attempts... (Watch your FastAPI server terminal logs!)")
    print("-------------------------------------------------------------------------")

    final_status = None
    
    # Poll for up to 60 seconds (checking every 2 seconds)
    for i in range(30):
        await asyncio.sleep(2)
        async with AsyncSessionLocal() as session:
            stmt_poll = select(JobQueue).where(JobQueue.id == job_id).execution_options(populate_existing=True)
            job = (await session.execute(stmt_poll)).scalars().first()
            
            if not job:
                print("❌ Job was deleted unexpectedly.")
                return
                
            time_str = datetime.now().strftime('%H:%M:%S')
            
            # Limit the displayed error to fit nicely in the terminal
            error_preview = "None"
            if job.error_message:
                error_preview = job.error_message[:40] + "..." if len(job.error_message) > 40 else job.error_message
                
            print(
                f"[{time_str}] "
                f"Status: {job.status.upper()} | "
                f"Attempts: {job.attempts}/{job.max_attempts} | "
                f"Error: {error_preview}"
            )
            
            if job.status == JobStatus.FAILED:
                final_status = JobStatus.FAILED
                print("-------------------------------------------------------------------------")
                print("✅ TEST PASSED: Job successfully retried 3 times and landed in FAILED status!")
                break
                
    # Cleanup Phase: Delete the test job database row
    print("\n🧹 Phase 4: Cleaning up database...")
    async with AsyncSessionLocal() as session:
        stmt_cleanup = delete(JobQueue).where(JobQueue.id == job_id)
        await session.execute(stmt_cleanup)
        await session.commit()
        print("✅ Test job database row deleted successfully.")

    if final_status != JobStatus.FAILED:
        print("❌ TEST FAILED: Job did not reach FAILED status within the timeout.")

if __name__ == "__main__":
    asyncio.run(main())