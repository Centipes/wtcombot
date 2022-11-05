import logging
from re import fullmatch
from os import getenv, strerror
from errno import ENOENT
from dotenv import load_dotenv

from wterror import Error
from tgbot import TelegramBot
from wabot import WhatsAppBot


# -- декоратор-обработчик исключений для телеграма --
def tg_check_errors(tg_sender):
    def wrapper(self, message, number, content_type):
        try:
            return tg_sender(self, message, number, content_type)
        except Exception as err:
            logging.error(f"method: tg_check_errors :{err}")
            logging.exception("message")
            return Error(self.whatsapp_bot.error_notifications["sending"])
    return wrapper

# -- декоратор-обработчик исключений для ватсапа --
def wa_check_errors(wa_sender):
    def wrapper(self, content_type, data, postscipt, message_id):
        try:
            return wa_sender(self, content_type, data, postscipt, message_id)
        except Exception as err:
            logging.error(f"method: wa_check_errors : {err}")
            logging.exception("message")
            return Error(self.telegram_bot.error_notifications["sending"])
    return wrapper


class TGWACOM():
    def __init__(self, filename):

        self.__ENV_FILE = filename
        if(not load_dotenv(self.__ENV_FILE)):
            raise FileNotFoundError(ENOENT, strerror(ENOENT), self.__ENV_FILE)
        
        self.__WA_NUMBER_ID = getenv('WT_COMBOT_WA_NUMBER_ID')
        self.__WA_ACCESS_TOKEN = getenv('WT_COMBOT_WA_ACCESS_TOKEN')
        self.__WA_VERIFY_TOKEN = getenv('WT_COMBOT_WA_VERIFY_TOKEN')

        self.__TG_CHAT_ID = getenv('WT_COMBOT_TG_CHAT_ID')
        self.__TG_BOT_ID = getenv('WT_COMBOT_TG_BOT_ID')
        self.__TG_API_TOKEN = getenv('WT_COMBOT_TG_API_TOKEN')

        print('WA_NUMBER_ID = ', self.__WA_NUMBER_ID)
        print('WA_ACCESS_TOKEN = ', self.__WA_ACCESS_TOKEN)
        print('WA_VERIFY_TOKEN = ', self.__WA_VERIFY_TOKEN)
        print('TG_CHAT_ID = ', self.__TG_CHAT_ID)
        print('TG_BOT_ID = ', self.__TG_BOT_ID)
        print('TG_API_TOKEN = ', self.__TG_API_TOKEN)

    def setup(self):
        self.whatsapp_bot = WhatsAppBot(self.__WA_ACCESS_TOKEN, self.__WA_NUMBER_ID) # self.__WA_ACCESS_TOKEN, self.__WA_NUMBER_ID
        self.telegram_bot = TelegramBot(self.__TG_API_TOKEN) 

    def check_env_variables(self) -> bool:

        # check_env_variables проверяет переменные окружения

        def digit(n):
            try:
                return int(n)
            except ValueError:
                return  None
            except TypeError:
                return None

        self.__TG_CHAT_ID = digit(self.__TG_CHAT_ID) 
        self.__TG_BOT_ID = digit(self.__TG_BOT_ID)

        return self.__WA_NUMBER_ID and self.__WA_ACCESS_TOKEN and self.__WA_VERIFY_TOKEN and self.__TG_CHAT_ID and self.__TG_BOT_ID and self.__TG_API_TOKEN

    def wa_point(self, data):

        # wa_point вызывается из app request (wa_webhook)

        logging.info("Received webhook data: %s", data)
        changed_field = self.whatsapp_bot.changed_field(data)

        if changed_field == "messages":
            phone_number = self.whatsapp_bot.get_mobile(data)

            if phone_number:
                modified_phone_number = self.__wa_modify_rus_number__(phone_number)
                name = self.whatsapp_bot.get_name(data)
                content_type = self.whatsapp_bot.get_message_type(data)

                logging.info(f"New Message; sender:{modified_phone_number} name:{name} type:{content_type}")
                postscipt = self.__tg_generate_user_info__(phone_number, name)

                
                retval = self.__whatsapp_to_telegram_sender__(content_type, data, postscipt, None) # get_reply_to_message_id(phone_number)
                if(isinstance(retval, Error)):
                    self.__wa_send_error__(retval.get_message(), modified_phone_number)
                # else:
                #     edit_db(number_id=phone_number, message_id=retval.message_id)

                logging.info(f"retval from telegram: {retval}")



    def tg_point(self, data):

        # tg_point вызывается из app request (tg_webhook)

        if 'message' in data:
            message = data['message']

            reply_message = message['reply_to_message'] if 'reply_to_message' in message else None
            mobile = ""

            message_id = message['message_id']

            logging.info(f"telegram data: {data}")

            # -- бот отправляет сообщение из чата группы пользователю --

            if(not reply_message is None and reply_message['from']['id'] == self.__TG_BOT_ID and message['chat']['id'] == self.__TG_CHAT_ID):
                if(reply_message.get('text') and not (reply_message['text'] in self.whatsapp_bot.error_notifications.values())):

                    logging.info(f"Message from telegram: {message}", )

                    last_line = reply_message['text'].split("\n")[-1]
                    mobile = last_line.split(" ")[-2]

                    content_type = self.telegram_bot.get_content_type(message)

                    retval = self.__telegram_to_whatsapp_sender__(message, self.__wa_modify_rus_number__(mobile[1:]), content_type)
                    if(isinstance(retval, Error)):
                        self.__tg_send_error__(self.__TG_CHAT_ID, message_id = message_id, message_text = retval.get_message())

                    logging.info(f"retval from whatsapp: {retval}")

                    # else:
                    #     save_tg_status(message_id)

                   
    @wa_check_errors
    def __whatsapp_to_telegram_sender__(self, content_type, data, postscipt, message_id):

        # __whatsapp_to_telegram_sender__ пересылает сообщение из ватсапа в телеграм

        if content_type == "text":
            message = self.whatsapp_bot.get_message(data)
            return self.telegram_bot.send_message(self.__TG_CHAT_ID, message, postscipt, reply_id=message_id)

        elif content_type == "document":
            file, content = self.__wa_get_content__(data, content_type)
            filename = file["filename"] if file else None
            return self.telegram_bot.send_document(self.__TG_CHAT_ID, content, filename, postscipt, reply_id=message_id)

        elif content_type == 'audio':
            _, content = self.__wa_get_content__(data, content_type)
            return self.telegram_bot.send_audio(self.__TG_CHAT_ID, content, postscipt, reply_id=message_id)

        elif content_type == 'video':
            video, content = self.__wa_get_content__(data, content_type)
            caption = video['caption'] if (video and 'caption' in video) else ""
            return self.telegram_bot.send_video(self.__TG_CHAT_ID, content, caption, postscipt, reply_id=message_id)

        elif content_type == "image":
            image, content = self.__wa_get_content__(data, content_type)
            caption = image['caption'] if (image and 'caption' in image) else ""
            return self.telegram_bot.send_photo(self.__TG_CHAT_ID, content, caption, postscipt, reply_id=message_id)

        elif content_type == "location":
            location = self.whatsapp_bot.get_data(data, content_type)
            if(location):
                latitude = location['latitude']
                longitude = location['longitude']
                name = location.get('name')
                name = '' if name is None else name
                address = location.get('address')
                address = '' if address is None else address
                return self.telegram_bot.send_location(self.__TG_CHAT_ID, latitude, longitude, name, address, postscipt, reply_id=message_id)

        elif content_type == "contacts":
            contact = self.whatsapp_bot.get_data(data, content_type)[0]
            if(contact and 'phones' in contact):
                return self.telegram_bot.send_message(self.__TG_CHAT_ID, "Contact: " + contact['name']['first_name'] + " +" + contact['phones'][0]['wa_id'], postscipt, reply_id=message_id)

        return Error(self.telegram_bot.error_notifications['content'])

    @tg_check_errors
    def __telegram_to_whatsapp_sender__(self, message, number, content_type):

        # __telegram_to_whatsapp_sender__ пересылает сообщение из телеграма в ватсап

        if content_type == "text": # работает
            return self.whatsapp_bot.send_message(message[content_type], number)

        elif content_type == 'document': # работает
            file_id = message[content_type]['file_id']
            filename = message[content_type]['file_name'].rsplit(".",1)[0]
            media_id = self.__wa_upload_media__(file_id)
            if(media_id):
                return self.whatsapp_bot.send_document(media_id['id'], number, filename, message.get('caption'))

        elif content_type == 'photo': # работает
            file_id = message[content_type][-1]['file_id']
            media_id = self.__wa_upload_media__(file_id)
            if(media_id):
                return self.whatsapp_bot.send_image(media_id['id'], number, message.get('caption'))

        elif content_type in ['audio', 'voice']: # не работает для голосовых сообщений
            file_id = message[content_type]['file_id']

            type = None
            if(content_type == 'voice'):
                type = "audio/ogg; codecs=opus"
                type = "audio/opus"

            media_id = self.__wa_upload_media__(file_id, content_type=type)
            if(media_id):
                return self.whatsapp_bot.send_audio(media_id['id'], number, message.get('caption'))

        elif content_type in ['video', 'video_note']: # работает
            file_id = message[content_type]['file_id']
            media_id = self.__wa_upload_media__(file_id)
            if(media_id):
                return self.whatsapp_bot.send_video(media_id['id'], number, message.get('caption'))

        elif content_type == 'location': # работает
            location_latitude = message['location']['latitude']
            location_longitude = message['location']['longitude']
            location_info = message.get('venue')
            title = None
            address = None
            if(location_info):
                title = location_info['title']
                address = location_info['address']
            return self.whatsapp_bot.send_location(location_latitude, location_longitude, title, address, number)

        return Error(self.whatsapp_bot.error_notifications['content'])

    def __wa_upload_media__(self, file_id, content_type=None):

        # __wa_upload_media__ скачивает файл по url из телеграма и загружает в ватсап
       
        file_info = self.telegram_bot.get_file(file_id)

        # file_url = self.telegram_bot.get_file_url(file_id)

        downloaded_file = self.telegram_bot.download_file(file_info.file_path)

        media_id = self.whatsapp_bot.upload_media(downloaded_file, file_info.file_path, content_type)
        logging.info(f"media_id:{media_id}")

        return media_id


    def __wa_get_content__(self, data, content_type) -> tuple:

        # __wa_get_content__ получает бинарный файл по запросу

        file = self.whatsapp_bot.get_data(data, content_type)
        logging.info(f"TYPE OF FILE: {type(file)}")
        if(file):
            file_id, mime_type = file["id"], file["mime_type"]
            file_url = self.whatsapp_bot.query_media_url(file_id)
            content = self.whatsapp_bot.get_content(file_url, mime_type)
            return file, content
        return None, None

    def __wa_modify_rus_number__(self, number) -> str:

        # __wa_modify_rus_number__ добавляет к российскому номеру код "78"

        match = fullmatch("^7\d{10}", number)
        logging.info(number)
        if(match):               # если номер российский
            return "78"+number[1:]
        return number

    def __tg_generate_user_info__(self, number, username) -> str:

        # __tg_generate_user_info__ генерирует информацию о пользователе из ватсапа

        generated_message = "\n\n"
        generated_message += '<i>~whatsapp</i> '
        generated_message += f'<a href="https://wa.me/{number}">{username}</a>' + " +" + number + " #ID" + number
        return f'{generated_message}'

    def __tg_send_error__(self, chat_id, message_id, message_text):

        # __tg_send_error__ телеграм-бот печатает ошибку в групповой чат

        return self.telegram_bot.send_message(chat_id, message=message_text, postscipt="", reply_id = message_id)

    def __wa_send_error__(self, number, message_text):

        # __wa_send_error__ ватсап-бот печатает ошибку в чат с пользователем

        return self.whatsapp_bot.send_message(message_text, number)

    def get_wa_verify_token(self) -> str:

        return self.__WA_VERIFY_TOKEN

    def get_tg_chat_id(self):
        return self.__TG_CHAT_ID
    #
    # def get_wa_access_token(self):
    #     return self.__WA_ACCESS_TOKEN
    #
    # def get_wa_number_id(self):
    #     return self.__WA_NUMBER_ID
    #
    def get_tg_api_token(self):
        return self.__TG_API_TOKEN
