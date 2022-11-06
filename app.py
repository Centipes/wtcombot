import logging
from sys import argv
from flask import Flask, request, make_response, abort

from wtcombot.wtcombot import TGWACOM
from dotenv import load_dotenv

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
        # test_wa_init()
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

if tgwacombot.check_env_variables():
    tgwacombot.setup()
else:
    logging.error(f"Not all environment variables are declared correctly in the file {filename}")

if __name__ == "__main__":
    filename = argv[1] if len(argv) == 2 else '.env'
    load_dotenv(filename)
    app.run(port=5000, debug=True)
