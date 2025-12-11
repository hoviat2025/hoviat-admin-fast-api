get /webhook/hoviat/v1/eurobot/quote_reply_info
query : user_id = integer
header : the bot_token dependency same as others


user_info = row where user_id == user_id 
if not exist raise 404

if {{ user_info.updated_at }} is after or equal to {{ $user_info.channel_updated_at }}
 OR 
if {{ $json.telegram_message_id }} is not an existing integer :
    resullt = call #update_user_channel endpoint that we just created , either through service or whatever else (make sure user_id or whatever input it wants is passed to it)
    ##basically here we say : if the db has been updated after the channel has been updated lets update the channel , or actually if there is no post associated with this user in the channel lets call that same function so that it adds it to the channel . 
    
    if failed raise 500 ##failed meaning it didnt add or edit the things as it supposed to have (so it doesnt just mean code breaking entirely it includes all possible errors that mean the channels didnt get updated properly)
    user_info = result.data ##meaning we update the user info , since that service returns the user_info if successful

##now one way or another we have user_info that is fresh and correct
result = call #text formatter (pass it user_info) ##this is the same function that is used in the update_user_channel service
if failed raise 500
data = result.components
return the data ##note we have a specific way of returning in endpoints which has a wrapper 