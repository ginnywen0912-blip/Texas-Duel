import pygame
import random
import sys
import itertools
import os
import time
import textwrap

pygame.init()


# Game window and basic configuration
WIDTH, HEIGHT = 1000, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("1v1 Texas Duel")

# Font and color definitions
font_big = pygame.font.SysFont("PingFang SC", 42)
font_mid = pygame.font.SysFont("PingFang SC", 28)
font_small = pygame.font.SysFont("PingFang SC", 22)

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (20, 120, 20)
RED = (220, 50, 50)
GRAY = (180, 180, 180)
YELLOW = (255, 210, 0)

CARD_W, CARD_H = 70, 100
CARD_GAP = 12


# Load the icon
def load_icon(name):
    path = os.path.join(os.path.dirname(__file__), name)
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(img, (20, 20))

SUIT_ICONS = {
    '♠': load_icon("spade.png"),
    '♥': load_icon("heart.png"),
    '♦': load_icon("diamond.png"),
    '♣': load_icon("club.png"),
}

SUITS = list(SUIT_ICONS.keys())
RANKS = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
RANK_VALUE = {r:i for i,r in enumerate(RANKS, start=2)}
VALUE_TO_RANK = {v:r for r,v in RANK_VALUE.items()}


# Card and card type evaluation module
class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
    def __str__(self):
        return f"{self.rank}{self.suit}"
    @property
    def value(self):
        return RANK_VALUE[self.rank]

class Deck:
    def __init__(self):
        self.cards = [Card(r, s) for s in SUITS for r in RANKS]
        random.shuffle(self.cards)
    def draw(self, n):
        return [self.cards.pop() for _ in range(n)]

def evaluate_best5(cards7):
    """Find the best 5-card combination from a set of 7 cards"""
    best = None
    for combo in itertools.combinations(cards7, 5):
        rank = evaluate5(list(combo))
        if best is None or rank > best:
            best = rank
    return best

def evaluate5(cards5):
    """Determines the shape of five cards and returns a tuple of weights"""
    ranks = sorted([c.value for c in cards5], reverse=True)
    counts = {v: ranks.count(v) for v in set(ranks)}
    is_flush = len(set(c.suit for c in cards5)) == 1
    uniq = sorted(set(ranks), reverse=True)
    is_straight = len(uniq) == 5 and max(uniq) - min(uniq) == 4
    if set([14,5,4,3,2]).issubset(set(ranks)):
        is_straight, top = True, 5
    else:
        top = max(uniq)
    by_count = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if is_flush and is_straight:
        return (8, top)
    if by_count[0][1] == 4:
        return (7, by_count[0][0])
    if by_count[0][1] == 3 and by_count[1][1] == 2:
        return (6, by_count[0][0], by_count[1][0])
    if is_flush:
        return (5, *sorted(ranks, reverse=True))
    if is_straight:
        return (4, top)
    if by_count[0][1] == 3:
        return (3, by_count[0][0])
    if by_count[0][1] == 2 and by_count[1][1] == 2:
        return (2, by_count[0][0], by_count[1][0])
    if by_count[0][1] == 2:
        return (1, by_count[0][0])
    return (0, *sorted(ranks, reverse=True))

def hand_rank_name(rank_tuple):
    category = rank_tuple[0]
    name_map = {
        8: "Straight Flush",
        7: "Four of a Kind",
        6: "Full House",
        5: "Flush",
        4: "Straight",
        3: "Three of a Kind",
        2: "Two Pair",
        1: "One Pair",
        0: "High Card"
    }
    main = VALUE_TO_RANK.get(rank_tuple[1], RANKS[0]) if len(rank_tuple) > 1 else RANKS[0]
    return f"{name_map.get(category, 'Unknown')} ({main}-high)"


class Player:
    def __init__(self, name, is_human=False):
        self.name = name
        self.is_human = is_human
        self.chips = 100
        self.hand = [] # Hand (2 cards)
        self.folded = False
        self.bet = 0
        self.total_bet_hand = 0


class Game:
    def __init__(self):
        # welcome → dice → playing → result
        self.state = "welcome"
        self.deck = Deck()
        self.p1 = Player("Player 1", True)
        self.p2 = Player("Computer", False)
        self.board = []# Public deck
        self.revealed = 0
        self.round = 1
        self.pot = 0
        self.current_bet = 0 # Current maximum bet amount
        self.first_player = 0 # 0=p1 1=p2
        self.winner_msg = "" # Settlement information
        self.p1_rank = "" # Player card type
        self.p2_rank = "" # Computer card type
        self.result_winner = None # Winner name
        self.result_net_gain = 0
        self.dice_p1 = 0
        self.dice_p2 = 0
        self.dice_ready = False
        self.dice_animating = False
        self.dice_timer = 0

        self.log = []
        self.rules_visible = False
        self.popup_msg = None
        self.popup_start = 0.0


    def roll_dice(self):
        """Dice were rolled to decide who would go first"""
        self.dice_p1 = random.randint(1,6)
        self.dice_p2 = random.randint(1,6)
        if self.dice_p1 == self.dice_p2:
            return False
        self.first_player = 0 if self.dice_p1 > self.dice_p2 else 1
        return True


    def new_hand(self):
        self.deck = Deck() # Two cards in each hand
        self.p1.hand = self.deck.draw(2)
        self.p2.hand = self.deck.draw(2)
        # 5 public cards
        self.board = self.deck.draw(5)
        # The first round exposes a card directly
        self.revealed = 1
        self.round = 1
        self.pot = 0
        self.current_bet = 0
        # reset the situation
        for p in [self.p1, self.p2]:
            p.folded = False
            p.bet = 0
            p.total_bet_hand = 0
        self.state = "playing"
        self.log.clear()
        starter = "Player 1" if self.first_player == 0 else "Computer"
        self.add_log(f"{starter} starts first")
        # If the computer is first, it will automatically perform a round of operation
        if self.first_player == 1:
            msg = self.cpu_action(first_turn=True)
            self.add_log(msg)
            if self.p2.folded:
                self.end_game_due_to_fold()


    def add_log(self, msg):
        """Add the action to the log"""
        self.log.append(msg)
        if len(self.log) > 20:
            self.log.pop(0)


    def cpu_action(self, first_turn=False):
        """Decide the action based on the current visible card strength"""
        cpu = self.p2
        if cpu.chips < 10:
            cpu.folded = True
            return "Computer folds (low chips)"

        #Calculate the currently visible card
        visible_cards = cpu.hand + self.board[:self.revealed]
        rank_tuple = evaluate_best5(visible_cards + [Card('2', '♠')] * (7 - len(visible_cards))) if len(
            visible_cards) < 5 else evaluate_best5(visible_cards)
        strength_score = rank_tuple[0]  # From 0 to 8, the larger the class, the stronger

        highcard_bonus = max(c.value for c in cpu.hand) / 14.0
        strength = strength_score + highcard_bonus
        # The higher the strength, the more inclined to raise or follow, and the weaker may abandon the card
        r = random.random()

        # Never discard a strong card (Flush or above)
        if strength >= 5.5:
            if r < 0.5:
                amt = random.choice([20, 30, 40])
                cpu.chips -= amt;
                self.pot += amt
                cpu.bet += amt;
                cpu.total_bet_hand += amt
                self.current_bet = max(self.current_bet, amt)
                return f"Computer raises {amt}"
            else:
                need = self.current_bet - cpu.bet
                if need > 0 and cpu.chips >= need:
                    cpu.chips -= need;
                    self.pot += need
                    cpu.bet += need;
                    cpu.total_bet_hand += need
                    return f"Computer calls {need}"
                return "Computer checks"

        elif 2.5 <= strength < 5.5:
            if r < 0.75:
                need = self.current_bet - cpu.bet
                if need > 0 and cpu.chips >= need:
                    cpu.chips -= need;
                    self.pot += need
                    cpu.bet += need;
                    cpu.total_bet_hand += need
                    return f"Computer calls {need}"
                else:
                    amt = random.choice([10, 20])
                    cpu.chips -= amt;
                    self.pot += amt
                    cpu.bet += amt;
                    cpu.total_bet_hand += amt
                    self.current_bet = max(self.current_bet, amt)
                    return f"Computer raises {amt}"
            else:
                cpu.folded = True
                return "Computer folds"

        else:
            if r < 0.15:
                amt = 10
                cpu.chips -= amt;
                self.pot += amt
                cpu.bet += amt;
                cpu.total_bet_hand += amt
                self.current_bet = max(self.current_bet, amt)
                return f"Computer bluff raises {amt}"
            elif r < 0.6:
                need = self.current_bet - cpu.bet
                if need > 0 and cpu.chips >= need:
                    cpu.chips -= need;
                    self.pot += need
                    cpu.bet += need;
                    cpu.total_bet_hand += need
                    return f"Computer cautiously calls {need}"
                return "Computer checks"
            else:
                cpu.folded = True
                return "Computer folds"


    def next_round(self):
        # The betting state is reset after each round
        self.round += 1
        self.current_bet = 0
        self.p1.bet = self.p2.bet = 0

        # If not all the public cards are turned over, a new card is turned over
        if self.revealed < 5:
            self.revealed += 1

        # If it is round 5 (all cards are turned over), go straight to the showdown
        if self.round > 5 or self.revealed >= 5:
            self.end_showdown()

    def evaluate_winner(self):
        h1 = evaluate_best5(self.p1.hand + self.board)
        h2 = evaluate_best5(self.p2.hand + self.board)
        h1n, h2n = hand_rank_name(h1), hand_rank_name(h2)
        if self.p1.folded:
            return self.p2, f"{self.p2.name} wins by fold!", h1n, h2n
        if self.p2.folded:
            return self.p1, f"{self.p1.name} wins by fold!", h1n, h2n
        if h1 > h2:
            return self.p1, f"{self.p1.name} WINS!", h1n, h2n
        elif h2 > h1:
            return self.p2, f"{self.p2.name} WINS!", h1n, h2n
        else:
            return None, "DRAW!", h1n, h2n


    def end_game_due_to_fold(self):
        self.revealed = 5
        self.state = "result"
        winner,msg,h1,h2 = self.evaluate_winner()
        if winner:
            self.result_winner = winner.name
            winner_total = winner.total_bet_hand
            self.result_net_gain = self.pot - winner_total
            winner.chips += self.pot
        self.winner_msg = msg
        self.p1_rank, self.p2_rank = h1, h2
        self.add_log(msg)


    def end_showdown(self):
        self.revealed = 5
        self.state = "result"
        winner,msg,h1,h2 = self.evaluate_winner()
        if winner:
            self.result_winner = winner.name
            winner_total = winner.total_bet_hand
            self.result_net_gain = self.pot - winner_total
            winner.chips += self.pot
        else:
            self.result_winner = None
            self.result_net_gain = 0
            self.p1.chips += self.pot // 2
            self.p2.chips += self.pot // 2
        self.winner_msg, self.p1_rank, self.p2_rank = msg, h1, h2
        self.add_log(msg)


def draw_text(text, font, color, x, y):
    screen.blit(font.render(text, True, color), (x, y))

def draw_card(x, y, card=None, hidden=False):
    pygame.draw.rect(screen, WHITE, (x, y, CARD_W, CARD_H), border_radius=8)
    pygame.draw.rect(screen, BLACK, (x, y, CARD_W, CARD_H), 2, border_radius=8)
    if hidden:
        pygame.draw.rect(screen, GRAY, (x+6, y+6, CARD_W-12, CARD_H-12))
        return
    if card:
        color = RED if card.suit in ['♥','♦'] else BLACK
        rank_surf = font_mid.render(card.rank, True, color)
        screen.blit(rank_surf, (x+25, y+10))
        screen.blit(SUIT_ICONS[card.suit], (x+25, y+50))

def draw_centered_cards(cards, y):
    n = len(cards)
    total_w = n * CARD_W + (n - 1) * CARD_GAP
    start_x = (WIDTH - total_w) // 2
    for i, c in enumerate(cards):
        draw_card(start_x + i * (CARD_W + CARD_GAP), y, c)

def draw_popup(msg):
    box_w, box_h = 420, 80
    rect = pygame.Rect((WIDTH - box_w)//2, 20, box_w, box_h)
    pygame.draw.rect(screen, (0,0,0), rect, border_radius=10)
    pygame.draw.rect(screen, (220,220,220), rect, 2, border_radius=10)
    draw_text(msg, font_mid, YELLOW, rect.x + 20, rect.y + 20)

def draw_rules_panel(game):
    btn_rect = pygame.Rect(WIDTH - 180, 20, 150, 35)
    pygame.draw.rect(screen, (40,40,40), btn_rect, border_radius=6)
    label = "Hide Rules" if game.rules_visible else "Show Rules"
    draw_text(label, font_small, WHITE, btn_rect.x + 10, btn_rect.y + 8)
    # The expanded state displays the list of rules
    if game.rules_visible:
        panel_rect = pygame.Rect(WIDTH - 250, 70, 240, 250)
        pygame.draw.rect(screen, (0,0,0,180), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (220,220,220), panel_rect, 2, border_radius=10)
        rules = [
            "1. Straight Flush",
            "2. Four of a Kind",
            "3. Full House",
            "4. Flush",
            "5. Straight",
            "6. Three of a Kind",
            "7. Two Pair",
            "8. One Pair",
            "9. High Card"
        ]
        for i, r in enumerate(rules):
            draw_text(r, font_small, YELLOW, panel_rect.x + 10, panel_rect.y + 10 + i * 25)
    return btn_rect

def draw_action_log(game):
    panel = pygame.Rect(730, 480, 250, 200)
    pygame.draw.rect(screen, (0,0,0), panel)
    draw_text("Action Log", font_small, YELLOW, 750, 485)
    for i, msg in enumerate(game.log[-6:]):  # 显示最近6条
        draw_text(msg, font_small, WHITE, 740, 510 + i * 28)

def draw_action_records(logs, x, y):
    p1_actions = [l for l in logs if "Player" in l]
    cpu_actions = [l for l in logs if "Computer" in l]
    all_text = ["Player Actions:"] + p1_actions + [""] + ["Computer Actions:"] + cpu_actions
    wrapped = []
    for t in all_text:
        wrapped += textwrap.wrap(t, width=25) if t else [""]
    panel = pygame.Rect(x, y, 230, 360)
    pygame.draw.rect(screen, (0,0,0,180), panel, border_radius=10)
    pygame.draw.rect(screen, (200,200,200), panel, 1, border_radius=10)
    for i, line in enumerate(wrapped[:18]):
        draw_text(line, font_small, WHITE, panel.x + 10, panel.y + 10 + i * 20)


def main():
    clock = pygame.time.Clock()
    game = Game()

    btns = {
        "check": pygame.Rect(50, 600, 100, 40),
        "raise": pygame.Rect(170, 600, 100, 40),
        "call": pygame.Rect(290, 600, 100, 40),
        "fold": pygame.Rect(410, 600, 100, 40),
    }

    result_panel = pygame.Rect(60, 40, 880, 620)
    continue_btn = pygame.Rect(result_panel.centerx - 130, result_panel.bottom - 55, 120, 40)
    quit_btn     = pygame.Rect(result_panel.centerx + 10,  result_panel.bottom - 55, 120, 40)


    while True:
        screen.fill(GREEN)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                rules_btn = draw_rules_panel(game)
                if rules_btn.collidepoint(mx,my):
                    game.rules_visible = not game.rules_visible

                # Welcome page
                if game.state == "welcome":
                    game.state = "dice"

                # dice page
                elif game.state == "dice":
                    if not game.dice_ready and not game.dice_animating:
                        game.dice_animating = True
                        game.dice_timer = pygame.time.get_ticks()
                    elif game.dice_ready:
                        if game.dice_p1 != game.dice_p2:
                            game.new_hand()
                            game.dice_ready = False
                        else:
                            game.dice_ready = False
                            game.dice_animating = False
                            game.dice_p1 = game.dice_p2 = 0

                elif game.state == "playing":
                    first_turn = (game.round==1 and game.first_player==0 and game.current_bet==0)
                    if btns["check"].collidepoint(mx, my):
                        # It can only be checked if no bets are currently placed
                        if game.current_bet == 0:
                            game.add_log("Player checks")
                            msg = game.cpu_action()
                            game.add_log(msg)
                            if game.p2.folded:
                                game.end_game_due_to_fold()
                            else:
                                game.next_round()

                    if btns["raise"].collidepoint(mx,my):
                        user_text=""; entering=True
                        while entering:
                            for ev in pygame.event.get():
                                if ev.type==pygame.KEYDOWN:
                                    if ev.key==pygame.K_RETURN: entering=False
                                    elif ev.key==pygame.K_BACKSPACE: user_text=user_text[:-1]
                                    elif ev.unicode.isdigit() and len(user_text)<3: user_text+=ev.unicode
                            screen.fill((0,0,0))
                            draw_text("Enter raise (10-100):", font_mid, YELLOW, 300, 300)
                            draw_text(user_text, font_mid, WHITE, 600, 300)
                            pygame.display.flip()
                        if user_text:
                            amt=int(user_text)
                            if 10<=amt<=100 and amt<=game.p1.chips:
                                game.p1.chips-=amt; game.pot+=amt; game.current_bet+=amt
                                game.p1.bet+=amt; game.p1.total_bet_hand+=amt
                                game.add_log(f"Player raises {amt}")
                                msg=game.cpu_action()
                                game.add_log(msg)
                                if game.p2.folded: game.end_game_due_to_fold()
                                else: game.next_round()
                    if btns["call"].collidepoint(mx, my) and not first_turn:
                        need = game.current_bet - game.p1.bet
                        if need <= 0:
                            game.add_log("Player checks")
                            msg = game.cpu_action()
                            game.add_log(msg)
                            if game.p2.folded:
                                game.end_game_due_to_fold()
                            else:
                                game.next_round()
                        elif game.p1.chips >= need:
                            game.p1.chips -= need
                            game.pot += need
                            game.p1.bet += need
                            game.p1.total_bet_hand += need
                            game.add_log(f"Player calls {need}")
                            msg = game.cpu_action()
                            game.add_log(msg)
                            if game.p2.folded:
                                game.end_game_due_to_fold()
                            else:
                                game.next_round()

                    if btns["fold"].collidepoint(mx,my):
                        game.p1.folded=True
                        game.end_game_due_to_fold()

                elif game.state == "result":
                    if continue_btn.collidepoint(mx,my):
                        if game.p1.chips < 10 or game.p2.chips < 10:
                            game.popup_msg = "某方筹码不足，已重置为100"
                            game.popup_start = time.time()
                            game.p1.chips = game.p2.chips = 100
                        game.state = "dice"  # new round
                    elif quit_btn.collidepoint(mx,my):
                        pygame.quit(); sys.exit()

        if game.state == "dice" and game.dice_animating:
            elapsed = pygame.time.get_ticks() - game.dice_timer
            if elapsed < 2000:
                if elapsed % 100 < 50:
                    game.dice_p1 = random.randint(1,6)
                    game.dice_p2 = random.randint(1,6)
            else:
                game.roll_dice()
                game.dice_animating = False
                game.dice_ready = True


        if game.state == "welcome":
            draw_text("Welcome to 1v1 Texas Duel", font_big, YELLOW, 240, 250)
            draw_text("Click anywhere to start", font_mid, WHITE, 360, 320)

        elif game.state == "dice":
            draw_text("Dice Roll to decide first player", font_big, YELLOW, 200, 150)
            if not game.dice_animating and not game.dice_ready:
                draw_text("Click to roll dice", font_mid, WHITE, 380, 240)
            elif game.dice_animating:
                draw_text("Rolling...", font_big, YELLOW, 420, 240)
                draw_text(f"{game.dice_p1} vs {game.dice_p2}", font_big, WHITE, 440, 320)
            elif game.dice_ready:
                draw_text(f"Player 1 Dice: {game.dice_p1}", font_mid, WHITE, 300, 320)
                draw_text(f"Computer Dice: {game.dice_p2}", font_mid, WHITE, 300, 360)
                if game.dice_p1==game.dice_p2:
                    draw_text("Same number! Roll again!", font_mid, RED, 300, 400)
                else:
                    first="Player 1" if game.first_player==0 else "Computer"
                    draw_text(f"{first} goes first!", font_mid, YELLOW, 300, 400)
                    draw_text("Click to start game", font_small, WHITE, 360, 440)

        else:
            draw_text(f"Pot: {game.pot}", font_mid, YELLOW, 50, 20)
            draw_text(f"P1 Chips: {game.p1.chips}", font_mid, WHITE, 50, 60)
            draw_text(f"CPU Chips: {game.p2.chips}", font_mid, WHITE, 50, 90)
            draw_text(f"Round: {game.round} / 5", font_mid, WHITE, 50, 130)

            for i, c in enumerate(game.board):
                draw_card(300 + i*(CARD_W+CARD_GAP), 250, c, hidden=(i >= game.revealed))
            for i, c in enumerate(game.p1.hand):
                draw_card(300 + i*(CARD_W+CARD_GAP), 450, c)
            for i, c in enumerate(game.p2.hand):
                draw_card(300 + i*(CARD_W+CARD_GAP), 100, c, hidden=(game.state != "result"))
            draw_action_log(game)
            draw_rules_panel(game)

            if game.state == "playing":
                first_turn=(game.round==1 and game.first_player==0 and game.current_bet==0)
                for key, rect in btns.items():
                    disabled = False
                    if key == "check" and game.current_bet > 0:
                        disabled = True
                    if key == "call" and (first_turn or game.current_bet == 0):
                        disabled = True

                    color = (80, 80, 80) if disabled else (50, 50, 50)
                    pygame.draw.rect(screen, color, rect, border_radius=6)
                    txt = font_small.render(key.upper(), True, WHITE)
                    screen.blit(txt, (rect.x + 20, rect.y + 8))


            elif game.state == "result":
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0,0,0,180))
                screen.blit(overlay, (0,0))
                pygame.draw.rect(screen, (20,20,20), result_panel, border_radius=12)
                pygame.draw.rect(screen, (200,200,200), result_panel, 2, border_radius=12)
                draw_text(game.winner_msg, font_big, YELLOW, result_panel.x+30, result_panel.y+20)
                draw_text(f"Pot: {game.pot}", font_mid, WHITE, result_panel.x+30, result_panel.y+80)
                if game.result_winner:
                    draw_text(f"Net gain: +{game.result_net_gain}", font_mid, YELLOW, result_panel.x+220, result_panel.y+80)
                draw_text(f"P1: {game.p1_rank}", font_mid, WHITE, result_panel.x+30, result_panel.y+120)
                draw_text(f"CPU: {game.p2_rank}", font_mid, WHITE, result_panel.x+30, result_panel.y+150)

                draw_centered_cards(game.p2.hand, result_panel.y+210)
                draw_centered_cards(game.board, result_panel.y+330)
                draw_centered_cards(game.p1.hand, result_panel.y+450)

                draw_action_records(game.log, result_panel.right-260, result_panel.y+80)

                pygame.draw.rect(screen,(60,60,60),continue_btn,border_radius=8)
                pygame.draw.rect(screen,(60,60,60),quit_btn,border_radius=8)
                draw_text("CONTINUE",font_small,WHITE,continue_btn.x+15,continue_btn.y+10)
                draw_text("QUIT",font_small,WHITE,quit_btn.x+45,quit_btn.y+10)

        if game.popup_msg:
            if time.time() - game.popup_start <= 1.5:
                draw_popup(game.popup_msg)
            else:
                game.popup_msg = None

        pygame.display.flip()
        clock.tick(30)

if __name__ == "__main__":
    main()