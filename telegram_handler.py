from functools import wraps
import logging
import random
from telegram.ext.filters import Filters
from telegram.ext.messagehandler import MessageHandler
from settings import BOT_TOKEN, USER_ID
from telegram import Update
from telegram.ext import (Updater,
                          PicklePersistence,
                          CommandHandler,
                          CallbackQueryHandler,
                          CallbackContext,
                          ConversationHandler)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply

from Models.gpt_j_6b import gpt_j_6B
from time import sleep
from pdf_reader import Text_Provider

print('Extracting text from PDF...')
tp = Text_Provider()
payloads_list = tp.get_payloads()
random.shuffle(payloads_list)

EXPECT_NAME, EXPECT_BUTTON_CLICK = range(2)
NUMEXPR_MAX_THREADS = 12
LIST_OF_ADMINS = [USER_ID]
gpt = gpt_j_6B()

def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)
    return wrapped

@restricted
def start(update: Update, context: CallbackContext):
    ''' Replies to /start command '''
    update.message.reply_text('Initializing...')
    payloads_count = 0

    while True:
        try:
            payload = payloads_list[payloads_count]
            reply = gpt.get_payload(payload)
            update.message.reply_text(f'{payload} {reply}')
            sleep(random.uniform(7.*60, 13.*60))
        except KeyboardInterrupt:
            break

        payloads_count += 1

        if payloads_count == payloads_list.index(payload):
            payloads_count = 0
        
    return ConversationHandler.END

if __name__ == "__main__":
    pp = PicklePersistence(filename='mybot')
    updater = Updater(token=BOT_TOKEN, persistence=pp)

    dispatcher = updater.dispatcher

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    _handlers = {}
    _handlers['start_handler'] = CommandHandler('start', start)

    for name, _handler in _handlers.items():
        print(f'Adding handler {name}')
        dispatcher.add_handler(_handler)

    updater.start_polling()

    updater.idle()