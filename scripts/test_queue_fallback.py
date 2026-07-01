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
TEST_CHAT_ID = 4  # We use User 4 because we know they fail on euro_bot


async def main():
    print(f"--- Starting Dual-Bot getChat Fallback Test for ID: {TEST_CHAT_ID} ---")
    
    # Setup clean testing state
    async with AsyncSessionLocal() as session:
        # Wipe out any existing jobs for this user first
        stmt_delete = delete(JobQueue).where(JobQueue.user_id == TEST_CHAT_ID)
        await session.execute(stmt_delete)
        await session.commit()
        print("🧹 Cleaned up existing queue jobs for this user.")

        # Enqueue a new HIGH priority task with source = "both"
        new_job = JobQueue(
            user_id=TEST_CHAT_ID,
            priority=JobPriority.HIGH.value,
            status=JobStatus.PENDING,
            source="both"  # <-- VIP task targeting both bots
        )
        session.add(new_job)
        await session.commit()
        job_id = new_job.id
        print(f"✅ Job {job_id} successfully created as 'PENDING' with source='BOTH'.")

    print("\n🔍 Monitoring fallback execution... (Watch your FastAPI server terminal logs!)")
    print("-------------------------------------------------------------------------")
    print("⚠️ EXPECTED BEHAVIOR:")
    print(" - The worker should start job with source='both'.")
    print(" - It will fail getChat on euro_bot, print a warning, and fallback to hilfen_bot.")
    print("-------------------------------------------------------------------------")

    final_status = None

    # Poll the database for up to 60 seconds (checking every 2 seconds)
    for i in range(30):
        await asyncio.sleep(2)
        async with AsyncSessionLocal() as session:
            stmt_poll = select(JobQueue).where(JobQueue.id == job_id).execution_options(populate_existing=True)
            job = (await session.execute(stmt_poll)).scalars().first()
            
            if not job:
                print("❌ Job was deleted unexpectedly.")
                return
                
            time_str = datetime.now().strftime('%H:%M:%S')
            print(
                f"[{time_str}] "
                f"Status: {job.status.upper()} | "
                f"Attempts: {job.attempts}/{job.max_attempts} | "
                f"Last Error: {job.error_message or 'None'}"
            )
            
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                final_status = job.status
                print("-------------------------------------------------------------------------")
                print(f"🎉 Test Finished. Job ended in status: {job.status.upper()}")
                break

    # Cleanup Phase: Delete the test database row
    print("\n🧹 Phase 4: Cleaning up database...")
    async with AsyncSessionLocal() as session:
        stmt_cleanup = delete(JobQueue).where(JobQueue.user_id == TEST_CHAT_ID)
        await session.execute(stmt_cleanup)
        await session.commit()
        print("✅ Test database rows deleted successfully.")

    if final_status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
        print("❌ TEST FAILED: Job did not complete within the timeout.")

if __name__ == "__main__":
    asyncio.run(main())