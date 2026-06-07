from player import Player
from sprite_objects import *
from ray_casting import ray_casting_walls
from drawing import Drawing
from interaction import Interaction
from network import GameNetwork

pygame.init()
sc = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF)
clock = pygame.time.Clock()

sc_map = pygame.Surface(MAP_RES)
sprites = Sprites()
player = Player(sprites)
drawing = Drawing(sc, sc_map, player, clock)
interaction = Interaction(player, sprites, drawing)

# ── lobby selection ──────────────────────────────────────────────────────────
lobby = drawing.menu()          # returns LobbyResult(action, code, host, port, ...)
pygame.mouse.set_visible(False)
interaction.play_music()

# ── network setup ────────────────────────────────────────────────────────────
game_net = GameNetwork()
peer_addr = (lobby.host, lobby.port) if lobby.action == 'join' else None

# HUD overlay: show server code in top-left while playing
hud_font = pygame.font.SysFont('Arial', 22, bold=True)

while True:

    player.movement()
    drawing.background()
    walls, wall_shot = ray_casting_walls(player, drawing.textures)
    drawing.world(walls + [obj.object_locate(player) for obj in sprites.list_of_objects])
    drawing.fps(clock)
    drawing.mini_map()
    drawing.health_bar()
    drawing.player_weapon([wall_shot, sprites.sprite_shot])

    interaction.interaction_objects()
    interaction.npc_action()
    interaction.clear_world()
    interaction.check_win()

    # ── send our state to peer (if connected) ──────────────────────────────
    if peer_addr:
        state = {'id': 'p1', 'x': player.x, 'y': player.y,
                 'angle': player.angle, 'hp': player.health}
        game_net.send_state(peer_addr, state)

    # ── in-game HUD: lobby code ────────────────────────────────────────────
    code_surf = hud_font.render(f'Server: {lobby.code}', True, (200, 200, 200))
    sc.blit(code_surf, (10, 10))

    # ── death check ────────────────────────────────────────────────────────
    if not player.alive:
        pygame.mixer.music.stop()
        font_dead = pygame.font.SysFont('Arial', 100, bold=True)
        render = font_dead.render('YOU DIED', 1, RED)
        sc.blit(render, (HALF_WIDTH - 250, HALF_HEIGHT - 60))
        pygame.display.flip()
        pygame.time.wait(3000)
        game_net.stop()
        exit()

    pygame.display.flip()
    clock.tick()