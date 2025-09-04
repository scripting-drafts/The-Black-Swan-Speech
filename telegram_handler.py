from functools import wraps
import logging
import random
import threading
import time
import sys
import os

# Set NumExpr thread limit before any imports that might use it
os.environ['NUMEXPR_MAX_THREADS'] = '12'

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

# Global variable to control bot shutdown
bot_should_restart = False

def restart_timer():
    """Timer function to restart the bot every 8 hours"""
    global bot_should_restart
    print("Restart timer started - bot will restart in 8 hours")
    time.sleep(6 * 60 * 60)  # 8 hours in seconds
    print("8 hours elapsed - scheduling bot restart...")
    bot_should_restart = True

def restart_bot():
    """Restart the bot by re-executing the script"""
    print("Restarting bot...")
    os.execv(sys.executable, ['python'] + sys.argv)

print('Extracting text from PDF...')
tp = Text_Provider()
payloads_list = tp.get_payloads()
random.shuffle(payloads_list)

EXPECT_NAME, EXPECT_BUTTON_CLICK = range(2)
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
    global bot_should_restart
    
    # Show the main keyboard immediately
    keyboard = [
        [InlineKeyboardButton('Get Reply', callback_data='get_reply')],
        [InlineKeyboardButton('Settings', callback_data='show_settings')],
        [InlineKeyboardButton('Start Auto Posts', callback_data='start_auto')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('🦢 Welcome to The Black Swan Bot!\n\nChoose an option:', reply_markup=reply_markup)
    
    return ConversationHandler.END

@restricted
def auto_post_handler(update: Update, context: CallbackContext):
    ''' Handles automatic posting '''
    global bot_should_restart
    update.message.reply_text('Starting automatic posts...')
    payloads_count = 0

    while True:
        try:
            # Check if bot should restart
            if bot_should_restart:
                update.message.reply_text('Bot is restarting for maintenance...')
                break
                
            payload = payloads_list[payloads_count]
            gen_opts = context.bot_data.get('generation_options', DEFAULT_GEN_OPTIONS)
            try:
                reply = gpt.get_payload(payload, **gen_opts)
            except TypeError:
                reply = gpt.get_payload(payload)
            
            # Show keyboard again after each post
            keyboard = [
                [InlineKeyboardButton('Get Reply', callback_data='get_reply')],
                [InlineKeyboardButton('Settings', callback_data='show_settings')],
                [InlineKeyboardButton('Stop Auto Posts', callback_data='stop_auto')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(f'{payload}\n\n{reply}', reply_markup=reply_markup)
            
            sleep(random.uniform(7.*60, 13.*60))
        except KeyboardInterrupt:
            break

        payloads_count += 1
        if payloads_count == len(payloads_list):
            payloads_count = 0
        
    return ConversationHandler.END

if __name__ == "__main__":
    # Start the restart timer in a separate thread
    restart_thread = threading.Thread(target=restart_timer, daemon=True)
    restart_thread.start()
    
    pp = PicklePersistence(filename='mybot')
    updater = Updater(token=BOT_TOKEN, persistence=pp)

    dispatcher = updater.dispatcher

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    _handlers = {}
    _handlers['start_handler'] = CommandHandler('start', start)

    # Message handler to show keyboard for any text message
    @restricted
    def handle_message(update: Update, context: CallbackContext):
        keyboard = [
            [InlineKeyboardButton('Get Reply', callback_data='get_reply')],
            [InlineKeyboardButton('Settings', callback_data='show_settings')],
            [InlineKeyboardButton('Start Auto Posts', callback_data='start_auto')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('🦢 The Black Swan Bot\n\nChoose an option:', reply_markup=reply_markup)

    # Add message handler for any text
    _handlers['message_handler'] = MessageHandler(Filters.text & ~Filters.command, handle_message)

    # Button command: sends an inline keyboard with a single 'Get Reply' button
    @restricted
    def send_button(update: Update, context: CallbackContext):
        keyboard = [[InlineKeyboardButton('Reply', callback_data='get_reply')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Press the button to receive a reply:', reply_markup=reply_markup)

    # Add the button handler
    _handlers['button_handler'] = CommandHandler('button', send_button)

    for name, _handler in _handlers.items():
        print(f'Adding handler {name}')
        dispatcher.add_handler(_handler)

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
            keyboard = [
                [InlineKeyboardButton('Get Reply', callback_data='get_reply')],
                [InlineKeyboardButton('Settings', callback_data='show_settings')],
                [InlineKeyboardButton('Start Auto Posts', callback_data='start_auto')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text('🦢 The Black Swan Bot\n\nChoose an option:', reply_markup=reply_markup)
            return

        if data == 'opt:reset':
            context.bot_data['generation_options'] = DEFAULT_GEN_OPTIONS.copy()
            opts = context.bot_data['generation_options']
            keyboard = [
                [InlineKeyboardButton('Temp -', callback_data='opt:temperature:-'), InlineKeyboardButton('Temp +', callback_data='opt:temperature:+')],
                [InlineKeyboardButton('Top-p -', callback_data='opt:top_p:-'), InlineKeyboardButton('Top-p +', callback_data='opt:top_p:+')],
                [InlineKeyboardButton('Max tokens -', callback_data='opt:max_tokens:-'), InlineKeyboardButton('Max tokens +', callback_data='opt:max_tokens:+')],
                [InlineKeyboardButton('Reset', callback_data='opt:reset'), InlineKeyboardButton('Back', callback_data='back_to_main')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(_format_options_text(opts), reply_markup=reply_markup)
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
            keyboard = [
                [InlineKeyboardButton('Temp -', callback_data='opt:temperature:-'), InlineKeyboardButton('Temp +', callback_data='opt:temperature:+')],
                [InlineKeyboardButton('Top-p -', callback_data='opt:top_p:-'), InlineKeyboardButton('Top-p +', callback_data='opt:top_p:+')],
                [InlineKeyboardButton('Max tokens -', callback_data='opt:max_tokens:-'), InlineKeyboardButton('Max tokens +', callback_data='opt:max_tokens:+')],
                [InlineKeyboardButton('Reset', callback_data='opt:reset'), InlineKeyboardButton('Back', callback_data='back_to_main')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                query.edit_message_text(_format_options_text(opts), reply_markup=reply_markup)
            except Exception:
                # fallback: send new message
                query.message.reply_text(_format_options_text(opts), reply_markup=reply_markup)


    # Callback for the inline button. Picks a random payload and replies using the model.
    @restricted
    def button_callback(update: Update, context: CallbackContext):
        query = update.callback_query
        if not query:
            return
        # Acknowledge the callback to remove the loading state in the client
        query.answer()

        data = query.data
        
        if data == 'get_reply':
            # Generate reply using current generation options
            payload = random.choice(payloads_list)
            gen_opts = context.bot_data.get('generation_options', DEFAULT_GEN_OPTIONS)
            try:
                reply = gpt.get_payload(payload, **gen_opts)
            except TypeError:
                reply = gpt.get_payload(payload)

            # Show keyboard again after reply
            keyboard = [
                [InlineKeyboardButton('Get Reply', callback_data='get_reply')],
                [InlineKeyboardButton('Settings', callback_data='show_settings')],
                [InlineKeyboardButton('Start Auto Posts', callback_data='start_auto')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.message.reply_text(f'{payload}\n\n{reply}', reply_markup=reply_markup)
            
        elif data == 'show_settings':
            # Show settings keyboard
            opts = context.bot_data.setdefault('generation_options', DEFAULT_GEN_OPTIONS.copy())
            keyboard = [
                [InlineKeyboardButton('Temp -', callback_data='opt:temperature:-'), InlineKeyboardButton('Temp +', callback_data='opt:temperature:+')],
                [InlineKeyboardButton('Top-p -', callback_data='opt:top_p:-'), InlineKeyboardButton('Top-p +', callback_data='opt:top_p:+')],
                [InlineKeyboardButton('Max tokens -', callback_data='opt:max_tokens:-'), InlineKeyboardButton('Max tokens +', callback_data='opt:max_tokens:+')],
                [InlineKeyboardButton('Reset', callback_data='opt:reset'), InlineKeyboardButton('Back', callback_data='back_to_main')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text(_format_options_text(opts), reply_markup=reply_markup)
            
        elif data == 'start_auto':
            query.message.reply_text('Starting automatic posts... Send any message to stop.')
            auto_post_handler(query, context)
            
        elif data == 'back_to_main':
            keyboard = [
                [InlineKeyboardButton('Get Reply', callback_data='get_reply')],
                [InlineKeyboardButton('Settings', callback_data='show_settings')],
                [InlineKeyboardButton('Start Auto Posts', callback_data='start_auto')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_text('🦢 The Black Swan Bot\n\nChoose an option:', reply_markup=reply_markup)

    # Register the remaining handlers
    dispatcher.add_handler(CallbackQueryHandler(button_callback, pattern='^(get_reply|show_settings|start_auto|back_to_main)$'))
    dispatcher.add_handler(CommandHandler('settings', settings_command))
    dispatcher.add_handler(CallbackQueryHandler(settings_callback, pattern='^opt:'))

    updater.start_polling()

    # Monitor for restart condition
    try:
        while not bot_should_restart:
            time.sleep(1)  # Check every second
        
        print("Restart condition detected - stopping bot...")
        updater.stop()
        restart_bot()
        
    except KeyboardInterrupt:
        print("Bot stopped by user")
        updater.stop()
    
    updater.idle()