# <h1 align="center"> wtcombot</h1>
This repository offers a program for a WhatsApp-bot communicating with a Telegram-bot. The program allows you to exchange messages with different types of content between two messengers. 
 
## How it works ##
The WhatsApp-bot receives a message from the WhatsApp-user and sends it to the Telegram group chat using the Telegram-bot. Telegram-bot adds a postscript to each message from WhatsApp, which contains a number and a link to the user’s WhatsApp profile. If group members reply to a message from the Telegram-bot, it automatically sends a reply message to the WhatsApp-user using WhatsApp-bot. The WhatsApp-bot knows which WhatsApp-user each message from the Telegram group chat belongs to, because all messages are being signed. 
 
For the beginning you need:
1. to create and connect a Telegram-bot to a Telegram group-chat. 
2. to create a WhatsApp Business Cloud API (link) in order to make a WhatsApp-bot. 
<a href="https://developers.facebook.com/docs/whatsapp/cloud-api" target="_blank">Here</a> you can find a way to test if your WhatsApp-bot is working right.  

After all the settings, you should have the following variables of your environment: 

<b>Telegram</b> 
1. Token for access HTTP API. 
2. Bot ID 
3. Group chat ID 

<b>WhatsApp</b> 
1. Token for access HTTP API. 
2. Verify token 
3. Number ID 

As an example, you can look at the attached file «WT_COMBOT_ENVFILE.env» with environment variables. 

This program is using an open <a href="https://github.com/eternnoir/pyTelegramBotAPI" target="_blank">Python implementation</a> for the Telegram Bot API and an open <a href="https://github.com/Neurotech-HQ/heyoo" target="_blank">Python wrapper</a> to WhatsApp Cloud API.  

To test communication of two messengers, you can use <a href="https://ngrok.com/" target="_blank">ngrok</a>.
