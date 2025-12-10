# update or insert user in telegram channels
get user_id
user_info = get the row from db where user_id == user_id
if you didnt find any row with that user_id raise 404

if the telegram_message_id of the row is not empty :
  call #update user in telegram channel (pass user_info to it)
else :
  return ok 


#update user in telegram channel (user_info)
  get user_info
  result = call #main_channel_formatter (pass the user_info to it)
  formatted_text = result.text
  result = call #edit the caption of the message in main channel (pass the formatted text and user_info["telegram_message_id"])
  if result == success :
    call #update channel_updated_at (pass user_info[user_id])
  else :
    return 500 error

#main_channel_formatter (user_info )
 user httpx to do the following request :
 post https://snowy-rain-3f69.safaee1361.workers.dev
 body : user_info as json
 if not succesful raise 500
 else return the response

#edit the caption of the message in main channel (formatted text and user_info["telegram_message_id"])
use the custom telegram client we have defined in main and pass it the following parameters :
  