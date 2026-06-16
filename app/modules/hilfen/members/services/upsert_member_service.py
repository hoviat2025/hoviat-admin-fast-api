import logging
import traceback
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.core.exceptions import ServiceError
from app.modules.hilfen.members.schemas.request import HilfenInsertMemberRequest

logger = logging.getLogger(__name__)

class UpsertHilfenMemberService:
    # Key profile fields protected from being wiped out by empty/null values
    PROTECTED_FIELDS = {
        "phone_number",
        "first_name",
        "last_name",
        "country",
        "username",
        "nickname"
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserBaseRepository(db)

    def _clean_db_error(self, error_obj: Exception) -> str:
        """Helper to extract user-friendly messages from DB errors."""
        raw_msg = str(error_obj.orig) if hasattr(error_obj, 'orig') else str(error_obj)
        
        if "DETAIL:" in raw_msg:
            return raw_msg.split("DETAIL:", 1)[1].strip()
        
        if raw_msg.strip().startswith("<class"):
            parts = raw_msg.split(":", 1)
            if len(parts) > 1:
                return parts[1].strip()
                
        return raw_msg

    def _merge_fields(self, user_obj: User, update_data: dict) -> None:
        """
        Updates database object attributes in place. Restricts overwrite permissions 
        on critical profile columns if incoming properties are blank or empty strings.
        Excludes primary key mutation.
        """
        for key, incoming_value in update_data.items():
            # Skip primary key modification on updates
            if key == "counter":
                continue

            if not hasattr(user_obj, key):
                continue

            if key in self.PROTECTED_FIELDS:
                if incoming_value not in (None, ""):
                    setattr(user_obj, key, incoming_value)
            else:
                setattr(user_obj, key, incoming_value)

    async def execute(self, payload: HilfenInsertMemberRequest) -> User:
        """
        Executes user upsert. Uses explicit prints to bypass logger configurations
        and dumps raw database traceback details directly into the HTTP error payload
        for easier debugging.
        """
        db_data = payload.to_db_dict()
        user_id = db_data["user_id"]

        print(f"\n[DEBUG] Starting Hilfen upsert execution for user_id: {user_id}", flush=True)

        if user_id is None:
            raise ServiceError(
                code="INVALID_INPUT",
                message="User ID parameter is missing or invalid.",
                status_code=422
            )

        # 1. Attempt Check-and-Update Route
        user = await self.repo.get_by_id(user_id)
        if user:
            print(f"[DEBUG] User {user_id} found in DB. Executing safe merge...", flush=True)
            self._merge_fields(user, db_data)
            await self.db.commit()
            await self.db.refresh(user)
            print(f"[DEBUG] User {user_id} successfully merged and committed.", flush=True)
            return user

        # 2. Attempt Create Route (Assumed new user)
        try:
            print(f"[DEBUG] User {user_id} NOT found in DB. Attempting INSERT...", flush=True)
            db_data["chat_not_found"] = False
            user = await self.repo.create(db_data)
            await self.db.commit()
            await self.db.refresh(user)
            print(f"[DEBUG] User {user_id} successfully inserted and committed.", flush=True)
            return user

        except IntegrityError as e:
            # 3. Catch-and-Retry Concurrency Path
            await self.db.rollback()
            
            # Print traceback directly to stdout so you see it in the terminal
            print("\n" + "="*60, flush=True)
            print(f"[DEBUG] !!! IntegrityError detected for user_id {user_id} !!!", flush=True)
            print(f"Cleaned DB Error Message: {self._clean_db_error(e)}", flush=True)
            traceback.print_exc()
            print("="*60 + "\n", flush=True)

            # Re-fetch the record to see if it was a user_id concurrency conflict
            user = await self.repo.get_by_id(user_id)
            if user:
                print(f"[DEBUG] Concurrency conflict confirmed. User {user_id} now exists in DB. Merging...", flush=True)
                self._merge_fields(user, db_data)
                await self.db.commit()
                await self.db.refresh(user)
                return user
            else:
                # It was NOT a user_id conflict (e.g. sequence pkey error or NOT NULL constraint)
                clean_message = self._clean_db_error(e)
                db_trace = str(e.orig) if hasattr(e, "orig") else str(e)
                
                print(f"[DEBUG] Non-conflict error. Raising detailed ServiceError: {clean_message}", flush=True)
                
                # We place the raw DB trace right into the message so it shows up in your JSON response
                raise ServiceError(
                    code="CONFLICT_UNRESOLVED",
                    message=f"Database integrity violation: {clean_message} | Trace: {db_trace}",
                    status_code=409
                )
        except Exception as e:
            await self.db.rollback()
            print(f"[DEBUG] Unexpected exception occurred: {e}", flush=True)
            traceback.print_exc()
            raise e