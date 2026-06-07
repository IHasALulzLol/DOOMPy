import asyncio
from player import Player
from sprite_objects import *
from ray_casting import ray_casting_walls
from drawing import Drawing
from interaction import Interaction

pygame.init()
sc = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF)
clock = pygame.time.Clock()

sc_map = pygame.Surface(MAP_RES)
sprites = Sprites()
player = Player(sprites)
drawing = Drawing(sc, sc_map, player, clock)
interaction = Interaction(player, sprites, drawing)

# ── lobby selection ──────────────────────────────────────────────────────────
lobby = drawing.menu()
pygame.mouse.set_visible(False)
interaction.play_music()

# HUD font
hud_font = pygame.font.SysFont('Arial', 22, bold=True)


async def main():
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

        # lobby code HUD
        code_surf = hud_font.render(f'Server: {lobby.code}', True, (200, 200, 200))
        sc.blit(code_surf, (10, 10))

        # death screen
        if not player.alive:
            pygame.mixer.music.stop()
            font_dead = pygame.font.SysFont('Arial', 100, bold=True)
            render = font_dead.render('YOU DIED', 1, RED)
            sc.blit(render, (HALF_WIDTH - 250, HALF_HEIGHT - 60))
            pygame.display.flip()
            await asyncio.sleep(3)
            return

        pygame.display.flip()
        clock.tick(30)
        await asyncio.sleep(0)   # yield to browser event loop


asyncio.run(main())