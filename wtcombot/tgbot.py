from wterror import WTCombotError
from telebot import TeleBot
from telebot import types

MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024

class TelegramBot(TeleBot):
    def __init__(self, TG_API_TOKEN):
        super().__init__(TG_API_TOKEN)
        self.telegram_content_types = ['text', 'document', 'audio', 'photo','video', 'video_note','voice', 'location']
        # -- сообщения о ошибках, которые ватсап-бот будет отправлять в чат --
        self.error_notifications = {"content": "This type of content cannot be forwarded to our operators", 
                                    "sending": "I can't send a message, please contact our operators in another way"}

    def get_phone_number(self, reply_message_text) -> str:
        last_line = reply_message_text.split("\n")[-1]
        return last_line.split(" ")[-2]

    def get_content_type(self, message) -> str:
        for type in self.telegram_content_types:
            if type in message:
                return type
        return ''

    def get_chat_id(self, message) -> str:
        return message['chat']['id']

    def get_reply_message_from_id(self, reply_message) -> str:
        return reply_message['from']['id']

    def get_reply_message_text(self, reply_message) -> str|None:
        text = reply_message.get('text')
        return text if text else reply_message.get('caption')

    def get_message_id(self, message) -> int:
        return message['message_id']

    def get_file_id(self, message, content_type):
        file_id = message[content_type]['file_id']
        return file_id

    def get_photo_id(self, message) -> str:
        photo_id = message['photo'][-1]['file_id']
        return photo_id

    def get_filename(self, message, content_type) -> str:
        return message[content_type]['file_name'].rsplit(".",1)[0]

    def get_geodata(self, message) -> tuple[float, float]:
        return message['location']['latitude'], message['location']['longitude']

    def get_place(self, location) -> tuple[str, str]:
        return location.get('title', ''), location.get('address', '')

    def send_message(self, chat_id, message, postscript, mode='HTML', reply_id=None) -> types.Message:
        send_message_args = {'chat_id':chat_id, 'parse_mode':mode,'disable_web_page_preview':True, 'reply_to_message_id':reply_id}
        return self.send_multiply_message(super().send_message, message, postscript, is_text=True, **send_message_args)

    def send_document(self, chat_id, document, document_file_name, postscript, mode='HTML', reply_id=None) -> types.Message:
        return super().send_document(chat_id, document=document, caption=postscript, visible_file_name=document_file_name,  
                                     parse_mode=mode, reply_to_message_id=reply_id, allow_sending_without_reply=True)

    def send_photo(self, chat_id, photo, message, postscript, mode='HTML', reply_id=None) -> types.Message:
        send_photo_args = {'chat_id':chat_id, 'photo':photo, 'parse_mode':mode, 'reply_to_message_id':reply_id}
        return self.send_multiply_message(super().send_photo, message, postscript, is_text=False, **send_photo_args)

    def send_audio(self, chat_id, audio, postscript, mode='HTML', reply_id=None) -> types.Message:
        return super().send_audio(chat_id, audio=audio, caption=postscript, parse_mode=mode, reply_to_message_id = reply_id, 
                                  allow_sending_without_reply=True)

    def send_video(self, chat_id, video, message, postscript, mode='HTML', reply_id=None) -> types.Message:
        send_video_args = {'chat_id':chat_id, 'video':video, 'parse_mode':mode, 'reply_to_message_id':reply_id}
        return self.send_multiply_message(super().send_video, message, postscript, is_text=False, **send_video_args)

    def send_location(self, chat_id, latitude, longitude, title, address, postscript, mode='HTML', reply_id=None) -> types.Message:
        location_message = super().send_venue(chat_id, latitude=latitude, longitude=longitude, title=title, address=address, 
                                              reply_to_message_id=reply_id, allow_sending_without_reply=True)
        if(reply_id):
            return location_message
        if(location_message):
            return super().send_message(chat_id, text=postscript, parse_mode=mode, disable_web_page_preview=True, 
                                        reply_to_message_id=location_message.message_id, allow_sending_without_reply=True)
        raise WTCombotError(self.error_notifications['content'])

    def send_multiply_message(self, sending_func, message, postscript, is_text, **kwargs) -> types.Message:
        if(is_text):
            type_text = 'text'
            message_length = MAX_MESSAGE_LENGTH
        else:
            type_text = 'caption'
            message_length = MAX_CAPTION_LENGTH

        text_list = self.smart_split(message, postscript, message_length)
        if(len(text_list)>0):
            kwargs[type_text] = text_list[0]
        kwargs['allow_sending_without_reply'] = True
        sent_message = sending_func(**kwargs)

        text_list = text_list[1:] if len(text_list) > 1 else []
        for text in text_list:
            sent_message = super().send_message(chat_id=kwargs['chat_id'], text=text, parse_mode=kwargs['parse_mode'], 
                                                disable_web_page_preview=True, reply_to_message_id=sent_message.message_id, 
                                                allow_sending_without_reply=True)
        return sent_message

    def smart_split(self, text: str, postscript: str='', chars_per_string: int=MAX_MESSAGE_LENGTH) -> list[str]:

        """
        Данный метод взят из модуля util библиотеки telebot.
        Разбивает одно сообщение на несколько строк с максимальным количеством символов `chars_per_string` в строке.
        Разделяет на '\n', '. ' или ' ' именно в этом приоритете.
        В качестве дополнения метод smart_split подписывает `postscript` каждое сообщение.
        """

        def _text_before_last(substr: str) -> str:
            text_before = substr.join(part.split(substr)[:-1])
            text_before += substr if(substr != '\n') else ' '
            return text_before
       
        chars_per_string -= len(postscript)

        parts = []
        while chars_per_string > 0:
            if len(text) < chars_per_string:
                # if(len(text)>0):
                parts.append(text + postscript)
                return parts

            part = text[:chars_per_string]

            if "\n" in part: part = _text_before_last("\n")
            elif ". " in part: part = _text_before_last(". ")
            elif " " in part: part = _text_before_last(" ")

            if(part not in ['\n', '.', ' ']): 
                parts.append(part + postscript)

            text = text[len(part):]
            
        return parts