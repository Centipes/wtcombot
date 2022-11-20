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
        except Error as error_from_telegram:
            raise error_from_telegram
        except Exception as err:
            logging.error(f"method: tg_check_errors :{err}")
            logging.exception("message")
            raise Error(self.whatsapp_bot.error_notifications["sending"])
    return wrapper

# -- декоратор-обработчик исключений для ватсапа --
def wa_check_errors(wa_sender):
    def wrapper(self, content_type, data, postscipt, message_id):
        try:
            return wa_sender(self, content_type, data, postscipt, message_id)
        except Error as error_from_whatsapp:
            raise error_from_whatsapp
        except Exception as err:
            logging.error(f"method: wa_check_errors : {err}")
            logging.exception("message")
            raise Error(self.telegram_bot.error_notifications["sending"])
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

        def digit(n) -> int:
            try:
                return int(n)
            except ValueError:
                return 0
            except TypeError:
                return 0

        self.__TG_CHAT_ID = digit(self.__TG_CHAT_ID) 
        self.__TG_BOT_ID = digit(self.__TG_BOT_ID)

        return self.__WA_NUMBER_ID and self.__WA_ACCESS_TOKEN and self.__WA_VERIFY_TOKEN and self.__TG_CHAT_ID and self.__TG_BOT_ID and self.__TG_API_TOKEN

    def wa_point(self, data) -> None:

        # wa_point вызывается из app request (wa_webhook)

        logging.info("Received whatsapp webhook data: %s", data)
        changed_field = self.whatsapp_bot.changed_field(data)

        if changed_field == "messages":
            phone_number = self.whatsapp_bot.get_mobile(data)

            if phone_number:
                modified_phone_number = self.__modify_rus_number__(phone_number)
                name = self.whatsapp_bot.get_name(data)
                content_type = self.whatsapp_bot.get_message_type(data)
                postscipt = self.whatsapp_bot.generate_user_info(phone_number, name)

                try:
                    sending_status = self.__whatsapp_to_telegram_sender__(data, postscipt, content_type, None) # get_reply_to_message_id(phone_number)
                except Error as err:
                    self.__wa_send_error__(err.get_message(), modified_phone_number)

                logging.info(f"sending_status from telegram: {sending_status}")


    def tg_point(self, data) -> None:

        # tg_point вызывается из app request (tg_webhook)

        logging.info("Received telegram webhook data: %s", data)
        message = data.get('message')

        if message:
            message_for_bot = self.__tg_check_reply_message_to_bot__(message)

            # -- бот отправляет сообщение из чата группы пользователю --

            if(message_for_bot):
                phone_number = self.telegram_bot.get_phone_number(message_for_bot)
                content_type = self.telegram_bot.get_content_type(message)
                message_id = self.telegram_bot.get_message_id(message)

                try:
                    sending_status = self.__telegram_to_whatsapp_sender__(message, self.__modify_rus_number__(phone_number[1:]), content_type)
                except Error as err:
                    self.__tg_send_error__(self.__TG_CHAT_ID, message_id = message_id, message_text = err.get_message())

                logging.info(f"sending_status from whatsapp: {sending_status}")

                   
    @wa_check_errors
    def __whatsapp_to_telegram_sender__(self, data, postscipt, content_type, message_id):

        # __whatsapp_to_telegram_sender__ пересылает сообщение из ватсапа в телеграм

        if content_type == "text":
            message = self.whatsapp_bot.get_message(data)
            return self.telegram_bot.send_message(self.__TG_CHAT_ID, message, postscipt, reply_id=message_id)

        elif content_type == "document":
            content = self.whatsapp_bot.get_binary_file(data, content_type)
            filename = self.whatsapp_bot.get_filename()
            return self.telegram_bot.send_document(self.__TG_CHAT_ID, content, filename, postscipt, reply_id=message_id)

        elif content_type == 'audio':
            content = self.whatsapp_bot.get_binary_file(data, content_type)
            return self.telegram_bot.send_audio(self.__TG_CHAT_ID, content, postscipt, reply_id=message_id)

        elif content_type == 'video':
            content = self.whatsapp_bot.get_binary_file(data, content_type)
            caption = self.whatsapp_bot.get_caption()
            return self.telegram_bot.send_video(self.__TG_CHAT_ID, content, caption, postscipt, reply_id=message_id)

        elif content_type == "image":
            content = self.whatsapp_bot.get_binary_file(data, content_type)
            caption = self.whatsapp_bot.get_caption()
            return self.telegram_bot.send_photo(self.__TG_CHAT_ID, content, caption, postscipt, reply_id=message_id)

        elif content_type == "location":
            location = self.whatsapp_bot.get_data(data, content_type)
            if(location):
                latitude, longitude = self.whatsapp_bot.get_geodata(location)
                name, address = self.whatsapp_bot.get_place(location)
                return self.telegram_bot.send_location(self.__TG_CHAT_ID, latitude, longitude, name, address, postscipt, reply_id=message_id)

        elif content_type == "contacts":
            contact = self.whatsapp_bot.get_data(data, content_type)[0]
            if(contact.get('phones')):
                return self.telegram_bot.send_message(self.__TG_CHAT_ID, "Contact: " + contact['name']['first_name'] + " +" + contact['phones'][0]['wa_id'], postscipt, reply_id=message_id)

        raise Error(self.telegram_bot.error_notifications['content'])

    @tg_check_errors
    def __telegram_to_whatsapp_sender__(self, message, number, content_type):

        # __telegram_to_whatsapp_sender__ пересылает сообщение из телеграма в ватсап

        if content_type == "text": # работает
            return self.whatsapp_bot.send_message(message[content_type], number)

        elif content_type == 'document': # работает
            file_id = self.telegram_bot.get_file_id(message, content_type)
            filename = self.telegram_bot.get_filename(message, content_type)
            media_id = self.__wa_upload_media__(file_id)
            return self.whatsapp_bot.send_document(media_id, number, filename, message.get('caption'))

        elif content_type == 'photo': # работает
            file_id = self.telegram_bot.get_photo_id(message)
            media_id = self.__wa_upload_media__(file_id)
            return self.whatsapp_bot.send_image(media_id, number, message.get('caption'))

        elif content_type in ['audio', 'voice']: # не работает для голосовых сообщений
            file_id = self.telegram_bot.get_file_id(message, content_type)

            type = None
            if content_type == 'voice':
                type = "audio/ogg; codecs=opus"
                type = "audio/opus"

            media_id = self.__wa_upload_media__(file_id, content_type=type)
            return self.whatsapp_bot.send_audio(media_id, number, message.get('caption'))

        elif content_type in ['video', 'video_note']: # работает
            file_id = self.telegram_bot.get_file_id(message, content_type)
            media_id = self.__wa_upload_media__(file_id)
            return self.whatsapp_bot.send_video(media_id, number, message.get('caption'))

        elif content_type == 'location': # работает
            location_latitude, location_longitude = self.telegram_bot.get_geodata(message)
            location_info = message.get('venue')
            title, address = self.telegram_bot.get_place(location_info) if location_info else None, None
            return self.whatsapp_bot.send_location(location_latitude, location_longitude, title, address, number)

        raise Error(self.whatsapp_bot.error_notifications['content'])

    def __tg_check_reply_message_to_bot__(self, message) -> str:

        # __tg_check_reply_message_to_bot__ возвращает текст сообщения от участника телеграм-группы, если он ответил на сообщение бота

        reply_message = message.get('reply_to_message')
        reply_message_from_id = None
        reply_message_text = ''
        chat_id =  self.telegram_bot.get_chat_id(message)

        if reply_message:
            reply_message_from_id = self.telegram_bot.get_reply_message_from_id(reply_message)
            reply_message_text = self.telegram_bot.get_reply_message_text(reply_message)

        if(reply_message_from_id != self.__TG_BOT_ID):
            return ''
        if(chat_id != self.__TG_CHAT_ID):
            return ''
        if(not reply_message_text or reply_message_text in self.whatsapp_bot.error_notifications.values()):
            return ''

        return reply_message_text

    def __wa_upload_media__(self, file_id, content_type=None):

        # __wa_upload_media__ скачивает файл по url из телеграма и загружает в ватсап
       
        file_info = self.telegram_bot.get_file(file_id)
        # file_url = self.telegram_bot.get_file_url(file_id)
        downloaded_file = self.telegram_bot.download_file(file_info.file_path)
        media_id = self.whatsapp_bot.upload_media(downloaded_file, file_info.file_path, content_type)

        return media_id['id'] if media_id else media_id

    def __tg_send_error__(self, chat_id, message_id, message_text):

        # __tg_send_error__ телеграм-бот печатает ошибку в групповой чат

        return self.telegram_bot.send_message(chat_id, message=message_text, postscipt="", reply_id = message_id)

    def __wa_send_error__(self, number, message_text):

        # __wa_send_error__ ватсап-бот печатает ошибку в чат с пользователем

        return self.whatsapp_bot.send_message(message_text, number)

    def __modify_rus_number__(self, number) -> str:

        # __modify_rus_number__ добавляет к российскому номеру код "78"

        match = fullmatch("^7\d{10}", number) # например 79997865656
        logging.info(number)
        if(match):                            # если номер российский
            return "78"+number[1:]
        return number

    def get_wa_verify_token(self) -> str:

        return self.__WA_VERIFY_TOKEN

    def get_tg_chat_id(self) -> int:
        return self.__TG_CHAT_ID
    #
    # def get_wa_access_token(self) -> str:
    #     return self.__WA_ACCESS_TOKEN
    #
    # def get_wa_number_id(self) -> str:
    #     return self.__WA_NUMBER_ID
    #
    # def get_tg_api_token(self) -> str:
    #     return self.__TG_API_TOKEN
