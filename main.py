"""Entry point for the group project.

`python main.py` must run your project at every milestone, so keep this file working
from Milestone 1 onward. Replace the placeholder below with your own core loop.
"""


import math
import random
import sys

import pygame

W, H = 480, 360
SCALE = 2
FPS = 60
OIL_CAP = 100
SHIP_R = 18
BULLET_R = 5

SPECS = {
    "violet": {
        "label": "Violet",
        "hp": 10,
        "cruise": 90,
        "boost": 150,
        "turn": 150,
        "oil_every": 0.2,
        "oil_cost": 30,
        "oil_need": 1,
        "start": (-211, 103, 90),
        "cooldown": 2.0,
        "shots": [(0.0, 0, 300), (1.0, 0, 300)],
        "lunge": 0.0,
        "lunge_speed": 0,
        "color": (176, 124, 255),
        "body": (153, 102, 255),
        "nose": (102, 255, 102),
    },
    "mint": {
        "label": "Mint",
        "hp": 10,
        "cruise": 60,
        "boost": 150,
        "turn": 150,
        "oil_every": 0.4,
        "oil_cost": 30,
        "oil_need": 0,
        "start": (206, 72, -90),
        "cooldown": 0.45,
        "shots": [(0.0, 0, 300), (0.0, 180, 300)],
        "lunge": 10 / 30,
        "lunge_speed": 60,
        "color": (61, 222, 192),
        "body": (102, 255, 205),
        "nose": (102, 255, 119),
    },
    "yellow": {
        "label": "Yellow",
        "hp": 7,
        "cruise": 90,
        "boost": 150,
        "turn": 150,
        "oil_every": 0.3,
        "oil_cost": 45,
        "oil_need": 1,
        "start": (5, -107, 0),
        "cooldown": 1.5,
        "shots": [(0.0, 0, 300), (0.0, -30, 210), (0.0, 30, 210)],
        "lunge": 0.0,
        "lunge_speed": 0,
        "color": (240, 200, 74),
        "body": (255, 229, 102),
        "nose": (168, 130, 53),
    },
}
ORDER = ("violet", "mint", "yellow")
HAZARD_R = {"star": 16, "planet": 26, "sun": 34}


def wrap_deg(d):
    d = (d + 180) % 360 - 180
    return d


def ang_diff(target, current):
    return wrap_deg(target - current)


def dir_to(x, y, tx, ty):
    return math.degrees(math.atan2(tx - x, ty - y))


def dist(x, y, tx, ty):
    return math.hypot(tx - x, ty - y)


def move(x, y, direction, px):
    r = math.radians(direction)
    return x + math.sin(r) * px, y + math.cos(r) * px


def wrap_pos(x, y):
    if x > 240:
        x -= 480
    if x < -240:
        x += 480
    if y > 180:
        y -= 360
    if y < -180:
        y += 360
    return x, y


class Ship:
    def __init__(self, sid, name, kind):
        spec = SPECS[sid]
        self.id = sid
        self.name = name
        self.kind = kind
        self.x, self.y, self.dir = spec["start"]
        self.hp = spec["hp"]
        self.oil = 0.0
        self.alive = True
        self.cooldown = 0.35
        self.lunge = 0.0
        self.regen = 0.0
        self.immune = 0.0
        self.boosting = False
        self.pending = []


class Bullet:
    def __init__(self, owner, x, y, direction, speed):
        self.owner = owner
        self.x = x
        self.y = y
        self.dir = direction
        self.speed = speed


class Hazard:
    def __init__(self):
        self.alive = False
        self.wait = random.uniform(3, 7)
        self.kind = "star"
        self.x = self.y = 0
        self.x0 = self.y0 = self.x1 = self.y1 = 0
        self.t = 0
        self.dur = 5

    def launch(self):
        self.kind = random.choice(("star", "planet", "sun"))
        self.x0 = random.uniform(-240, 240)
        self.y0 = random.uniform(-180, 180)
        self.x1 = random.uniform(-240, 240)
        self.y1 = random.uniform(-180, 180)
        self.x, self.y = self.x0, self.y0
        self.t = 0
        self.dur = 5
        self.alive = True
        self.wait = 0


def fresh(human):
    ships = []
    for sid in ORDER:
        if sid == human:
            ships.append(Ship(sid, "You", "human"))
        else:
            ships.append(Ship(sid, SPECS[sid]["label"] + " drone", "ai"))
    return ships, [], Hazard(), "fight", None


def kinematics(ship, turn, boost, dt):
    if not ship.alive:
        ship.boosting = False
        return
    spec = SPECS[ship.id]
    if turn:
        ship.dir = wrap_deg(ship.dir + turn * spec["turn"] * dt)
    want = boost and ship.oil > spec["oil_need"]
    ship.boosting = want
    speed = spec["cruise"]
    if want:
        speed += spec["boost"]
        ship.oil -= spec["oil_cost"] * dt
        if ship.oil < 1:
            ship.oil = 0
    if ship.lunge > 0:
        speed += spec["lunge_speed"]
        ship.lunge = max(0, ship.lunge - dt)
    x, y = move(ship.x, ship.y, ship.dir, speed * dt)
    ship.x, ship.y = wrap_pos(x, y)
    ship.regen += dt
    while ship.regen >= spec["oil_every"]:
        ship.regen -= spec["oil_every"]
        ship.oil = min(OIL_CAP, ship.oil + 1)
    if ship.immune > 0:
        ship.immune = max(0, ship.immune - dt)
    if ship.cooldown > 0:
        ship.cooldown = max(0, ship.cooldown - dt)


def try_fire(ship, fire):
    if not ship.alive or ship.boosting or not fire or ship.cooldown > 0:
        return
    spec = SPECS[ship.id]
    ship.cooldown = spec["cooldown"]
    ship.lunge = spec["lunge"]
    ship.pending = [[delay, off, speed] for delay, off, speed in spec["shots"]]


def release(ship, bullets, dt):
    if not ship.alive:
        return
    keep = []
    for shot in ship.pending:
        shot[0] -= dt
        if shot[0] <= 0:
            direction = wrap_deg(ship.dir + shot[1])
            x, y = move(ship.x, ship.y, direction, 28)
            bullets.append(Bullet(ship.id, x, y, direction, shot[2]))
        else:
            keep.append(shot)
    ship.pending = keep


def ai_input(ship, ships, hazard):
    if not ship.alive:
        return 0, False, False
    foes = [s for s in ships if s.alive and s.id != ship.id]
    if not foes:
        return 0, False, False
    foe = min(foes, key=lambda s: dist(ship.x, ship.y, s.x, s.y))
    best = dist(ship.x, ship.y, foe.x, foe.y)
    desired = dir_to(ship.x, ship.y, foe.x, foe.y)
    hazard_close = False
    if hazard.alive:
        hd = dist(ship.x, ship.y, hazard.x, hazard.y)
        hang = dir_to(ship.x, ship.y, hazard.x, hazard.y)
        hazard_close = hd < HAZARD_R[hazard.kind] + 70
        if hazard_close and abs(ang_diff(hang, ship.dir)) < 55:
            desired = wrap_deg(hang + (-110 if ang_diff(hang, ship.dir) > 0 else 110))
    diff = ang_diff(desired, ship.dir)
    turn = 1 if diff > 7 else -1 if diff < -7 else 0
    aim = dir_to(ship.x, ship.y, foe.x, foe.y)
    to_foe = ang_diff(aim, ship.dir)
    aligned = abs(to_foe) < (34 if ship.id == "yellow" else 16)
    behind = abs(ang_diff(aim, wrap_deg(ship.dir + 180))) < 24
    oil_ok = ship.oil > (10 if ship.id == "yellow" else 6)
    do_boost = False
    if oil_ok and not hazard_close and abs(to_foe) < 38:
        if ship.id == "mint":
            do_boost = best > 170
        elif ship.id == "yellow":
            do_boost = best > 120
        else:
            do_boost = best > 95
    fire = (not do_boost) and (aligned or (ship.id == "mint" and behind and best < 230))
    return turn, do_boost, fire


def step_world(ships, bullets, hazard, phase, dt):
    if phase != "fight":
        return bullets, phase, None
    for ship in ships:
        if ship.kind == "ai":
            turn, boost, fire = ai_input(ship, ships, hazard)
        else:
            turn, boost, fire = ship.turn, ship.boost_key, ship.fire_key
        kinematics(ship, turn, boost, dt)
        try_fire(ship, fire)
        release(ship, bullets, dt)
    keep = []
    for b in bullets:
        b.x, b.y = move(b.x, b.y, b.dir, b.speed * dt)
        if abs(b.x) > 252 or abs(b.y) > 192:
            continue
        spent = False
        if hazard.alive and dist(b.x, b.y, hazard.x, hazard.y) < HAZARD_R[hazard.kind] + BULLET_R:
            hazard.alive = False
            hazard.wait = random.uniform(6, 12)
            spent = True
        if not spent:
            for ship in ships:
                if ship.alive and ship.id != b.owner and dist(b.x, b.y, ship.x, ship.y) < SHIP_R + BULLET_R:
                    ship.hp -= 1
                    if ship.hp < 1:
                        ship.alive = False
                        ship.hp = 0
                        ship.boosting = False
                    spent = True
                    break
        if not spent:
            keep.append(b)
    if not hazard.alive:
        hazard.wait -= dt
        if hazard.wait <= 0:
            hazard.launch()
    else:
        hazard.t += dt
        u = min(1, hazard.t / hazard.dur)
        hazard.x = hazard.x0 + (hazard.x1 - hazard.x0) * u
        hazard.y = hazard.y0 + (hazard.y1 - hazard.y0) * u
        if hazard.t >= hazard.dur:
            hazard.alive = False
            hazard.wait = random.uniform(6, 12)
        else:
            for ship in ships:
                if not ship.alive or ship.immune > 0:
                    continue
                if dist(ship.x, ship.y, hazard.x, hazard.y) < HAZARD_R[hazard.kind] + SHIP_R - 4:
                    ship.immune = 5
                    ship.hp -= 2
                    if ship.hp < 1:
                        ship.alive = False
                        ship.hp = 0
    up = [s for s in ships if s.alive]
    winner = None
    if len(up) <= 1:
        phase = "over"
        winner = up[0].id if up else "draw"
    return keep, phase, winner


def screen_pt(x, y):
    return int((x + 240) * SCALE), int((180 - y) * SCALE)


def draw_ship(surf, ship):
    if not ship.alive:
        return
    spec = SPECS[ship.id]
    sx, sy = screen_pt(ship.x, ship.y)
    s = pygame.Surface((70, 70), pygame.SRCALPHA)
    cx = cy = 35
    if ship.boosting or ship.lunge > 0:
        flame = (255, 93, 108) if ship.boosting else (240, 200, 74)
        pygame.draw.polygon(s, flame, [(cx - 16, cy), (cx - 32, cy + 8), (cx - 22, cy), (cx - 32, cy - 8)])
    pygame.draw.rect(s, spec["body"], (cx - 8, cy - 16, 16, 32))
    pygame.draw.polygon(s, spec["nose"], [(cx + 8, cy - 10), (cx + 24, cy), (cx + 8, cy + 10)])
    pygame.draw.line(s, (7, 16, 24), (cx - 6, cy - 6), (cx + 4, cy + 4), 2)
    if ship.hp / spec["hp"] < 0.5:
        pygame.draw.line(s, (7, 16, 24), (cx + 4, cy - 10), (cx - 6, cy + 2), 2)
    rot = pygame.transform.rotate(s, -(ship.dir - 90))
    rect = rot.get_rect(center=(sx, sy))
    surf.blit(rot, rect)
    bw = 36
    pygame.draw.rect(surf, (7, 16, 24), (sx - bw // 2, sy - 42, bw, 5))
    pygame.draw.rect(surf, spec["color"], (sx - bw // 2, sy - 42, int(bw * max(0, ship.hp) / spec["hp"]), 5))


def draw_world(screen, font, small, ships, bullets, hazard, phase, winner, human):
    screen.fill((7, 16, 24))
    arena = pygame.Rect(0, 0, W * SCALE, H * SCALE)
    pygame.draw.rect(screen, (12, 24, 36), arena)
    for i in range(1, 8):
        x = int(W * SCALE * i / 8)
        pygame.draw.line(screen, (30, 48, 58), (x, 0), (x, H * SCALE))
    for i in range(1, 6):
        y = int(H * SCALE * i / 6)
        pygame.draw.line(screen, (30, 48, 58), (0, y), (W * SCALE, y))
    if hazard.alive:
        hx, hy = screen_pt(hazard.x, hazard.y)
        col = {"star": (240, 200, 74), "planet": (127, 208, 196), "sun": (255, 140, 40)}[hazard.kind]
        pygame.draw.circle(screen, col, (hx, hy), HAZARD_R[hazard.kind] * SCALE // 2)
    for b in bullets:
        bx, by = screen_pt(b.x, b.y)
        pygame.draw.circle(screen, SPECS[b.owner]["color"], (bx, by), 4)
    for ship in ships:
        draw_ship(screen, ship)
    pygame.draw.rect(screen, (61, 222, 192), arena, 2)
    y = H * SCALE + 8
    for ship in ships:
        spec = SPECS[ship.id]
        label = f"{spec['label']}  HP {max(0, math.ceil(ship.hp))}  Oil {int(ship.oil)}"
        if not ship.alive:
            label = f"{spec['label']}  down"
        text = small.render(label, True, spec["color"])
        screen.blit(text, (12, y))
        y += 22
    if phase == "over":
        if winner == "draw":
            msg = "Both wings burned out"
        elif winner == human:
            msg = "You held the sky"
        else:
            msg = SPECS[winner]["label"] + " holds the sky"
        banner = font.render(msg + "   R restarts", True, (231, 242, 234))
        screen.blit(banner, (16, 16))


def title(screen, font, small, human):
    screen.fill((7, 16, 24))
    screen.blit(font.render("OILWING", True, (231, 242, 234)), (36, 36))
    lines = [
        "Versus the computer. Last wing flying.",
        "Glide never stops. Oil burn blocks your guns.",
        "",
        "1 Violet    fast oil, twin pulse, 10 HP",
        "2 Mint      nose + tail gun, then a lunge",
        "3 Yellow    thin hull, three-shot fan, 7 HP",
        "",
        "A/D or arrows turn.  W/Up burns oil.  S/Down fires.",
        "Enter starts as " + SPECS[human]["label"] + ".",
    ]
    y = 110
    for line in lines:
        screen.blit(small.render(line, True, (138, 160, 148)), (36, y))
        y += 28
    pygame.display.flip()


def main():
    pygame.init()
    screen = pygame.display.set_mode((W * SCALE, H * SCALE + 80))
    pygame.display.set_caption("OILWING — vs AI")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 28)
    small = pygame.font.SysFont("consolas", 18)
    human = "mint"
    mode = "title"
    ships, bullets, hazard, phase, winner = fresh(human)

    while True:
        dt = min(0.05, clock.tick(FPS) / 1000)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if mode == "title":
                    if event.key == pygame.K_1:
                        human = "violet"
                    elif event.key == pygame.K_2:
                        human = "mint"
                    elif event.key == pygame.K_3:
                        human = "yellow"
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        ships, bullets, hazard, phase, winner = fresh(human)
                        mode = "fight"
                elif event.key == pygame.K_r:
                    ships, bullets, hazard, phase, winner = fresh(human)
                    mode = "fight"
        if mode == "title":
            title(screen, font, small, human)
            continue
        keys = pygame.key.get_pressed()
        # A / Left decreases Scratch direction (counter-clockwise): nose goes left when facing up.
        turn = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            turn -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            turn += 1
        boost = keys[pygame.K_w] or keys[pygame.K_UP]
        fire = (keys[pygame.K_s] or keys[pygame.K_DOWN]) and not boost
        for ship in ships:
            if ship.kind == "human":
                ship.turn = turn
                ship.boost_key = boost
                ship.fire_key = fire
        if phase == "fight":
            bullets, phase, got = step_world(ships, bullets, hazard, phase, dt)
            if got is not None:
                winner = got
        draw_world(screen, font, small, ships, bullets, hazard, phase, winner, human)
        pygame.display.flip()



if __name__ == '__main__':
    main()
