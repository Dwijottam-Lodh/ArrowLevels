import pygame,sys, json

# ================= Arrowlevels Mini Engine =================
pygame.init()
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

_players, _blocks = [], []
_event_registry = {"playerdeath": [], "keydown": {}}
GRAVITY = 0.5
_moves = []
_music_channel = None

# ---------------- Player Class ----------------
class Player(pygame.sprite.Sprite):
    def __init__(self, sprite=None, scale=(40,60), walk_accelaration=1, max_walkspeed=5,
                 jump_accelaration=-10, autoscroll=False, autoscroll_speed=2):
        super().__init__()
        self.image = pygame.Surface(scale)
        if sprite: self.image = pygame.image.load(sprite)
        else: self.image.fill((200,100,100))
        self.rect = self.image.get_rect(topleft=(100,100))
        self.vel = pygame.Vector2(0,0)

        self.walk_acc = walk_accelaration
        self.max_walk = max_walkspeed
        self.jump_acc = jump_accelaration
        self.autoscroll = autoscroll
        self.autoscroll_speed = autoscroll_speed

        self.grounded = False
        self.dead = False

        _players.append(self)

    def jump(self):
        if self.grounded:
            self.vel.y = self.jump_acc
            self.grounded = False

    def update(self, keys):
        if self.autoscroll:
            self.vel.x = self.autoscroll_speed
        else:
            if keys[pygame.K_LEFT]:
                self.vel.x = max(-self.max_walk, self.vel.x - self.walk_acc)
            elif keys[pygame.K_RIGHT]:
                self.vel.x = min(self.max_walk, self.vel.x + self.walk_acc)
            else:
                self.vel.x *= 0.8

        self.vel.y += GRAVITY
        self.rect.x += int(self.vel.x)
        self.rect.y += int(self.vel.y)

        self.grounded = False
        for b in _blocks:
            if self.rect.colliderect(b.rect):
                if self.vel.y > 0:
                    self.rect.bottom = b.rect.top
                    self.vel.y = 0
                    self.grounded = True
                if getattr(b,"danger",False) and not self.dead:
                    self.dead = True
                    spawn_block = next((blk for blk in _blocks if getattr(blk,"spawn",False)), None)
                    if spawn_block:
                        self.rect.topleft = spawn_block.rect.topleft
                        self.vel = pygame.Vector2(0,0)
                        self.dead = False
                    for cmd in _event_registry["playerdeath"]:
                        cmd()

# ---------------- Block Class ----------------
class Block(pygame.sprite.Sprite):
    def __init__(self, sprite=None, scale=(100,40), x=0, y=0, onclick=None, danger=False, spawn=False):
        super().__init__()
        if isinstance(sprite, pygame.Surface):
            self.image = sprite
        elif sprite:
            self.image = pygame.image.load(sprite)
        else:
            self.image = pygame.Surface(scale)
            self.image.fill((100,200,100) if not danger else (200,50,50))
        self.rect = self.image.get_rect(topleft=(x,y))
        self.onclick, self.danger, self.spawn = onclick, danger, spawn
        _blocks.append(self)
# ---------------- Spike ----------------
def Spike(scale=(40,40), color=(0,0,0)):
    """
    Returns a Pygame Surface with a black equilateral triangle (spike).
    `scale` = (width, height)
    `color` = RGB tuple
    """
    surf = pygame.Surface(scale, pygame.SRCALPHA)
    w, h = scale
    points = [(w//2, 0), (0, h), (w, h)]  # top-middle, bottom-left, bottom-right
    pygame.draw.polygon(surf, color, points)
    return surf

# ---------------- Moves ----------------
def Move(target, keyframes, speed=2):
    _moves.append({"target":target, "keyframes":keyframes, "index":0, "speed":speed})

def _update_moves():
    for mv in _moves:
        tgt = mv["target"]
        idx = mv["index"]
        pos = mv["keyframes"][idx]["pos"]
        dx, dy = pos[0]-tgt.rect.x, pos[1]-tgt.rect.y
        step_x = max(-mv["speed"], min(mv["speed"], dx))
        step_y = max(-mv["speed"], min(mv["speed"], dy))
        tgt.rect.x += step_x
        tgt.rect.y += step_y
        if (tgt.rect.x, tgt.rect.y) == pos:
            mv["index"] = (idx+1)%len(mv["keyframes"])

# ---------------- Music ----------------
def Music(file, loop=True):
    global _music_channel
    pygame.mixer.init()
    pygame.mixer.music.load(file)
    pygame.mixer.music.play(-1 if loop else 0)

# ---------------- API ----------------
def Player_(*a, **kw): return Player(*a, **kw)
def Physics(gravity=0.5, **_): global GRAVITY; GRAVITY=gravity
def Newblock(**kw): return Block(**kw)
def on(event, command):
    if event in _event_registry: _event_registry[event].append(command)
def Click(key, command):
    if key not in _event_registry["keydown"]: _event_registry["keydown"][key]=[]
    _event_registry["keydown"][key].append(command)
def Forcepush(x_velocity=0, y_velocity=0):
    for p in _players: p.vel += (x_velocity,y_velocity)

def Save(file,data):
    with open(file,"w") as f: json.dump(data,f,indent=4)

def Load(file):
    data = json.load(open(file))
    globals_cfg = data.get("globals",{})
    if "physics" in globals_cfg: Physics(**globals_cfg["physics"])
    if "players" in globals_cfg: Player_(**globals_cfg["players"])
    for blk_cfg in data.get("blocks",{}).values(): Newblock(**blk_cfg)

# ---------------- Mainloop ----------------
def mainloop(bg_color=(30,30,30)):
    running=True
    credit=False
    if not credit:
        print(f"{"-"*71}\nHey!\nThis is based off Arrowlevels v1.1 by Dwijottam Lodh AKA GIGADOJO.\nWebsite: https://gigadojowashere.neocities.org\nArrowlevels Repo: https://github.com/Dwijottam-Lodh/ArrowLevels. (Fork freely, just add the MIT License included.)")
        credit=True
    while running:
        keys = pygame.key.get_pressed()
        for e in pygame.event.get():
            if e.type==pygame.QUIT: running=False
            if e.type==pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                for b in _blocks:
                    if b.rect.collidepoint(pos) and b.onclick: b.onclick()
            if e.type==pygame.KEYDOWN:
                if e.key in _event_registry["keydown"]:
                    for cmd in _event_registry["keydown"][e.key]: cmd()

        for p in _players: p.update(keys)
        _update_moves()
        screen.fill(bg_color)
        for b in _blocks: screen.blit(b.image,b.rect)
        for p in _players: screen.blit(p.image,p.rect)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit(); sys.exit()
