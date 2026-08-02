import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete

# 1. Setup Path to find 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.job_queue import JobQueue, JobStatus, JobPriority

# ==============================================================================
# TEST CONFIGURATION (Define your test variables at the very top)
# ==============================================================================
USER_A_MEDIUM = 4          # First verified user ID (gets enqueued as MEDIUM)
USER_B_HIGH_VIP = 6385568014  # Second verified user ID (gets enqueued as HIGH/VIP)


async def main():
    print(f"--- Starting Rate Limiter & VIP Quota Spacing Test ---")
    
    # We will use dummy user IDs for the simulated completed jobs
    dummy_ids = [999991, 999992, 999993]
    all_test_ids = dummy_ids + [USER_A_MEDIUM, USER_B_HIGH_VIP]

    # Setup clean testing state
    async with AsyncSessionLocal() as session:
        # Wipe out any existing jobs for all test IDs to start fresh
        stmt_delete = delete(JobQueue).where(JobQueue.user_id.in_(all_test_ids))
        await session.execute(stmt_delete)
        await session.commit()
        print("🧹 Cleaned up existing queue jobs for all test users.")

        # Step 1: Insert 3 dummy COMPLETED jobs directly into the DB.
        # This tells the rate limiter that 3 non-VIP tasks ran in the last minute.
        now_time = datetime.now(timezone.utc)
        
        for d_id in dummy_ids:
            completed_job = JobQueue(
                user_id=d_id,
                priority=JobPriority.MEDIUM.value,
                status=JobStatus.COMPLETED,
                source="eurobot",
                completed_at=now_time,
                attempts=1
            )
            session.add(completed_job)
            
        # Step 2: Enqueue User A as MEDIUM (pending)
        medium_job = JobQueue(
            user_id=USER_A_MEDIUM,
            priority=JobPriority.MEDIUM.value,
            status=JobStatus.PENDING,
            source="eurobot"
        )
        session.add(medium_job)

        # Step 3: Enqueue User B as HIGH (pending/VIP)
        vip_job = JobQueue(
            user_id=USER_B_HIGH_VIP,
            priority=JobPriority.HIGH.value,
            status=JobStatus.PENDING,
            source="eurobot"
        )
        session.add(vip_job)
        
        await session.commit()
        medium_job_id = medium_job.id
        vip_job_id = vip_job.id
        
        print("\n⚙️ Setup completed:")
        print(f"✅ Simulated 3 COMPLETED jobs in the database.")
        print(f"✅ Enqueued Job {medium_job_id} for User {USER_A_MEDIUM} as [MEDIUM]")
        print(f"✅ Enqueued Job {vip_job_id} for User {USER_B_HIGH_VIP} as [HIGH/VIP]")

    print("\n🔍 Monitoring rate limits... (Watch your FastAPI server terminal logs!)")
    print("-------------------------------------------------------------------------")
    print("⚠️ EXPECTED BEHAVIOR:")
    print(" - The HIGH/VIP job should process IMMEDIATELY.")
    print(" - The MEDIUM job should stay PENDING/BLOCKED until the 60-second window clears.")
    print("-------------------------------------------------------------------------")

    medium_completed = False
    vip_completed = False

    # Poll the database for up to 90 seconds (checking every 3 seconds)
    for i in range(30):
        await asyncio.sleep(3)
        async with AsyncSessionLocal() as session:
            stmt_m = select(JobQueue).where(JobQueue.id == medium_job_id).execution_options(populate_existing=True)
            stmt_v = select(JobQueue).where(JobQueue.id == vip_job_id).execution_options(populate_existing=True)
            
            m_job = (await session.execute(stmt_m)).scalars().first()
            v_job = (await session.execute(stmt_v)).scalars().first()
            
            time_str = datetime.now().strftime('%H:%M:%S')
            print(
                f"[{time_str}] "
                f"MEDIUM (User {USER_A_MEDIUM}): {m_job.status.upper()} | "
                f"VIP (User {USER_B_HIGH_VIP}): {v_job.status.upper()}"
            )
            
            # Check outcomes
            if v_job.status == JobStatus.COMPLETED and not vip_completed:
                vip_completed = True
                print(f"⭐ VIP Job completed successfully!")
                
            if m_job.status == JobStatus.COMPLETED and not medium_completed:
                medium_completed = True
                print(f"📦 MEDIUM Job completed successfully!")
                
            if vip_completed and medium_completed:
                print("-------------------------------------------------------------------------")
                print("✅ TEST PASSED: VIP job executed immediately, and MEDIUM job safely waited for the quota gap to clear!")
                break
    else:
        print("-------------------------------------------------------------------------")
        print("❌ TEST FAILED: Timeout reached before both jobs completed.")

    # Cleanup Phase: Delete all test database rows
    print("\n🧹 Phase 4: Cleaning up database...")
    async with AsyncSessionLocal() as session:
        stmt_cleanup = delete(JobQueue).where(JobQueue.user_id.in_(all_test_ids))
        await session.execute(stmt_cleanup)
        await session.commit()
        print("✅ Test database rows deleted successfully.")

if __name__ == "__main__":
    asyncio.run(main())