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

# Default generation options
DEFAULT_GEN_OPTIONS = {
    'temperature': 0.5,
    'top_p': 0.9,
    'max_tokens': 256,
}

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

    # Button command: sends an inline keyboard with a single 'Get Reply' button
    @restricted
    def send_button(update: Update, context: CallbackContext):
        keyboard = [[InlineKeyboardButton('Reply', callback_data='get_reply')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Press the button to receive a reply:', reply_markup=reply_markup)

    # Settings: view and adjust generation parameters
    def _format_options_text(opts: dict) -> str:
        return (f"Generation options:\n"
                f"Temperature: {opts['temperature']}\n"
                f"Top-p: {opts['top_p']}\n"
                f"Max tokens: {opts['max_tokens']}")

    @restricted
    def settings_command(update: Update, context: CallbackContext):
        # ensure persistence key exists
        opts = context.bot_data.setdefault('generation_options', DEFAULT_GEN_OPTIONS.copy())

        keyboard = [
            [InlineKeyboardButton('Temp -', callback_data='opt:temperature:-'), InlineKeyboardButton('Temp +', callback_data='opt:temperature:+')],
            [InlineKeyboardButton('Top-p -', callback_data='opt:top_p:-'), InlineKeyboardButton('Top-p +', callback_data='opt:top_p:+')],
            [InlineKeyboardButton('Max tokens -', callback_data='opt:max_tokens:-'), InlineKeyboardButton('Max tokens +', callback_data='opt:max_tokens:+')],
            [InlineKeyboardButton('Reset', callback_data='opt:reset'), InlineKeyboardButton('Done', callback_data='opt:done')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(_format_options_text(opts), reply_markup=reply_markup)

    @restricted
    def settings_callback(update: Update, context: CallbackContext):
        query = update.callback_query
        if not query:
            return
        query.answer()

        data = query.data or ''
        opts = context.bot_data.setdefault('generation_options', DEFAULT_GEN_OPTIONS.copy())

        if data == 'opt:done':
            query.message.reply_text('Settings saved.')
            return

        if data == 'opt:reset':
            context.bot_data['generation_options'] = DEFAULT_GEN_OPTIONS.copy()
            opts = context.bot_data['generation_options']
            query.edit_message_text(_format_options_text(opts))
            return

        # data format: opt:<key>:+ or -
        parts = data.split(':')
        if len(parts) == 3 and parts[0] == 'opt':
            key = parts[1]
            action = parts[2]

            # increment/decrement rules
            if key == 'temperature':
                step = 0.1
                new = round(max(0.0, min(2.0, opts.get('temperature', DEFAULT_GEN_OPTIONS['temperature']) + (step if action == '+' else -step))), 2)
                opts['temperature'] = new
            elif key == 'top_p':
                step = 0.05
                new = round(max(0.0, min(1.0, opts.get('top_p', DEFAULT_GEN_OPTIONS['top_p']) + (step if action == '+' else -step))), 2)
                opts['top_p'] = new
            elif key == 'max_tokens':
                step = 16
                new = int(max(1, min(2048, opts.get('max_tokens', DEFAULT_GEN_OPTIONS['max_tokens']) + (step if action == '+' else -step))))
                opts['max_tokens'] = new

            # persist
            context.bot_data['generation_options'] = opts

            # update message text with new values
            try:
                query.edit_message_text(_format_options_text(opts), reply_markup=query.message.reply_markup)
            except Exception:
                # fallback: send new message
                query.message.reply_text(_format_options_text(opts))


    # Callback for the inline button. Picks a random payload and replies using the model.
    @restricted
    def button_callback(update: Update, context: CallbackContext):
        query = update.callback_query
        if not query:
            return
        # Acknowledge the callback to remove the loading state in the client
        query.answer()

        # Generate reply using current generation options (if supported)
        payload = random.choice(payloads_list)
        gen_opts = context.bot_data.get('generation_options', DEFAULT_GEN_OPTIONS)
        try:
            # prefer passing options if gpt.get_payload accepts them
            reply = gpt.get_payload(payload, **gen_opts)
        except TypeError:
            # fallback if model method doesn't accept options
            reply = gpt.get_payload(payload)

        # Send the generated reply in the same chat
        query.message.reply_text(f'{payload} {reply}')

    # Register the new handlers
    _handlers['button_handler'] = CommandHandler('button', send_button)
    _handlers['callback_query_handler'] = CallbackQueryHandler(button_callback, pattern='^get_reply$')
    _handlers['settings_handler'] = CommandHandler('settings', settings_command)
    _handlers['settings_callback_handler'] = CallbackQueryHandler(settings_callback, pattern='^opt:')

    for name, _handler in _handlers.items():
        # avoid adding duplicates if handlers were already added above
        if _handler not in dispatcher.handlers.get(0, []):
            print(f'Adding handler {name}')
            dispatcher.add_handler(_handler)

    updater.start_polling()

    updater.idle()