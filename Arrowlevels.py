import pygame, sys, json
pygame.init()

# ================= Arrowlevels Mini Engine =================
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

_players, _blocks, _cameras, _animations = [], [], [], []
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
        self.death_timer = 0

        _players.append(self)

    def jump(self):
        if self.grounded and self.death_timer == 0:
            self.vel.y = self.jump_acc
            self.grounded = False

    def _die(self):
        self.dead = True
        self.vel = pygame.Vector2(0,0)
        spawn_block = next((b for b in _blocks if getattr(b, "spawn", False)), None)
        if spawn_block:
            self.rect.midbottom = spawn_block.rect.midtop
        self.death_timer = 1
        for cmd in _event_registry["playerdeath"]:
            cmd()

    def update(self, keys):
        if self.death_timer > 0:
            self.death_timer -= 1
            return

        # Horizontal movement
        if self.autoscroll:
            self.vel.x = self.autoscroll_speed
        else:
            if keys[pygame.K_LEFT]:
                self.vel.x = max(-self.max_walk, self.vel.x - self.walk_acc)
            elif keys[pygame.K_RIGHT]:
                self.vel.x = min(self.max_walk, self.vel.x + self.walk_acc)
            else:
                self.vel.x *= 0.8

        # Gravity
        self.vel.y += GRAVITY

        # Horizontal collision
        self.rect.x += int(self.vel.x)
        for b in _blocks:
            if getattr(b, "passable", False): continue
            if self.rect.colliderect(b.rect):
                if getattr(b, "danger", False):
                    self._die()
                    return
                if self.vel.x > 0: self.rect.right = b.rect.left
                elif self.vel.x < 0: self.rect.left = b.rect.right
                self.vel.x = 0
                if b.oncollide: b.oncollide(self)

        # Vertical collision
        self.rect.y += int(self.vel.y)
        self.grounded = False
        for b in _blocks:
            if getattr(b, "passable", False): continue
            if self.rect.colliderect(b.rect):
                if getattr(b, "ladder", False) and self.vel.y < 0:
                    while self.rect.colliderect(b.rect):
                        self.rect.y -= 2
                    continue
                if getattr(b, "danger", False):
                    self._die()
                    return
                if self.vel.y > 0:
                    self.rect.bottom = b.rect.top
                    self.vel.y = 0
                    self.grounded = True
                elif self.vel.y < 0:
                    self.rect.top = b.rect.bottom
                    self.vel.y = 0
                if b.oncollide: b.oncollide(self)

# ---------------- Block Class ----------------
class Block(pygame.sprite.Sprite):
    def __init__(self, sprite=None, scale=(100,40), x=0, y=0, onclick=None, oncollide=None,
                 danger=False, spawn=False, passable=False, alpha=255, ladder=False):
        super().__init__()
        if isinstance(sprite, pygame.Surface):
            self.image = sprite.copy()
        elif sprite:
            self.image = pygame.image.load(sprite)
        else:
            self.image = pygame.Surface(scale, pygame.SRCALPHA)
            color = (100,200,100) if not danger else (200,50,50)
            self.image.fill((*color, alpha))
        self.image.set_alpha(alpha)
        self.rect = self.image.get_rect(topleft=(x,y))
        self.onclick = onclick
        self.oncollide = oncollide
        self.danger = danger
        self.spawn = spawn
        self.passable = passable
        self.ladder = ladder
        self.alpha = alpha
        _blocks.append(self)

# ---------------- Camera ----------------
class Camera:
    active_camera = None
    def __init__(self, target=None, target_player=True, xoffset=0, yoffset=0, zoom=1, active=True):
        self.target = target
        self.target_player = target_player
        self.xoffset = xoffset
        self.yoffset = yoffset
        self.zoom = zoom
        if active:
            Camera.active_camera = self
        _cameras.append(self)

    def apply(self, rect):
        if Camera.active_camera is None: return rect
        tx, ty = 0,0
        if self.target_player:
            tx = self.target.rect.centerx if self.target else 0
            ty = self.target.rect.centery if self.target else 0
        else:
            tx = self.target.rect.centerx if self.target else 0
            ty = self.target.rect.centery if self.target else 0
        return pygame.Rect(
            (rect.x - tx + 400 + self.xoffset) * self.zoom,
            (rect.y - ty + 300 + self.yoffset) * self.zoom,
            rect.width * self.zoom,
            rect.height * self.zoom
        )

# ---------------- Animate ----------------
class Animate:
    def __init__(self, target, target_player=True, animation=None, interval=5, offset=0, steps_ahead=1):
        self.target = target
        self.target_player = target_player
        self.animation = animation or []
        self.interval = interval
        self.offset = offset
        self.steps_ahead = max(1, steps_ahead)
        self.counter = 0
        self.frame = 0
        _animations.append(self)

    def update(self):
        self.counter += 1
        if self.counter % self.interval == 0:
            self.frame = (self.frame + self.steps_ahead) % len(self.animation)
            self.target.image = self.animation[self.frame]

# ---------------- Move System ----------------
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
            mv["index"] = (idx+1) % len(mv["keyframes"])

# ---------------- Assets ----------------
Assets = {}

def Asset(name, x, y, sprite=None, alpha=255, danger=False, passable=True, spawn=False,
          oncollide=None, onclick=None, ladder=False, z=0):
    if sprite is None:
        sprite = pygame.Surface((40,40),pygame.SRCALPHA)
        color = (0,0,0) if danger else (255,255,255)
        pygame.draw.rect(sprite, color, (0,0,40,40))
    obj = Block(sprite=sprite, x=x, y=y, danger=danger, passable=passable,
                spawn=spawn, oncollide=oncollide, onclick=onclick, ladder=ladder, alpha=alpha)
    Assets[name] = obj
    return obj


# Spike: black triangle
surf = pygame.Surface((40,40), pygame.SRCALPHA)
pygame.draw.polygon(surf, (0,0,0), [(20,0),(0,40),(40,40)])
Asset("spike", x=100, y=200, sprite=surf, danger=True, passable=False)

# Block: black square
surf_block = pygame.Surface((40,40))
surf_block.fill((0,0,0))
Asset("block", x=200, y=300, sprite=surf_block, passable=False)

# JumpOrb: yellow circle
surf_orb = pygame.Surface((40,40), pygame.SRCALPHA)
pygame.draw.circle(surf_orb, (255,255,0), (20,20), 20)
Asset("jumporb", x=300, y=300, sprite=surf_orb, passable=True, onclick=lambda player: setattr(player.vel, "y", -15))

# Spawn: invisible square
surf_spawn = pygame.Surface((40,40),pygame.SRCALPHA)
Asset("spawn", x=50, y=500, sprite=surf_spawn, passable=True, spawn=True)

# Moving Platform: gray rectangle, passable False
surf_mplat = pygame.Surface((80,20))
surf_mplat.fill((150,150,150))
Asset("moving_platform", x=400, y=400, sprite=surf_mplat, passable=False)

# Collectible Star: yellow star, passable True, oncollide removes it
surf_star = pygame.Surface((30,30),pygame.SRCALPHA)
pygame.draw.polygon(surf_star, (255,255,0), [(15,0),(18,10),(30,10),(20,18),(23,30),(15,23),(7,30),(10,18),(0,10),(12,10)])
Asset("star", x=500, y=200, sprite=surf_star, passable=True, oncollide=lambda p: _blocks.remove(Assets["star"]))

# Ladder: brown rectangle, ladder=True
surf_ladder = pygame.Surface((20,80))
surf_ladder.fill((150,75,0))
Asset("ladder", x=600, y=300, sprite=surf_ladder, passable=True, ladder=True)

# Spring Pad: blue rectangle, passable True, oncollide boosts player upward
surf_spring = pygame.Surface((40,10))
surf_spring.fill((0,0,255))
Asset("spring", x=700, y=500, sprite=surf_spring, passable=True,
      oncollide=lambda p: setattr(p.vel, "y", -20))

# Enemy Dummy: red square, danger True
surf_enemy = pygame.Surface((40,40))
surf_enemy.fill((255,0,0))
Asset("enemy", x=350, y=350, sprite=surf_enemy, danger=True, passable=False)
# ---------------- API ----------------
def Player_(*a, **kw): return Player(*a, **kw)
def Physics(gravity=0.5, **_): global GRAVITY; GRAVITY=gravity
def Newblock(**kw): return Block(**kw)
def on(event, command): _event_registry[event].append(command)
_held_keys = {}
def Click(key, command, repeat=False):
    if key not in _event_registry["keydown"]:
        _event_registry["keydown"][key] = []
    _event_registry["keydown"][key].append(command)
    if repeat: _held_keys[key] = command
def _update_held_keys(keys):
    for key, cmd in _held_keys.items():
        if keys[key]: cmd()
def Forcepush(x_velocity=0, y_velocity=0):
    for p in _players: p.vel += (x_velocity, y_velocity)
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
    print("-"*71)
    print("Arrowlevels Mini Engine v2.0")
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
        for b in _blocks: screen.blit(b.image, Camera.active_camera.apply(b.rect) if Camera.active_camera else b.rect)
        for p in _players: screen.blit(p.image, Camera.active_camera.apply(p.rect) if Camera.active_camera else p.rect)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()
