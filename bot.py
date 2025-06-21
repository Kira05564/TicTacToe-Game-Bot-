import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    MessageHandler,
    filters
)
import random
from enum import Enum
import sqlite3
import time

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot credentials
BOT_TOKEN = "8077709311:AAHF_PUkz-vydeXzdEja59WftqfutqEpgYM"
OWNER_ID = 7841882010
GROUP_LINK = "https://t.me/+nCPKGZFJlbkzZjM1"

# Initialize database
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT)''')
    conn.commit()
    conn.close()

init_db()

class GameMode(Enum):
    BOT_EASY = 1
    BOT_MEDIUM = 2
    BOT_HARD = 3
    PLAYER_VS_PLAYER = 4

class Player(Enum):
    X = "❌"
    O = "⭕"
    EMPTY = " "

class Game:
    def __init__(self, mode, player1_id=None, player2_id=None):
        self.board = [[Player.EMPTY for _ in range(3)] for _ in range(3)]
        self.current_player = Player.X
        self.mode = mode
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.winner = None
        self.game_over = False
        self.last_update_time = time.time()

    def make_move(self, row, col):
        if self.game_over or self.board[row][col] != Player.EMPTY:
            return False

        self.board[row][col] = self.current_player
        self.last_update_time = time.time()

        if self.check_winner(self.current_player):
            self.winner = self.current_player
            self.game_over = True
        elif self.is_board_full():
            self.game_over = True
        else:
            self.switch_player()

        return True

    def switch_player(self):
        self.current_player = Player.O if self.current_player == Player.X else Player.X

    def check_winner(self, player):
        # Check rows
        for row in self.board:
            if all(cell == player for cell in row):
                return True

        # Check columns
        for col in range(3):
            if all(self.board[row][col] == player for row in range(3)):
                return True

        # Check diagonals
        if all(self.board[i][i] == player for i in range(3)):
            return True
        if all(self.board[i][2-i] == player for i in range(3)):
            return True

        return False

    def is_board_full(self):
        return all(cell != Player.EMPTY for row in self.board for cell in row)

    def get_bot_move(self, difficulty):
        empty_cells = [(i, j) for i in range(3) for j in range(3) if self.board[i][j] == Player.EMPTY]
        
        if difficulty == GameMode.BOT_EASY:
            return random.choice(empty_cells) if empty_cells else (None, None)
        
        if difficulty == GameMode.BOT_MEDIUM and random.random() > 0.5:
            for i, j in empty_cells:
                temp_board = [row.copy() for row in self.board]
                temp_board[i][j] = self.current_player
                if self.check_winner(self.current_player):
                    return (i, j)
            
            opponent = Player.O if self.current_player == Player.X else Player.X
            for i, j in empty_cells:
                temp_board = [row.copy() for row in self.board]
                temp_board[i][j] = opponent
                if self.check_winner(opponent):
                    return (i, j)
        
        if difficulty == GameMode.BOT_HARD:
            best_score = -float('inf')
            best_move = None
            
            for i, j in empty_cells:
                self.board[i][j] = self.current_player
                score = self.minimax(False)
                self.board[i][j] = Player.EMPTY
                
                if score > best_score:
                    best_score = score
                    best_move = (i, j)
            
            return best_move if best_move else random.choice(empty_cells)
        
        return random.choice(empty_cells) if empty_cells else (None, None)

    def minimax(self, is_maximizing):
        if self.check_winner(Player.X):
            return 1
        if self.check_winner(Player.O):
            return -1
        if self.is_board_full():
            return 0

        if is_maximizing:
            best_score = -float('inf')
            for i in range(3):
                for j in range(3):
                    if self.board[i][j] == Player.EMPTY:
                        self.board[i][j] = Player.X
                        score = self.minimax(False)
                        self.board[i][j] = Player.EMPTY
                        best_score = max(score, best_score)
            return best_score
        else:
            best_score = float('inf')
            for i in range(3):
                for j in range(3):
                    if self.board[i][j] == Player.EMPTY:
                        self.board[i][j] = Player.O
                        score = self.minimax(True)
                        self.board[i][j] = Player.EMPTY
                        best_score = min(score, best_score)
            return best_score

active_games = {}

def add_user(user_id, username=None):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", (user_id, username))
        conn.commit()
    finally:
        conn.close()

def get_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute("SELECT user_id FROM users")
        return [row[0] for row in c.fetchall()]
    finally:
        conn.close()

def start(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if query:
        chat_id = query.message.chat_id
        user = query.from_user
        query.answer()
    else:
        chat_id = update.message.chat_id
        user = update.effective_user
    
    add_user(user.id, user.username)
    
    # Clear any existing game in this chat
    if chat_id in active_games:
        del active_games[chat_id]
    
    keyboard = [
        [
            InlineKeyboardButton("Bot vs Player", callback_data='mode_bot'),
            InlineKeyboardButton("Player vs Player", callback_data='mode_pvp'),
        ],
        [InlineKeyboardButton("Help", callback_data='help')],
        [InlineKeyboardButton("About", callback_data='about')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        try:
            query.edit_message_text(
                text=f"Hi {user.first_name}! Welcome to Tic Tac Toe Bot!\n\nChoose a game mode:",
                reply_markup=reply_markup,
            )
        except:
            pass
    else:
        update.message.reply_text(
            f"Hi {user.first_name}! Welcome to Tic Tac Toe Bot!\n\nChoose a game mode:",
            reply_markup=reply_markup,
        )

def help_command(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if query:
        query.answer()
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        
        keyboard = [[InlineKeyboardButton("Back", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    "🤖 *Tic Tac Toe Bot Help* 🤖\n\n"
                    "🔹 /start - Start the bot\n"
                    "🔹 /help - Show this help message\n"
                    "🔹 /about - About the bot and developer\n"
                    "🔹 /broadcast - Owner only: Send message to all users\n\n"
                    "*Game Modes:*\n"
                    "1. 🤖 Bot vs Player - Play against AI (choose difficulty)\n"
                    "2. 👥 Player vs Player - Play with a friend\n\n"
                    "Use the buttons to navigate and play the game!"
                ),
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except:
            pass
    else:
        update.message.reply_text(
            "🤖 *Tic Tac Toe Bot Help* 🤖\n\n"
            "🔹 /start - Start the bot\n"
            "🔹 /help - Show this help message\n"
            "🔹 /about - About the bot and developer\n"
            "🔹 /broadcast - Owner only: Send message to all users\n\n"
            "*Game Modes:*\n"
            "1. 🤖 Bot vs Player - Play against AI (choose difficulty)\n"
            "2. 👥 Player vs Player - Play with a friend\n\n"
            "Use the buttons to navigate and play the game!",
            parse_mode='Markdown'
        )

def about(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if query:
        query.answer()
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        
        keyboard = [
            [
                InlineKeyboardButton("Join Group", url=GROUP_LINK),
                InlineKeyboardButton("Contact Owner", url=f"tg://user?id={OWNER_ID}"),
            ],
            [InlineKeyboardButton("Back", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    "🎮 *Tic Tac Toe Bot* 🎮\n\n"
                    "A fun Tic Tac Toe game for Telegram!\n\n"
                    "Developed by @Titan_hunter_Levi\n"
                    "Version: 1.0\n\n"
                    "Join our group for updates and support!"
                ),
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except:
            pass
    else:
        keyboard = [
            [
                InlineKeyboardButton("Join Group", url=GROUP_LINK),
                InlineKeyboardButton("Contact Owner", url=f"tg://user?id={OWNER_ID}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "🎮 *Tic Tac Toe Bot* 🎮\n\n"
            "A fun Tic Tac Toe game for Telegram!\n\n"
            "Developed by @Titan_hunter_Levi\n"
            "Version: 1.0\n\n"
            "Join our group for updates and support!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

def broadcast(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != OWNER_ID:
        update.message.reply_text("⚠️ You are not authorized to use this command!")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    all_users = get_all_users()
    success = 0
    failed = 0
    
    update.message.reply_text(f"Starting broadcast to {len(all_users)} users...")
    
    for user_id in all_users:
        try:
            context.bot.send_message(
                chat_id=user_id,
                text=f"📢 Broadcast from Admin:\n\n{message}"
            )
            success += 1
            time.sleep(0.1)  # To avoid rate limiting
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            failed += 1
    
    update.message.reply_text(
        f"📢 Broadcast Results:\n"
        f"Total users: {len(all_users)}\n"
        f"Success: {success}\n"
        f"Failed: {failed}"
    )

def choose_difficulty(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton("Easy", callback_data='diff_easy'),
            InlineKeyboardButton("Medium", callback_data='diff_medium'),
        ],
        [InlineKeyboardButton("Hard", callback_data='diff_hard')],
        [InlineKeyboardButton("Back", callback_data='back')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        query.edit_message_text(
            text="Choose difficulty level:",
            reply_markup=reply_markup,
        )
    except:
        pass

def start_game(update: Update, context: CallbackContext, mode: GameMode) -> None:
    query = update.callback_query
    query.answer()
    
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    if chat_id in active_games:
        try:
            query.edit_message_text(
                text="There's already an active game in this chat! Please finish it first.",
            )
        except:
            pass
        return
    
    if mode in [GameMode.BOT_EASY, GameMode.BOT_MEDIUM, GameMode.BOT_HARD]:
        active_games[chat_id] = Game(mode, player1_id=user_id)
        text = f"Game started! You're playing against the bot as {Player.X.value}\n\n"
    else:
        active_games[chat_id] = Game(mode, player1_id=user_id)
        text = "Game started! Waiting for another player to join...\n\n"
    
    text += get_board_text(active_games[chat_id])
    
    try:
        query.edit_message_text(
            text=text,
            reply_markup=get_board_markup(active_games[chat_id], query),
        )
    except Exception as e:
        logger.error(f"Error in start_game: {e}")

def get_board_text(game):
    board_text = ""
    for row in game.board:
        board_text += " | ".join(cell.value for cell in row) + "\n"
        board_text += "---------\n"
    
    if game.mode == GameMode.PLAYER_VS_PLAYER and not game.player2_id:
        board_text += "\nWaiting for second player to join..."
    elif not game.game_over:
        board_text += f"\nCurrent turn: {game.current_player.value}"
    else:
        if game.winner:
            board_text += f"\n🎉 {game.winner.value} wins!"
        else:
            board_text += "\n🤝 It's a draw!"
    
    return board_text

def get_board_markup(game, query):
    keyboard = []
    for i in range(3):
        row = []
        for j in range(3):
            cell = game.board[i][j]
            if cell == Player.EMPTY and not game.game_over:
                if (game.mode == GameMode.PLAYER_VS_PLAYER and 
                    ((game.current_player == Player.X and game.player1_id == query.from_user.id) or 
                     (game.current_player == Player.O and game.player2_id == query.from_user.id))):
                    row.append(InlineKeyboardButton(" ", callback_data=f'move_{i}_{j}'))
                elif game.mode != GameMode.PLAYER_VS_PLAYER and game.player1_id == query.from_user.id:
                    row.append(InlineKeyboardButton(" ", callback_data=f'move_{i}_{j}'))
                else:
                    row.append(InlineKeyboardButton(" ", callback_data=' '))
            else:
                row.append(InlineKeyboardButton(cell.value, callback_data=' '))
        keyboard.append(row)
    
    if game.game_over:
        keyboard.append([InlineKeyboardButton("New Game", callback_data='new_game')])
    elif game.mode == GameMode.PLAYER_VS_PLAYER and not game.player2_id:
        keyboard.append([InlineKeyboardButton("Join Game", callback_data='join_game')])
    
    return InlineKeyboardMarkup(keyboard)

def button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    if query.data == 'mode_bot':
        choose_difficulty(update, context)
    elif query.data == 'mode_pvp':
        start_game(update, context, GameMode.PLAYER_VS_PLAYER)
    elif query.data == 'help':
        help_command(update, context)
    elif query.data == 'about':
        about(update, context)
    elif query.data == 'back' or query.data == 'new_game':
        # Clear any existing game when going back
        if query.message.chat_id in active_games:
            del active_games[query.message.chat_id]
        start(update, context)
    elif query.data.startswith('diff_'):
        if query.data == 'diff_easy':
            mode = GameMode.BOT_EASY
        elif query.data == 'diff_medium':
            mode = GameMode.BOT_MEDIUM
        else:
            mode = GameMode.BOT_HARD
        start_game(update, context, mode)
    elif query.data == 'join_game' and query.message.chat_id in active_games:
        game = active_games[query.message.chat_id]
        if game.mode == GameMode.PLAYER_VS_PLAYER and not game.player2_id:
            game.player2_id = query.from_user.id
            try:
                query.edit_message_text(
                    text=f"Player 2 has joined! {Player.X.value} goes first.\n\n{get_board_text(game)}",
                    reply_markup=get_board_markup(game, query),
                )
            except:
                pass
    elif query.data.startswith('move_') and query.message.chat_id in active_games:
        game = active_games[query.message.chat_id]
        
        if (game.mode == GameMode.PLAYER_VS_PLAYER and 
            ((game.current_player == Player.X and game.player1_id != query.from_user.id) or 
             (game.current_player == Player.O and game.player2_id != query.from_user.id))):
            query.answer("It's not your turn!", show_alert=True)
            return
        
        if game.mode != GameMode.PLAYER_VS_PLAYER and game.player1_id != query.from_user.id:
            query.answer("You're not in this game!", show_alert=True)
            return
        
        if game.game_over:
            query.answer("Game is already over!", show_alert=True)
            return
        
        _, i, j = query.data.split('_')
        i, j = int(i), int(j)
        
        if game.make_move(i, j):
            text = get_board_text(game)
            reply_markup = get_board_markup(game, query)
            
            if (not game.game_over and 
                game.mode in [GameMode.BOT_EASY, GameMode.BOT_MEDIUM, GameMode.BOT_HARD]):
                bot_i, bot_j = game.get_bot_move(game.mode)
                if bot_i is not None and bot_j is not None:
                    game.make_move(bot_i, bot_j)
                    text = get_board_text(game)
                    reply_markup = get_board_markup(game, query)
            
            try:
                query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                )
            except:
                pass
        else:
            query.answer("Invalid move!", show_alert=True)

def error_handler(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update.callback_query:
        update.callback_query.answer("An error occurred. Please try again.", show_alert=True)

def main() -> None:
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("about", about))
    dispatcher.add_handler(CommandHandler("broadcast", broadcast))
    dispatcher.add_handler(CallbackQueryHandler(button_click))
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()