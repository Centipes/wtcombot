from telebot import TeleBot
from requests_toolbelt.multipart.encoder import MultipartEncoder
import logging
import requests
import mimetypes
from heyoo import WhatsApp
from flask import Flask, request, make_response, abort
import re

from os import getenv
from dotenv import load_dotenv

# -- сообщения о ошибках, которые телеграм-бот будет отправлять в чат --
tg_error_notifications = {"uploading": "Error uploading media", "sending":"Error sending message", "content": "Content error"}
# -- сообщения о ошибках, которые ватсап-бот будет отправлять в чат --
wa_error_notifications = {"content": "This type of content cannot be forwarded to our operators", "sending": "I can't send a message, please contact our operators in another way"}

class Error():
    def __init__(self, error_message):
        self.__error_message = error_message
    def get_message(self):
        return self.__error_message

# -- декоратор-обработчик исключений для телеграма --
def tg_check_errors(tg_sender):
    def wrapper(self, message, number, content_type):
        try:
            return tg_sender(self, message, number, content_type)
        except Exception as err:
            logging.error(err)
            logging.exception("message")
            return Error(tg_error_notifications["sending"])
    return wrapper

# -- декоратор-обработчик исключений для ватсапа --
def wa_check_errors(wa_sender):
    def wrapper(self, content_type, data, postscipt, message_id):
        try:
            return wa_sender(self, content_type, data, postscipt, message_id)
        except Exception as err:
            logging.error(err)
            logging.exception("message")
            return Error(tg_error_notifications["sending"])
    return wrapper

class WhatsAppBot(WhatsApp):

    def __init__(self, WA_ACCESS_TOKEN, WA_NUMBER_ID):
        super().__init__(WA_ACCESS_TOKEN,  phone_number_id = WA_NUMBER_ID)
        self.base_url = "https://graph.facebook.com/v15.0"

    def get_content(self, media_url, mime_type):
        r = requests.get(media_url, headers=self.headers)
        content = r.content
        return content

    def get_data(self, data, content_type):

        try:
            data = self.preprocess(data)
            if "messages" in data:
                if content_type in data["messages"][0]:
                    return data["messages"][0][content_type]
        except Exception as e:
            logging.error(e)
            logging.exception("message")
        return None

    def __check_message__(self, response, second_message, number): # переделать

        # __check_message__  возвращает Error, если запрос завершился с ошибкой.
        # В случае успеха возвращает True

        if(response.get("error")):
            logging.error(response)
            if(second_message):
                return Error(tg_error_notifications["uploading"])
            return Error(tg_error_notifications["sending"])

        logging.info(f"WhatsApp messenge from telegram: {response}")

        if(second_message):
            return self.send_message(second_message, number)

        return True

    def send_message(self, message, number):
        response = super().send_message(message, number)
        return self.__check_message__(response, None, number)
       

    def send_document(self, media_id, number, filename, second_message):
        response = super().send_document(document=media_id, recipient_id=number, caption=filename, link=False)
        return self.__check_message__(response, second_message, number)

    def send_image(self, media_id, number, caption_text):
        response = super().send_image(image=media_id, recipient_id=number, caption=caption_text, link=False)
        return self.__check_message__(response, None, number)

    def send_audio(self, media_id, number, second_message):
        response = super().send_audio(audio=media_id, recipient_id=number, link=False)
        return self.__check_message__(response, second_message, number)

    def send_video(self, media_id, number, caption_text):
        response = super().send_video(video=media_id, recipient_id=number, caption=caption_text, link=False)
        return self.__check_message__(response, None, number)

    def send_location(self, location_latitude, location_longitude, title, address, number):
        response = super().send_location(location_latitude, location_longitude, name=title, address=address, recipient_id=number)
        return self.__check_message__(response, None, number)

    def upload_media(self, content, media, content_type = None):

        type = mimetypes.guess_type(media)[0] if content_type is None else content_type
        logging.info(f"type:{type}")

        form_data = {
            "file": (
                media,
                content,
                type
            ),
            "messaging_product": "whatsapp",
            "type": type,
        }
        form_data = MultipartEncoder(fields=form_data)
        headers = self.headers.copy()
        headers["Content-Type"] = form_data.content_type
        logging.info(f"headers {headers}")
        logging.info(f"Content-Type: {form_data.content_type}")
        logging.info(f"Uploading media {media}")
      
        r = requests.post(
            f"{self.base_url}/{self.phone_number_id}/media",
            headers=headers,
            data=form_data
            )

        if r.status_code == 200:
            logging.info(f"Media {media} uploaded")
            return r.json()
        logging.info(f"Error uploading media {media}")
        logging.info(f"Status code: {r.status_code}")
        logging.info(f"Response: {r.json()}")
        return None



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

class TGWACOM():
    def __init__(self):

        self.__ENV_FILE = 'WT_COMBOT_ENVFILE.env'
        load_dotenv(self.__ENV_FILE)

        self.__WA_NUMBER_ID = getenv('WT_COMBOT_WA_NUMBER_ID')
        self.__WA_ACCESS_TOKEN = getenv('WT_COMBOT_WA_ACCESS_TOKEN')
        self.__WA_VERIFY_TOKEN = getenv('WT_COMBOT_WA_VERIFY_TOKEN')

        self.__TG_CHAT_ID = int(getenv('WT_COMBOT_TG_CHAT_ID'))
        self.__TG_BOT_ID = int(getenv('WT_BOT_CHAT_ID'))
        self.__TG_API_TOKEN = getenv('WT_COMBOT_TG_API_TOKEN')


        print('WA_NUMBER_ID = ', self.__WA_NUMBER_ID)
        print('WA_ACCESS_TOKEN = ', self.__WA_ACCESS_TOKEN)
        print('WA_VERIFY_TOKEN = ', self.__WA_VERIFY_TOKEN)
        print('TG_CHAT_ID = ', self.__TG_CHAT_ID)
        print('TG_BOT_ID = ', self.__TG_BOT_ID)
        print('TG_API_TOKEN = ', self.__TG_API_TOKEN)

    def setup(self):
        self.whatsapp_bot = WhatsAppBot(self.__WA_ACCESS_TOKEN, self.__WA_NUMBER_ID)
        self.telegram_bot = TelegramBot(self.__TG_API_TOKEN)

    def check_env_variables(self):

        # check_env_variables проверяет переменные окружения

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
                if(reply_message.get('text') and not (reply_message['text'] in tg_error_notifications.values())):

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
            return self.telegram_bot.send_text(self.__TG_CHAT_ID, message, postscipt, reply_id=message_id)

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

        return Error(wa_error_notifications['content'])

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

        return Error(tg_error_notifications['content'])

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
        if(file):
            file_id, mime_type = file["id"], file["mime_type"]
            file_url = self.whatsapp_bot.query_media_url(file_id)
            content = self.whatsapp_bot.get_content(file_url, mime_type)
            return file, content
        return None, None

    def __wa_modify_rus_number__(self, number) -> str:

        # __wa_modify_rus_number__ добавляет к российскому номеру код "78"

        match = re.fullmatch("^7\d{10}", number)
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

    def get_wa_verify_token(self):

        return self.__WA_VERIFY_TOKEN

    # def get_tg_chat_id(self):
    #     return self.__TG_CHAT_ID
    #
    # def get_wa_access_token(self):
    #     return self.__WA_ACCESS_TOKEN
    #
    # def get_wa_number_id(self):
    #     return self.__WA_NUMBER_ID
    #
    # def get_tg_api_token(self):
    #     return self.__TG_API_TOKEN



## -----------------------------------------------------------------------------

app = Flask(__name__)
tgwacombot = TGWACOM()

# ВАТСАП
@app.route("/w", methods=["GET", "POST"])
def wa_webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == tgwacombot.get_wa_verify_token():
            response = make_response(request.args.get("hub.challenge"), 200)
            response.mimetype = "text/plain"
            return response
    try:
        data = request.get_json()
        tgwacombot.wa_point(data)
    except Exception as e:
        logging.error(f'WhatsApp: {e}')
        logging.exception("message")
        abort(400)
    return ''


# ТЕЛЕГРАМ
@app.route("/t", methods=["GET", "POST"])
def tg_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        logging.info(f"json telegram: {json_string}")

        try:
            data = request.get_json()
            tgwacombot.tg_point(data)
        except Exception as e:
            logging.error(f'Telegram {e}')
            logging.exception("message")
            abort(400)
    else:
        abort(403)
    return ''



if __name__ == "__main__":
    if tgwacombot.check_env_variables():
        tgwacombot.setup()
        app.run(port=5000, debug=True)
