import logging
import requests

from mimetypes import guess_type
from requests_toolbelt.multipart.encoder import MultipartEncoder
from heyoo import WhatsApp

from wterror import Error


class WhatsAppBot(WhatsApp):

    def __init__(self, WA_ACCESS_TOKEN, WA_NUMBER_ID):
        super().__init__(WA_ACCESS_TOKEN,  phone_number_id = WA_NUMBER_ID)
        self.base_url = "https://graph.facebook.com/v15.0"
        # -- сообщения о ошибках, которые телеграм-бот будет отправлять в чат --
        self.error_notifications = {"uploading": "Error uploading media", "sending":"Error sending message", "content": "Content error"}
        self.file = None
        
    def generate_user_info(self, number, username) -> str:

        # generate_user_info генерирует информацию о пользователе из ватсапа

        generated_message = "\n\n"
        generated_message += '<i>~whatsapp</i> '
        generated_message += f'<a href="https://wa.me/{number}">{username}</a>' + " +" + number + " #ID" + number
        return f'{generated_message}'

    def get_binary_file(self, data, content_type):
        self.file = self.get_data(data, content_type)
        if(self.file):
            file_id, mime_type = self.file["id"], self.file["mime_type"]
            file_url = self.query_media_url(file_id)
            content = self.get_content(file_url, mime_type)
            return content
        return None

    def get_data(self, data, content_type) -> dict:
        try:
            data = self.preprocess(data)
            if "messages" in data:
                if content_type in data["messages"][0]:
                    return data["messages"][0][content_type]
        except Exception as e:
            logging.error(f"class: WhatsAppBot, method: get_data : {e}")
            logging.exception("message")
        return dict()

    def get_content(self, media_url, mime_type):
        try:
            r = requests.get(media_url, headers=self.headers)
            content = r.content
            return content
        except Exception as e:
            logging.error(f"class: WhatsAppBot, method: get_content : {e}")
            logging.exception("message")
        return None

    def get_caption(self) -> str:
        return self.file.get('caption', '') if self.file else ''

    def get_filename(self) -> str|None:
        return self.file["filename"] if self.file else None

    def get_geodata(self, location) -> tuple:
        latitude, longitude = location['latitude'], location['longitude']
        return latitude, longitude

    def get_place(self, location) -> tuple:
        return location.get('name', ''), location.get('address', '')

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

        type = guess_type(media)[0] if content_type is None else content_type
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

    def __check_message__(self, response, second_message, number) -> dict:

        # __check_message__  генерирует исключение, если запрос завершился с ошибкой.
        # В случае успеха возвращает response

        if(response.get("error")):
            logging.error(response)
            if(second_message):
                raise Error(self.error_notifications["uploading"])
            raise Error(self.error_notifications["sending"])

        logging.info(f"WhatsApp messenge from telegram: {response}")

        if(second_message):
            return self.send_message(second_message, number)

        return response
