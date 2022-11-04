import logging

from wterror import Error
from telebot import TeleBot

# -- сообщения о ошибках, которые ватсап-бот будет отправлять в чат --
wa_error_notifications = {"content": "This type of content cannot be forwarded to our operators", "sending": "I can't send a message, please contact our operators in another way"}

class TelegramBot(TeleBot):
    def __init__(self, TG_API_TOKEN):
        super().__init__(TG_API_TOKEN)
        self.telegram_content_types = ['text', 'document', 'audio', 'photo','video', 'video_note','voice', 'location']

    def get_content_type(self, message):
        for type in self.telegram_content_types:
            if type in message:
                return type
        return None

    def send_message(self, chat_id, message, postscipt, mode='HTML', reply_id = None):
        logging.info(f"Message to telegram: {message}")
        return super().send_message(chat_id, text=message+postscipt, parse_mode=mode, disable_web_page_preview=True, reply_to_message_id = reply_id)

    def send_document(self, chat_id, document_id, document_file_name, postscipt, mode='HTML', reply_id = None):
        return super().send_document(chat_id, document=document_id, caption=postscipt, visible_file_name=document_file_name,  parse_mode=mode, reply_to_message_id = reply_id)

    def send_photo(self, chat_id, photo_id, message, postscipt, mode='HTML', reply_id = None):
        return super().send_photo(chat_id, photo=photo_id, caption=message+postscipt, parse_mode=mode, reply_to_message_id = reply_id)

    def send_audio(self, chat_id, audio_id, postscipt, mode='HTML', reply_id = None):
        return super().send_audio(chat_id, audio=audio_id, caption=postscipt, parse_mode=mode, reply_to_message_id = reply_id)

    def send_video(self, chat_id, video_id, message, postscipt, mode='HTML', reply_id = None):
        return super().send_video(chat_id, video=video_id, caption=message+postscipt, parse_mode=mode, reply_to_message_id = reply_id)

    def send_location(self, chat_id, location_latitude, location_longitude, location_title, location_address, postscipt, mode='HTML', reply_id = None):
        location_message = super().send_venue(chat_id, latitude=location_latitude, longitude=location_longitude, title=location_title, address=location_address, reply_to_message_id = reply_id)
        if(reply_id):
            return location_message
        if(location_message):
            return super().send_message(chat_id, text=postscipt, parse_mode=mode,  disable_web_page_preview=True, reply_to_message_id=location_message.message_id)
        return Error(wa_error_notifications['content'])