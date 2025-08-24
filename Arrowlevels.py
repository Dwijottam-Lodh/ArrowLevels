import pygame, sys, json

# ================= Arrowlevels Mini Engine =================
pygame.init()
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

_players, _blocks, _animations = [], [], []
_event_registry = {"playerdeath": [], "keydown": {}}
_held_keys = {}
GRAVITY = 0.5
_moves = []
_music_channel = None
_camera = None

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
        self.death_timer = 0

        _players.append(self)

    def jump(self):
        if self.grounded and self.death_timer == 0:
            self.vel.y = self.jump_acc
            self.grounded = False

    def _die(self):
        self.dead = True
        self.vel = pygame.Vector2(0,0)
        spawn_block = next((blk for blk in _blocks if getattr(blk,"spawn",False)), None)
        if spawn_block:
            self.rect.midbottom = spawn_block.rect.midtop
        self.death_timer = 1
        for cmd in _event_registry["playerdeath"]:
            cmd()

    def update(self, keys):
        if self.death_timer > 0:
            self.death_timer -= 1
            return

        # horizontal input
        if self.autoscroll:
            self.vel.x = self.autoscroll_speed
        else:
            if keys[pygame.K_LEFT]:
                self.vel.x = max(-self.max_walk, self.vel.x - self.walk_acc)
            elif keys[pygame.K_RIGHT]:
                self.vel.x = min(self.max_walk, self.vel.x + self.walk_acc)
            else:
                self.vel.x *= 0.8

        # apply gravity
        self.vel.y += GRAVITY

        # Horizontal collision
        self.rect.x += int(self.vel.x)
        for b in _blocks:
            if getattr(b,"passable",False): continue
            if self.rect.colliderect(b.rect):
                if getattr(b,"danger",False):
                    self._die()
                    return
                if self.vel.x > 0: self.rect.right = b.rect.left
                elif self.vel.x < 0: self.rect.left = b.rect.right
                self.vel.x = 0
                if callable(getattr(b,"oncollide",None)):
                    b.oncollide(self)

        # Vertical collision
        self.rect.y += int(self.vel.y)
        self.grounded = False
        for b in _blocks:
            if getattr(b,"passable",False): continue
            if self.rect.colliderect(b.rect):
                # ladder logic
                if getattr(b,"ladder",False) and self.vel.y < 0:
                    while self.rect.colliderect(b.rect):
                        self.rect.y -= 2
                    continue
                if getattr(b,"danger",False):
                    self._die()
                    return
                if self.vel.y > 0:
                    self.rect.bottom = b.rect.top
                    self.vel.y = 0
                    self.grounded = True
                elif self.vel.y < 0:
                    self.rect.top = b.rect.bottom
                    self.vel.y = 0
                if callable(getattr(b,"oncollide",None)):
                    b.oncollide(self)

# ---------------- Block Class ----------------
class Block(pygame.sprite.Sprite):
    def __init__(self, sprite=None, scale=(100,40), x=0, y=0,
                 onclick=None, oncollide=None, danger=False, spawn=False,
                 passable=False, ladder=False, alpha=255):
        super().__init__()
        if isinstance(sprite,pygame.Surface): self.image = sprite.copy()
        elif sprite: self.image = pygame.image.load(sprite)
        else:
            self.image = pygame.Surface(scale,pygame.SRCALPHA)
            color = (100,200,100) if not danger else (200,50,50)
            self.image.fill((*color,alpha))

        self.image.set_alpha(alpha)
        self.rect = self.image.get_rect(topleft=(x,y))
        self.onclick = onclick
        self.oncollide = oncollide
        self.danger = danger
        self.spawn = spawn
        self.passable = passable
        self.ladder = ladder

        _blocks.append(self)

# ---------------- Spike ----------------
def Spike(scale=(40,40), color=(0,0,0)):
    surf = pygame.Surface(scale,pygame.SRCALPHA)
    w,h = scale
    points = [(w//2,0),(0,h),(w,h)]
    pygame.draw.polygon(surf,color,points)
    return surf

# ---------------- Moves ----------------
def Move(target,keyframes,speed=2):
    _moves.append({"target":target,"keyframes":keyframes,"index":0,"speed":speed})

def _update_moves():
    for mv in _moves:
        tgt = mv["target"]
        idx = mv["index"]
        pos = mv["keyframes"][idx]["pos"]
        dx,dy = pos[0]-tgt.rect.x, pos[1]-tgt.rect.y
        step_x = max(-mv["speed"], min(mv["speed"], dx))
        step_y = max(-mv["speed"], min(mv["speed"], dy))
        tgt.rect.x += step_x
        tgt.rect.y += step_y
        if (tgt.rect.x,tgt.rect.y)==pos: mv["index"] = (idx+1)%len(mv["keyframes"])

# ---------------- Camera ----------------
class Camera:
    def __init__(self,target=None,target_player=True,xoffset=0,yoffset=0,zoom=1,active=True):
        global _camera
        self.target = target or (_players[0] if target_player else None)
        self.xoffset = xoffset
        self.yoffset = yoffset
        self.zoom = zoom
        self.active = active
        _camera = self

    def apply(self,surf,rect):
        if not self.active: return surf,rect
        x = int((rect.x - self.target.rect.x + 400 + self.xoffset)*self.zoom)
        y = int((rect.y - self.target.rect.y + 300 + self.yoffset)*self.zoom)
        surf_scaled = pygame.transform.scale(surf,(int(rect.width*self.zoom),int(rect.height*self.zoom)))
        return surf_scaled, pygame.Rect(x,y,rect.width*self.zoom,rect.height*self.zoom)

# ---------------- Animation ----------------
class Animate:
    def __init__(self,target=None,target_player=True,animation=[],interval=5,offset=0,steps_ahead=1):
        self.target = target or (_players[0] if target_player else None)
        self.animation = animation
        self.interval = interval
        self.offset = offset
        self.steps_ahead = steps_ahead
        self.frame_counter = self.offset
        self.index = 0
        _animations.append(self)

    def update(self):
        if not self.target: return
        self.frame_counter += self.steps_ahead
        if self.frame_counter >= self.interval:
            self.frame_counter = 0
            self.index = (self.index + 1)%len(self.animation)
            self.target.image = self.animation[self.index]

# ---------------- Music ----------------
def Music(file, loop=True):
    global _music_channel
    pygame.mixer.init()
    pygame.mixer.music.load(file)
    pygame.mixer.music.play(-1 if loop else 0)

# ---------------- API ----------------
def Player_(*a,**kw): return Player(*a,**kw)
def Physics(gravity=0.5,**_): global GRAVITY; GRAVITY=gravity
def Newblock(**kw): return Block(**kw)
def on(event,command):
    if event in _event_registry: _event_registry[event].append(command)
def Click(key,command,repeat=False):
    if key not in _event_registry["keydown"]: _event_registry["keydown"][key] = []
    _event_registry["keydown"][key].append(command)
    if repeat: _held_keys[key] = command
def Forcepush(x_velocity=0,y_velocity=0):
    for p in _players: p.vel += (x_velocity,y_velocity)

def Save(file,data):
    with open(file,"w") as f: json.dump(data,f,indent=4)
def Load(file):
    data = json.load(open(file))
    globals_cfg = data.get("globals",{})
    if "physics" in globals_cfg: Physics(**globals_cfg["physics"])
    if "players" in globals_cfg: Player_(**globals_cfg["players"])
    for blk_cfg in data.get("blocks",{}).values(): Newblock(**blk_cfg)

def _update_held_keys(keys):
    for key,cmd in _held_keys.items():
        if keys[key]: cmd()

# ---------------- Mainloop ----------------
def mainloop(bg_color=(30,30,30)):
    print("-" * 71)
    print("Hey!\nThis is based off Arrowlevels v1:3 by Dwijottam Lodh AKA GIGADOJO.")
    print("Website: https://gigadojowashere.neocities.org")
    print("Arrowlevels Repo: https://github.com/Dwijottam-Lodh/ArrowLevels")
    running = True
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

        _update_held_keys(keys)
        for p in _players: p.update(keys)
        _update_moves()
        for anim in _animations: anim.update()

        screen.fill(bg_color)
        for b in _blocks:
            img,rect = (_camera.apply(b.image,b.rect) if _camera else (b.image,b.rect))
            screen.blit(img,rect)
        for p in _players:
            img,rect = (_camera.apply(p.image,p.rect) if _camera else (p.image,p.rect))
            screen.blit(img,rect)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()
