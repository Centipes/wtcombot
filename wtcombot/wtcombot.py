from logging import info as log_info, error as log_error, exception as log_exception  
from psycopg2 import connect as ps_connect
from re import fullmatch
from os import getenv, strerror
from errno import ENOENT
from dotenv import load_dotenv
from kafka.structs import OffsetAndMetadata

from wterror import WTCombotError
from tgbot import TelegramBot
from wabot import WhatsAppBot


class TGWACOM():
    def __init__(self, filename):
        log_info("Create TGWACOM")
        self.__ENV_FILE = filename
        if(not load_dotenv(self.__ENV_FILE)):
            raise FileNotFoundError(ENOENT, strerror(ENOENT), self.__ENV_FILE)
        
        self.__WA_NUMBER_ID = getenv('WT_COMBOT_WA_NUMBER_ID')
        self.__WA_ACCESS_TOKEN = getenv('WT_COMBOT_WA_ACCESS_TOKEN')
        self.__WA_VERIFY_TOKEN = getenv('WT_COMBOT_WA_VERIFY_TOKEN')

        self.__TG_CHAT_ID = getenv('WT_COMBOT_TG_CHAT_ID')
        self.__TG_BOT_ID = getenv('WT_COMBOT_TG_BOT_ID')
        self.__TG_API_TOKEN = getenv('WT_COMBOT_TG_API_TOKEN')

        self.__DB_NAME = getenv('WT_COMBOT_DB_NAME')
        self.__DB_USER = getenv('WT_COMBOT_DB_USER')
        self.__DB_PASSWORD = getenv('WT_COMBOT_DB_PASSWORD')

        print('WA_NUMBER_ID = ', self.__WA_NUMBER_ID)
        print('WA_ACCESS_TOKEN = ', self.__WA_ACCESS_TOKEN)
        print('WA_VERIFY_TOKEN = ', self.__WA_VERIFY_TOKEN)
        print('TG_CHAT_ID = ', self.__TG_CHAT_ID)
        print('TG_BOT_ID = ', self.__TG_BOT_ID)
        print('TG_API_TOKEN = ', self.__TG_API_TOKEN)

    def setup(self) -> None:
        self.whatsapp_bot = WhatsAppBot(self.__WA_ACCESS_TOKEN, self.__WA_NUMBER_ID)
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

    def wa_point(self, json_data) -> None:

        # wa_point вызывается из app request (wa_webhook)

        log_info("Received whatsapp webhook data: %s", json_data)
        changed_field = self.whatsapp_bot.changed_field(json_data)

        if changed_field == "messages":
            phone_number = None
            old_message_id = None
            new_message_id = None
            status_connection = self.open_connection()
            
            try:
                prep_data = self.whatsapp_bot.preprocess(json_data)

                phone_number = self.whatsapp_bot.get_mobile(prep_data)
                if not phone_number:
                    return
                
                modified_phone_number = self.__modify_rus_number__(phone_number)
                old_message_id = self.get_reply_to_message_id(phone_number) #

                content_type = self.whatsapp_bot.get_message_type(prep_data) #

                name = self.whatsapp_bot.get_name(prep_data)
                postscipt = self.whatsapp_bot.generate_user_info(phone_number, name) #

                try:
                    data = self.whatsapp_bot.get_data(prep_data, content_type)
                    sent_message = self.__whatsapp_to_telegram_sender__(data, postscipt, content_type, old_message_id)
                    log_info(f"sending_status from telegram: {sent_message}")
                    new_message_id = sent_message.message_id

                except KeyError as ke:
                    log_error(f"KeyError in whatsapp {ke}")
                    log_exception("message")
                    self.__wa_send_error__(self.telegram_bot.error_notifications['content'], modified_phone_number)
                
                except WTCombotError as error_from_telegram:
                    self.__wa_send_error__(error_from_telegram.get_message(), modified_phone_number)
        
            finally:            
                if(status_connection):
                    if(phone_number and new_message_id):
                        self.set_reply_to_message_id(phone_number, old_message_id, new_message_id)
                    self.close_connection()

    def tg_point(self, data) -> None:

        # tg_point вызывается из app request (tg_webhook)

        log_info("Received telegram webhook data: %s", data)
        message = data.get('message')

        if message:
            try:
                message_id = self.telegram_bot.get_message_id(message)
                message_for_bot = self.__tg_check_reply_message_to_bot__(message)

            # -- бот отправляет сообщение из чата группы пользователю --
                log_info(f"Message for bot:{message_for_bot}")
                if(message_for_bot):
                    content_type = self.telegram_bot.get_content_type(message)
                    phone_number = self.telegram_bot.get_phone_number(message_for_bot)
                    sent_message = self.__telegram_to_whatsapp_sender__(message, self.__modify_rus_number__(phone_number[1:]), content_type)
                    log_info(f"Sending_status from whatsapp: {sent_message}")

            except WTCombotError as error_from_whatsapp:
                self.__tg_send_error__(message_id, error_from_whatsapp.get_message())

            except Exception as err:
                log_error(f"method: tg_check_errors :{err}")
                log_exception("message")
                self.__tg_send_error__(message_id, self.whatsapp_bot.error_notifications['sending'])

    def open_connection(self) -> bool:
        try:
            self.conn = ps_connect(dbname=self.__DB_NAME, user=self.__DB_USER, password=self.__DB_PASSWORD, host='localhost')
            self.cursor = self.conn.cursor()
            return True
        except Exception as err:
            log_error("Exception from open_connection: %s", err)
            log_exception("message")
        return False

    def close_connection(self) -> None:
        try:
            if(hasattr(self, 'conn')):
                self.conn.close()
            if(hasattr(self, 'cursor')):
                self.cursor.close()
        except Exception as err:
            log_error("Exception from close_connection: %s", err)

    def get_reply_to_message_id(self, phone_number) -> int|None:
        try:
            self.cursor.execute(f'SELECT message_id FROM tg_user_messages WHERE user_number={phone_number};')
            response = self.cursor.fetchone()
            return response[0] if response else None
        except Exception as err:
            log_error("Exception from get_reply_to_message_id: %s", err)
        return None

    def set_reply_to_message_id(self, phone_number, old_message_id, new_message_id) -> None:
        try:
            if(old_message_id):
                self.cursor.execute(f'UPDATE tg_user_messages SET message_id={new_message_id} WHERE user_number={phone_number};')
            else:
                self.cursor.execute(f'INSERT INTO tg_user_messages VALUES ({phone_number}, {new_message_id});')
            self.conn.commit()
        except Exception as err:
            log_error("Exception from set_reply_to_message_id: %s", err)


    def __whatsapp_to_telegram_sender__(self, data, postscipt, content_type, message_id): 

        # __whatsapp_to_telegram_sender__ пересылает сообщение из ватсапа в телеграм
        log_info(f'MESSAGE for telegram: {data}')
        if content_type == "text":
            message = self.whatsapp_bot.get_message(data)
            return self.telegram_bot.send_message(self.__TG_CHAT_ID, message, postscipt, reply_id=message_id)

        if content_type == "document":
            content = self.whatsapp_bot.get_binary_file(data)
            filename = self.whatsapp_bot.get_filename(data)
            return self.telegram_bot.send_document(self.__TG_CHAT_ID, content, filename, postscipt, reply_id=message_id)

        if content_type == 'audio':
            content = self.whatsapp_bot.get_binary_file(data)
            return self.telegram_bot.send_audio(self.__TG_CHAT_ID, content, postscipt, reply_id=message_id)

        if content_type == 'video':
            content = self.whatsapp_bot.get_binary_file(data)
            caption = self.whatsapp_bot.get_caption(data)
            return self.telegram_bot.send_video(self.__TG_CHAT_ID, content, caption, postscipt, reply_id=message_id)

        if content_type == "image":
            content = self.whatsapp_bot.get_binary_file(data)
            caption = self.whatsapp_bot.get_caption(data)
            return self.telegram_bot.send_photo(self.__TG_CHAT_ID, content, caption, postscipt, reply_id=message_id)

        if content_type == "location":
            if(data):
                latitude, longitude = self.whatsapp_bot.get_geodata(data)
                name, address = self.whatsapp_bot.get_place(data)
                return self.telegram_bot.send_location(self.__TG_CHAT_ID, latitude, longitude, name, address, postscipt, reply_id=message_id)

        elif content_type == "contacts":
            contact = data[0]
            if(contact.get('phones')):
                return self.telegram_bot.send_message(self.__TG_CHAT_ID, "Contact: " + contact['name']['first_name'] + " +" + contact['phones'][0]['wa_id'], postscipt, reply_id=message_id)

        raise WTCombotError(self.telegram_bot.error_notifications['content'])

    # @tg_check_errors
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

        elif content_type in ['audio', 'voice']: # работает
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
            title, address = self.telegram_bot.get_place(location_info) if location_info else ('', '')
            return self.whatsapp_bot.send_location(str(location_latitude), str(location_longitude), title, address, number)

        raise WTCombotError(self.whatsapp_bot.error_notifications['content'])

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
        if(reply_message_text in self.whatsapp_bot.error_notifications.values()):
            return ''
        if(not reply_message_text):
            raise WTCombotError(self.whatsapp_bot.error_notifications['number'])

        return reply_message_text

    def __wa_upload_media__(self, file_id, content_type=None) -> str:

        # __wa_upload_media__ скачивает файл по url из телеграма и загружает в ватсап
       
        file_info = self.telegram_bot.get_file(file_id)
        # file_url = self.telegram_bot.get_file_url(file_id)
        downloaded_file = self.telegram_bot.download_file(file_info.file_path)
        media_id = self.whatsapp_bot.upload_media(downloaded_file, file_info.file_path, content_type)
        log_info(f"media_id:{media_id}, type media_id: {type(media_id['id'])}, {type(media_id)}")
        return media_id['id'] if media_id else media_id

    def __tg_send_error__(self, message_id, message_text):

        # __tg_send_error__ телеграм-бот печатает ошибку в групповой чат

        return self.telegram_bot.send_message(self.__TG_CHAT_ID, message=message_text, postscript="", reply_id = message_id)

    def __wa_send_error__(self, message_text, number):

        # __wa_send_error__ ватсап-бот печатает ошибку в чат с пользователем

        return self.whatsapp_bot.send_message(message_text, number)

    def __modify_rus_number__(self, number) -> str:

        # __modify_rus_number__ добавляет к российскому номеру код "78"

        match = fullmatch("^7\d{10}", number) # например 79997865656
        if(match):                            # если номер российский
            return "78"+number[1:]
        return number

    def get_wa_verify_token(self) -> str:
        return self.__WA_VERIFY_TOKEN

    def get_tg_chat_id(self) -> int:
        return self.__TG_CHAT_ID

    def consumeData(self, consumer, wt_point, args) -> None:
        meta = args[0]
        tp = args[1]
    
        for msg in consumer:
            data = msg.value
            wt_point(data)
            options = {tp: OffsetAndMetadata(msg.offset+1, meta)}
            consumer.commit(options)