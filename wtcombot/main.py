from sys import argv
from json import dumps, loads
import signal
from logging import info as log_info, error as log_error, exception as log_exception  
from flask import Flask, request, make_response, abort
from telebot import types as tb_types
from kafka import KafkaProducer, KafkaConsumer
from kafka.structs import TopicPartition
from threading import Thread, Event
from kafka.errors import KafkaTimeoutError, KafkaError 

from wtcombot import TGWACOM

producer = KafkaProducer(value_serializer=lambda v: dumps(v).encode('utf-8'), api_version=(0,10,2), bootstrap_servers=['localhost:9092'])

filename = argv[1] if len(argv) == 2 else '../WT_COMBOT_ENVFILE.env'
log_info(f"File env: {filename}")
tgwacombot = TGWACOM(filename)

app = Flask(__name__)

class BackgroundThread(Thread):
    def __init__(self, target, args):
        Thread.__init__(self)
        
        self.topic = args[0]
        self.wt_point = target
        self.consumer = KafkaConsumer(self.topic, value_deserializer=lambda v: loads(v.decode('utf-8')), auto_offset_reset='earliest',
                                bootstrap_servers=['localhost:9092'], group_id="test-consumer-group", consumer_timeout_ms=500, enable_auto_commit=False, api_version=(0,10,2))
        
        partition = 0
        meta = self.consumer.partitions_for_topic(self.topic)
        tp = TopicPartition(self.topic, partition)
        
        self.options = (meta, tp)
        self._stop_event = Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _stopped(self) -> bool:
        return self._stop_event.is_set()
    
    def handle(self) -> None:
        tgwacombot.consumeData(self.consumer, self.wt_point, self.options)

    def run(self) -> None:
        log_info('Running Consumer..')
        try:
            while not self._stopped():
                self.handle()
        except KafkaError as ke:
            log_error(f'KafkaLogsConsumer error sending log to Kafka: {ke}')  
            log_exception('message')  
        except Exception as e:
            log_error(f'Error in {self.topic}. KafkaLogsProducer exception sending log to Kafka: {e}')
            log_exception('message')
        finally:
            self.consumer.close()
            log_info(f"consumer with topic '{self.topic}' closed")

def producer_launch(request, topic) -> None:
    try:
        data = request.get_json()
        producer.send(topic, data)
    except KafkaTimeoutError as kte:
        log_error(f'KafkaLogsConsumer timeout sending log to Kafka: {kte}')
        log_exception('message')
    except KafkaError as ke:
        log_error(f'KafkaLogsConsumer error sending log to Kafka: {ke}')  
        log_exception('message')  
    except Exception as e:
        log_error(f'WhatsApp Error: {e}')
        log_exception('message')

def launch_consumers() -> None:
    whatsapp_consumer_thread = BackgroundThread(target=tgwacombot.wa_point, args=('whatsapp',))
    telegram_consumer_thread = BackgroundThread(target=tgwacombot.tg_point, args=('telegram',))
    whatsapp_consumer_thread.start()
    telegram_consumer_thread.start()

    original_handler = signal.getsignal(signal.SIGINT) 

    def sigint_handler(signum, frame):
        whatsapp_consumer_thread.stop()
        telegram_consumer_thread.stop()
        log_info("Threads stop")

        if whatsapp_consumer_thread.is_alive():
            whatsapp_consumer_thread.join()
            log_info("Thread stop")
        if telegram_consumer_thread.is_alive():
            telegram_consumer_thread.join()
            log_info("Thread stop")

        original_handler(signum, frame)

    try:
        signal.signal(signal.SIGINT, sigint_handler)
    except ValueError as e:
        log_error(f'{e}. Continuing execution...')

# ВАТСАП
@app.route("/w", methods=["GET", "POST"])
def wa_webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == tgwacombot.get_wa_verify_token():
            response = make_response(request.args.get("hub.challenge"), 200)
            response.mimetype = "text/plain"
            return response
    producer_launch(request, 'whatsapp')
    return ''


# ТЕЛЕГРАМ
@app.route("/t", methods=["POST"])
def tg_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = tb_types.Update.de_json(json_string)
        tgwacombot.telegram_bot.process_new_updates([update])
        producer_launch(request, 'telegram')
    else:
        abort(403)
    return ''


if __name__ == "__main__":
    if tgwacombot.check_env_variables():
        tgwacombot.setup()
        launch_consumers()
        app.run(port=5000, debug=True, use_reloader=False)
    else:
        log_error(f"Not all environment variables are declared correctly in the file: {filename}")