# update or insert user in telegram channels
get user_id
user_info = get the row from db where user_id == user_id
if you didnt find any row with that user_id raise 404

if the telegram_message_id of the row is not empty :
  call #update user in telegram channel (pass user_info to it)
else :
  call #insert user in telegram channel (pass user_info to it)

#insert user in telegram channel
using the send_request of euro_bot client do the get_chat in telegram (you get and use the euro_bot the way you got the sender_bot : from app.shared.bot_instances import euro_bot, essentially you pass it the telegram endpoint and the body that is supposed to be sent)
image_path = null
if the get_chat failed or result.photo.big_file_id didnt exist:
  Picture_file = DEFAULT_PICTURE (get it from config variables with same name)
else meaning we got profile from telegram:
    result = call #upload user profile (pass the user_id)
    if failed similar to the previous line set to default Picture_file
    else if result.image_url and result.image_path not empty :
      Picture_file = result.image_url
      image_path = result.image_path
chat_not_found = true if get_chat failed , false if it was succesful (it is successful if telegram succesfuly gives us the chat info)
result = call #main_channel_formatter (pass the user_info to it) ##this is the same thing used in the update
formatted_text = result.text
call #send photo with a caption in main channel (pass the formatted text and user_info["telegram_message_id"] and Picture_file
result = call #confirm_group_message (pass it user_id)
group_message_id = result.group_message_id
## now from this point on , if things don't succeed we must make telegram_message_id and group_message_id null and other things null in the database and I have written that pay attention
result = call #set public channel posts (pass user_id) ##this function should not internally raise errors but rather if it fails we catch it here so that we can make the things null as I said
if result.public_group_message_id is not an existing number (meaning the previous function failed one way or another):
  call #update channel_posts_to_null (pass it user_id and chat_not_found)
  raise 500
else (meaning the function was succesfulc):
  result = call #update profile path and channel_updated_at and chat_not_found (pass it user_id , image_path and chat_not_found)
  return result




#upload user profile (pass the user_id)
use the app\modules\eurobot\members\services\profile_service.py
here's an explanation of using it :
***

**Function:** `save_user_profile_to_cloud(chat_id)`

**1. Import:**
```python
from app.modules.eurobot.members.services.profile_service import save_user_profile_to_cloud
```

**2. Usage:**
This function is **fail-safe**. You do not need a `try/except` block when calling it.
```python
result = await save_user_profile_to_cloud(chat_id)
```

**3. Return Value:**
*   **Success:** Returns a dictionary.
    ```python
    {
      "image_url": "https://full-url.com/123.jpg",
      "image_path": "123.jpg"
    }
    ```
*   **Failure:** Returns `False` (boolean).



#send photo with a caption in main channel (pass the formatted text and user_info["telegram_message_id"] and Picture_file
use the sender_bot
here's an example of a function doing a similar but not exactly this :
async def _edit_caption_in_main_channel(self, message_id: int, formatted_text: str) -> bool:
        """
        Uses the shared sender_bot to edit the message.
        """
        print(formatted_text)
        payload = {
            "chat_id": settings.MAIN_CHANNEL_ID,
            "message_id": message_id,
            "caption": formatted_text
        }

        # Multi-Tenant Bot Usage
        result = await sender_bot.send_request("editMessageCaption", payload)

        if not result.success:
            # LOG the specific error from Telegram for debugging
            logger.error(f"Telegram Edit Failed for Msg {message_id}: {result.error_message}")
            
            # Raise generic error to client
            raise ServiceError(
                code="TELEGRAM_EDIT_FAILED",
                message="Failed to update Telegram Channel",
                status_code=502
            )
        
        return True
now here we would give it this enpoitn :
sendPhoto
and this body :
chat_id = main channel
photo = the Picture_file that is passed to it
caption = the formatted text passed to it



#confirm_group_message (pass it user_id)
##essentially confirming if group_message_id has been set in database , checking every half a second and wait maximum of 20 seconds 
user_info = row where user_id == user_id
if not found raise 404
group_message_id = user_info.group_message_id
while group_message_id is not a exisitng intenger (type convert if necessary):
  wait 0.5 seconds
  user_info = row where user_id == user_id (get the user again so you check again)
  if we have waited more than 20 seconds raise 500
now that group_message_id is cool return the fresh user_info




#set public channel posts (pass user_id) 
user_info = get row where user_id == user_id
if not found return error 
if telegram_message_id is not a existing integer return error 
result = call #send user post in public_channel (pass it telegram_message_id )
if failed return error meaning if successfully we havent sent the post we wont proceed to try to confirm it
result= call #confirm public group post 
if failed return error 
else return result

#send user post in public_channel (pass it telegram_message_id )
use sender bot to sendMessage
this should be the the body :
{
           "chat_id": PUBLIC_CHANNEL_ID,
           "text": "❗️مشتری جدید\nستاره ها : « ⭐️⭐️⭐️⭐️⭐️ »\nتعداد کنسلی ❌❌❌❌❌",
           "reply_parameters": {
               "message_id": telegram_message_id,
               "chat_id": MAIN_CHANNEL_ID
           }
         }
the PUBLIC_CHANNEL_ID and so on are varaibles in config with same names


#confirm public group post 
##essentially confirming if public_group_message_id has been set in database , checking every half a second and wait maximum of 20 seconds 
user_info = row where user_id == user_id
if not found raise 404
public_group_message_id = user_info.public_group_message_id
while public_group_message_id is not a exisitng intenger (type convert if necessary):
  wait 0.5 seconds
  user_info = row where user_id == user_id (get the user again so you check again)
  if we have waited more than 20 seconds raise 500
now that public_group_message_id is cool return the fresh user_info



#update channel_posts_to_null (pass it user_id and chat_not_found)
##simply use the update repo to update the user info in db 
here's how the update should be :
set the followings to null :
telegram_message_id
group_message_id
public_message_id
public_group_message_id
set chat_not_found true or false based on chat_not_found
and ocrourse the column to match on is user_id  == user_id 
if failed raise 500


#update profile path and channel_updated_at and chat_not_found (pass it user_id , image_path and chat_not_found)
##simply use the update repo to update the user info in db 
here's how the update should be :
column to match on user_id
set channel_updated_at to equivalent of {{new Date().toISOString()}} (just like it is done in the #update user in telegram channel )
set chat_not_found to chat_not_found it should be boolean
set profile_path to image_path which should be null if no profile is found and uploaded






#update user in telegram channel (user_info)
  get user_info
  result = call #main_channel_formatter (pass the user_info to it)
  formatted_text = result.text
  result = call #edit the caption of the message in main channel (pass the formatted text and user_info["telegram_message_id"])
  if result == success :
    result = call #update channel_updated_at (pass user_info[user_id])
    if success return the result
  else :
    return 500 error

#main_channel_formatter (user_info )
 user httpx to do the following request :
 post https://snowy-rain-3f69.safaee1361.workers.dev
 body : user_info as json
 if not succesful raise 500
 else return the response

#edit the caption of the message in main channel (formatted text and user_info["telegram_message_id"])
use the sender_bot.send_request(editMessageCaption , { chat_id : -1003307384504, message_id: user_info..telegram_message_id , caption : formatted_text} ) #sender bot is an existing thing here's how to summon it :
from app.shared.bot_instances import sender_bot
if not succesful raise 500 error otherwise return the result 
  here's how you know it succedd : {{ $result.body.ok }} == true


#update channel_updated_at ( user_info[user_id])
the following is roughly how you can call the update repo
from app.shared.repositories.user_base import UserBaseRepository
UserBaseRepository(db)
update_data = payload.model_dump(exclude_unset=True, exclude={"user_id"})

        if not update_data:
            raise ServiceError(code="INVALID_INPUT", message="No fields provided for update", status_code=422)

        # 2. Data Access: Call the Repo (Service doesn't know SQL)
        updated_user = await self.repo.update(
            user_id=payload.user_id, 
            update_data=update_data
        )
now in this instance we set the user_id the thing that is being passed to us and the only column we are updating is channel_updated_at that will be set to {{new Date().toISOString()}}
if successful it will return the updated row
if successful it returns success otherwise raise 500