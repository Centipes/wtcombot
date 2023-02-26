import requests
from logging import info as log_info, error as log_error

from mimetypes import guess_type
from requests_toolbelt.multipart.encoder import MultipartEncoder
from heyoo import WhatsApp

from wterror import WTCombotError


class WhatsAppBot(WhatsApp):

    def __init__(self, WA_ACCESS_TOKEN, WA_NUMBER_ID):
        super().__init__(WA_ACCESS_TOKEN,  phone_number_id = WA_NUMBER_ID)
        self.base_url = "https://graph.facebook.com/v15.0"
        # -- сообщения о ошибках, которые телеграм-бот будет отправлять в чат --
        self.error_notifications = {"uploading": "Error uploading media", 
                                    "sending":"Error sending message", 
                                    "content": "Content error", 
                                    "number": "Please, reply to the message that contains the phone number",
                                     131047 : "Message failed to send because more than 24 hours have passed since the customer last replied to this number."}
        self.file = None
        
    def generate_user_info(self, number, username) -> str:

        # generate_user_info генерирует информацию о пользователе из ватсапа

        generated_message = "\n\n"
        generated_message += '<i>~whatsapp</i> '
        generated_message += f'<a href="https://wa.me/{number}">{username}</a>' + " +" + number + " #ID" + number
        return f'{generated_message}'

    def get_name(self, prep_data) -> str:
        return prep_data["contacts"][0]["profile"]["name"]
        
    def get_mobile(self, prep_data) -> str:
        try:
            return prep_data["contacts"][0]["wa_id"]
        except Exception:
            return ''
        
    def get_status(self, prep_data) -> str:
        if('statuses' in prep_data):
            return prep_data['statuses'][0]
        return ''

    def get_errors(self, status) -> str:
        if('errors' in status):
            return status['errors'][0]
        return ''

    def get_recipient_id(self, status) -> str|None:
        return status.get('recipient_id')
       
    def get_message_type(self, prep_data) -> str:
        return prep_data["messages"][0]["type"]

    def get_binary_file(self, file) -> bytes:
        file_id, mime_type = file["id"], file["mime_type"]
        file_url = self.query_media_url(file_id)
        content = self.get_content(file_url, mime_type)
        return content
    
    def get_content(self, media_url, mime_type) -> bytes:
        r = requests.get(media_url, headers=self.headers)
        content = r.content
        return content

    def get_data(self, prep_data, content_type) -> dict:
        return prep_data["messages"][0][content_type]
    
    def get_text_info(self, data, content_type) -> str:
        text = self.get_message(data)
        if(not text and (content_type=="video" or content_type=="image")):
            text = data.get('caption', '') if data else ''
        return text

    def get_caption(self, file) -> str:
        return file.get('caption', '') if file else ''

    def get_filename(self, file) -> str|None:
        return file["filename"] if file else None

    def get_geodata(self, location) -> tuple[float, float]:
        latitude, longitude = location['latitude'], location['longitude']
        return latitude, longitude

    def get_place(self, location) -> tuple[str,str]:
        return location.get('name', ''), location.get('address', '')

    def get_message(self, prep_data) -> str:
        return prep_data.get('body', '')

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
        response = super().send_location(lat=location_latitude, long=location_longitude, name=title, address=address, recipient_id=number)
        return self.__check_message__(response, None, number)

    def upload_media(self, content, media, content_type = None) -> dict:

        type_media = guess_type(media)[0] if content_type is None else content_type

        form_data = {
            "file": (
                media,
                content,
                type_media
            ),
            "messaging_product": "whatsapp",
            "type": type_media,
        }
        form_data = MultipartEncoder(fields=form_data)
        headers = self.headers.copy()
        headers["Content-Type"] = form_data.content_type
        log_info(f"headers: {headers}")
        log_info(f"Content-Type: {form_data.content_type}")
        log_info(f"Uploading media: {media}")
      
        r = requests.post(
            f"{self.base_url}/{self.phone_number_id}/media",
            headers=headers,
            data=form_data
            )

        if r.status_code == 200:
            log_info(f"Media {media} uploaded")
            return r.json()
        log_info(f"Error uploading media {media}")
        log_info(f"Status code: {r.status_code}")
        log_info(f"Response: {r.json()}")
        raise WTCombotError(self.error_notifications["uploading"])

    def __check_message__(self, response, second_message, number) -> dict:

        # __check_message__  генерирует исключение, если запрос завершился с ошибкой.
        # В случае успеха возвращает response

        if(response.get("error")):
            log_error(f"Error whatsapp response: {response}")
            if(second_message):
                raise WTCombotError(self.error_notifications["uploading"])
            raise WTCombotError(self.error_notifications["sending"])

        if(second_message):
            return self.send_message(second_message, number)

        return response