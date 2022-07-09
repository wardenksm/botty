import keyboard
from char.sorceress import Sorceress
from utils.custom_mouse import mouse
from logger import Logger
from utils.misc import wait, rotate_vec, unit_vector
import random, time, math
from pather import Location
import numpy as np
from screen import convert_abs_to_monitor, convert_screen_to_monitor, grab, convert_screen_to_abs
from config import Config
import template_finder
from ui_manager import center_mouse, ScreenObjects, is_visible
import cv2

class BlizzSorc(Sorceress):
    def __init__(self, *args, **kwargs):
        Logger.info("Setting up Blizz Sorc")
        super().__init__(*args, **kwargs)
        #Nihlathak Bottom Right
        self._pather.offset_node(505, (50, 200))
        self._pather.offset_node(506, (40, -10))
        #Nihlathak Top Right
        self._pather.offset_node(510, (700, -55))
        self._pather.offset_node(511, (30, -25))
        #Nihlathak Top Left
        self._pather.offset_node(515, (-120, -100))
        self._pather.offset_node(517, (-18, -58))
        #Nihlathak Bottom Left
        self._pather.offset_node(500, (-150, 200))
        self._pather.offset_node(501, (10, -33))
        self._secondary_skill = self._static_field
        self._ranged_secondary = False
        if self._skill_hotkeys["hydra"]:
            self._secondary_skill = self._hydra
            self._ranged_secondary = True
        elif self._skill_hotkeys["fire_ball"]:
            self._secondary_skill = self._fire_ball
            self._ranged_secondary = True
        elif self._skill_hotkeys["nova"]:
            self._secondary_skill = self._nova

    def _hydra(self, cast_pos_abs: tuple[float, float], wait_time = 3.5):
        self.cast_in_arc("hydra", cast_pos_abs, time_in_s=self._cast_duration*5, spread_deg=12)
        time.sleep(wait_time)

    def _fire_ball(self, cast_pos_abs: tuple[float, float], atk_len = 3):
        self.cast_in_arc("fireball", cast_pos_abs, time_in_s=atk_len*3)
        time.sleep(0.5)

    def _nova(self, duration = 3):
        center_mouse()
        if self._skill_hotkeys["static_field"]:
            keyboard.send(self._skill_hotkeys["static_field"])
            mouse.press(button="right")
            time.sleep(duration * 0.25)
            duration *= 0.75
            mouse.release(button="right")
        if self._skill_hotkeys["nova"]:
            keyboard.send(self._skill_hotkeys["nova"])
        else:
            raise ValueError("You did not set a hotkey for Nova!")
        time.sleep(0.04)
        mouse.press(button="right")
        start = time.time()
        while (time.time() - start) < duration:
            time.sleep(self._cast_duration-0.02)
            mouse.release("right")
            time.sleep(0.01)
            mouse.click("right")
        mouse.release(button="right")
    
    def _static_field(self, duration = 3):
        center_mouse()
        self._cast_static(duration + 1)

    def _ice_blast(self, cast_pos_abs: tuple[float, float], delay: tuple[float, float] = (0.16, 0.23), spray: float = 10):
        keyboard.send(Config().char["stand_still"], do_release=False)
        if self._skill_hotkeys["ice_blast"]:
            keyboard.send(self._skill_hotkeys["ice_blast"])
        for _ in range(5):
            x = cast_pos_abs[0] + (random.random() * 2*spray - spray)
            y = cast_pos_abs[1] + (random.random() * 2*spray - spray)
            cast_pos_monitor = convert_abs_to_monitor((x, y))
            mouse.move(*cast_pos_monitor)
            mouse.press(button="left")
            wait(delay[0], delay[1])
            mouse.release(button="left")
        keyboard.send(Config().char["stand_still"], do_press=False)

    def _cast_ranged_spell(self, skill, cast_pos_abs: tuple[float, float], atk_len = 1, spray: float = 8, monster = None):
        if self._skill_hotkeys[skill]:
            keyboard.send(self._skill_hotkeys[skill])
        else:
            raise ValueError(f"You did not set a hotkey for {skill}!")
        if monster is not None:
            cast_pos_monitor = convert_abs_to_monitor(cast_pos_abs)
            mouse.move(*cast_pos_monitor)
        prev_time = start_time = time.time()
        while True:
            if monster is not None:
                img = grab()
                self.find_name_bar(img, monster)
            x = cast_pos_abs[0] + (random.random() * 2 - 1) * spray
            y = cast_pos_abs[1] + (random.random() * 2 - 1) * spray
            cast_pos_monitor = convert_abs_to_monitor((x, y))
            mouse.move(*cast_pos_monitor)
            mouse.press("right")
            curr_time = time.time()
            delta = 0.1 - curr_time + prev_time
            if delta > 0:
                time.sleep(delta)
                prev_time = time.time()
            else:
                prev_time = curr_time
            mouse.release("right")
            if prev_time - start_time > atk_len * self._cast_duration:
                break
        return cast_pos_abs

    def _blizzard(self, cast_pos_abs: tuple[float, float], spray: float = 10):
        if not self._skill_hotkeys["blizzard"]:
            raise ValueError("You did not set a hotkey for blizzard!")
        keyboard.send(self._skill_hotkeys["blizzard"])
        x = cast_pos_abs[0] + (random.random() * 2 * spray - spray)
        y = cast_pos_abs[1] + (random.random() * 2 * spray - spray)
        cast_pos_monitor = convert_abs_to_monitor((x, y))
        mouse.move(*cast_pos_monitor)
        click_tries = 1#random.randint(2, 4)
        for _ in range(click_tries):
            mouse.press(button="right")
            wait(0.09, 0.12)
            mouse.release(button="right")

    def kill_pindle(self) -> bool:
        self._found_monster_bar = 0
        self._monster_gone_cnt = 0
        self._name_bar_gone_cnt = -1
        self._monster_hp = 1.0
        self._immunities = ''
        atk_len = Config().char["atk_len_pindle"]

        found_name_bar = False
        pindle_end = Config().path["pindle_end"][0]
        mouse.move(*convert_screen_to_monitor(pindle_end), delay_factor=[0.1,0.2])
        img = grab()
        found_name_bar = self.find_name_bar(img, "pindle")
        if found_name_bar:
            pindle_pos = pindle_end
        else:
            time.sleep(0.3) # wait for fade out effect of the roof
            pindle_pos = self.find_monster_pos(grab(), "pindle")
            if pindle_pos is None:
                pindle_pos = pindle_end
            else:
                Logger.info(f"Found pindle at {pindle_pos}")
            mouse.move(*convert_screen_to_monitor(pindle_pos), delay_factor=[0.1,0.2])
            time.sleep(0.04)
            found_name_bar = self.find_name_bar(grab(), "pindle")

        if found_name_bar:
            pindle_pos_abs = convert_screen_to_abs(pindle_pos)
        else:
            pindle_pos_abs = convert_screen_to_abs(pindle_end)
            #cv2.imwrite(f"./debug_screenshots/bad_detect_{time.strftime('%m%d_%H%M%S')}_{pindle_pos}.png", img)
        cast_pos_abs = (pindle_pos_abs[0] * 0.8, pindle_pos_abs[1] * 0.8)

        self._fe_explosin_cnt = 0
        self._blizzard(cast_pos_abs, spray=5)
        if found_name_bar:
            self._cast_ranged_spell("glacier_spike", pindle_pos_abs)
        else:
            self._cast_ranged_spell("glacier_spike", cast_pos_abs, monster="pindle")
        self.cast_in_arc(ability="ice_blast", cast_pos_abs=pindle_pos_abs, spread_deg=10, time_in_s=4*self._cast_duration, btn="left")
        for i in range(int(atk_len - 1)):
            cast_pos_abs = (pindle_pos_abs[0] * 0.75**(i+1), pindle_pos_abs[1] * 0.75**(i+1))
            self._blizzard(cast_pos_abs, spray=5)
            if 'c' in self._immunities:
                Logger.info("Found cold immune, kill with secondary spell")
                if self._ranged_secondary:
                    self._secondary_skill(cast_pos_abs, atk_len)
                else:
                    # Chicken if merc is dead
                    if not is_visible(ScreenObjects.MercIcon):
                        return False
                    # Move close to pindle
                    cast_pos_abs = (pindle_pos_abs[0] * 0.5, pindle_pos_abs[1] * 0.5)
                    node = convert_abs_to_monitor(cast_pos_abs)
                    self.select_tp()
                    self.move(node, force_tp = True)
                    self._secondary_skill(atk_len)
                break
            if not found_name_bar:
                found_name_bar = self.find_name_bar(grab(), "pindle")
            self._cast_ranged_spell("glacier_spike", cast_pos_abs, monster="pindle")
            self.cast_in_arc(ability="ice_blast", cast_pos_abs=pindle_pos_abs, spread_deg=15, time_in_s=4*self._cast_duration, btn="left")
            if self._monster_hp < 0.1:
                break

        self.pre_move()
        cast_pos_monitor = convert_abs_to_monitor(cast_pos_abs)
        wait(0.1, 0.15)
        self.move(cast_pos_monitor, force_tp=True, force_move=True)
        return True

    def kill_eldritch(self) -> bool:
        #move up
        pos_m = convert_abs_to_monitor((0, -175))
        self.pre_move()
        self.move(pos_m, force_move=True)
        self._blizzard((-50, -50), spray=10)
        self._cast_static()
        wait(0.75)
        #move down
        pos_m = convert_abs_to_monitor((0, 85))
        self.pre_move()
        self.move(pos_m, force_move=True)
        self._blizzard((-170, -350), spray=10)
        self._cast_static()
        #move down
        wait(0.75)
        pos_m = convert_abs_to_monitor((0, 75))
        self.pre_move()
        self.move(pos_m, force_move=True)
        self._blizzard((100, -300), spray=10)
        self._cast_static()
        wait(0.75)
        pos_m = convert_abs_to_monitor((0, 55))
        self.pre_move()
        self.move(pos_m, force_move=True)
        self._blizzard((-50, -130), spray=10)
        self._cast_static()
        wait(3.0)
        pos_m = convert_abs_to_monitor((0, -100))
        self.pre_move()
        self.move(pos_m, force_move=True)
        self._blizzard((-50, -130), spray=10)
        self._cast_static()
        wait(1.75)
        self._pather.traverse_nodes_fixed("eldritch_end", self)
        return True

    def kill_shenk(self) -> bool:
        pos_m = convert_abs_to_monitor((100, 170))
        self.pre_move()
        self.move(pos_m, force_move=True)
        #lower left posistion
        self._pather.traverse_nodes([151], self, timeout=2.5, force_tp=False)
        self._cast_static()
        self._blizzard((-250, 100), spray=10)
        self._ice_blast((60, 70), spray=60)
        self._blizzard((400, 200), spray=10)
        self._cast_static()
        self._ice_blast((-300, 100), spray=60)
        self._blizzard((185, 200), spray=10)
        pos_m = convert_abs_to_monitor((-10, 10))
        self.pre_move()
        self.move(pos_m, force_move=True)
        self._cast_static()
        self._blizzard((-300, -270), spray=10)
        self._ice_blast((-20, 30), spray=60)
        wait(1.0)
        #teledance 2
        pos_m = convert_abs_to_monitor((150, -240))
        self.pre_move()
        self.move(pos_m, force_move=True)
        #teledance attack 2
        self._cast_static()
        self._blizzard((450, -250), spray=10)
        self._ice_blast((150, -100), spray=60)
        self._blizzard((0, -250), spray=10)
        wait(0.3)
        #Shenk Kill
        self._cast_static()
        self._blizzard((100, -50), spray=10)
        # Move to items
        self._pather.traverse_nodes((Location.A5_SHENK_SAFE_DIST, Location.A5_SHENK_END), self, timeout=1.4, force_tp=True)
        return True

    def kill_council(self) -> bool:
        # Move inside to the right
        self._pather.traverse_nodes_fixed([(1110, 120)], self)
        self._pather.offset_node(300, (80, -110))
        self._pather.traverse_nodes([300], self, timeout=5.5, force_tp=True)
        self._pather.offset_node(300, (-80, 110))
        # Attack to the left
        self._blizzard((-150, 10), spray=80)
        self._ice_blast((-300, 50), spray=40)
        # Tele back and attack
        pos_m = convert_abs_to_monitor((-50, 200))
        self.pre_move()
        self.move(pos_m, force_move=True)
        self._blizzard((-235, -230), spray=80)
        wait(1.0)
        pos_m = convert_abs_to_monitor((-285, -320))
        self.pre_move()
        self.move(pos_m, force_move=True)
        wait(0.5)
        # Move to far left
        self._pather.offset_node(301, (-80, -50))
        self._pather.traverse_nodes([301], self, timeout=2.5, force_tp=True)
        self._pather.offset_node(301, (80, 50))
        # Attack to RIGHT
        self._blizzard((100, 150), spray=80)
        self._ice_blast((230, 230), spray=20)
        wait(0.5)
        self._blizzard((310, 260), spray=80)
        wait(1.0)
        # Move to bottom of stairs
        self.pre_move()
        for p in [(450, 100), (-190, 200)]:
            pos_m = convert_abs_to_monitor(p)
            self.move(pos_m, force_move=True)
        self._pather.traverse_nodes([304], self, timeout=2.5, force_tp=True)
        # Attack to center of stairs
        self._blizzard((-175, -200), spray=30)
        self._ice_blast((30, -60), spray=30)
        wait(0.5)
        self._blizzard((175, -270), spray=30)
        wait(1.0)
        # Move back inside
        self._pather.traverse_nodes_fixed([(1110, 15)], self)
        self._pather.traverse_nodes([300], self, timeout=2.5, force_tp=False)
        # Attack to center
        self._blizzard((-100, 0), spray=10)
        self._cast_static()
        self._ice_blast((-300, 30), spray=50)
        self._blizzard((-175, 50), spray=10)
        wait(1.0)
        # Move back outside and attack
        pos_m = convert_abs_to_monitor((-430, 230))
        self.pre_move()
        self.move(pos_m, force_move=True)
        self._blizzard((-50, -150), spray=30)
        self._cast_static()
        wait(0.5)
        # Move back inside and attack
        pos_m = convert_abs_to_monitor((150, -350))
        self.pre_move()
        self.move(pos_m, force_move=True)
        # Attack sequence center
        self._blizzard((-100, 35), spray=30)
        self._cast_static()
        self._blizzard((-150, 20), spray=30)
        wait(1.0)
        # Move inside
        pos_m = convert_abs_to_monitor((100, -30))
        self.pre_move()
        self.move(pos_m, force_move=True)
        # Attack sequence to center
        self._blizzard((-50, 50), spray=30)
        self._cast_static()
        self._ice_blast((-30, 50), spray=10)
        # Move outside since the trav.py expects to start searching for items there if char can teleport
        self._pather.traverse_nodes([226], self, timeout=2.5, force_tp=True)
        return True

    def kill_nihlathak(self, end_nodes: list[int]) -> bool:
        self._found_monster_bar = 0
        self._monster_gone_cnt = 0
        self._name_bar_gone_cnt = -1
        self._immunities = ''
        # Find nilhlatak position
        atk_len = Config().char["atk_len_nihlathak"]
        cast_pos_abs = None
        for i in range(int(atk_len)):
            nihlathak_pos_abs = self._pather.find_abs_node_pos(end_nodes[-1], grab())
            if nihlathak_pos_abs is not None:
                cast_pos_abs = nihlathak_pos_abs
            if cast_pos_abs is not None:
                curr_time = time.time()
                Logger.info(f"Cast blizzard at {cast_pos_abs}")
                self._blizzard(cast_pos_abs, spray=0)
                found_nihl = self.find_name_bar(grab(), "nihlathak")
                if found_nihl:
                    Logger.info("Found Nihlathak!")
                    if 'c' in self._immunities:
                        if self._secondary_skill == self._static_field:
                            Logger.info("Cold Immune! - Exiting")
                        elif self._ranged_secondary:
                            self._secondary_skill(cast_pos_abs, atk_len + 2)
                            self._pather.traverse_nodes(end_nodes, self, timeout=0.8)
                            return True
                        else:
                            node = convert_abs_to_monitor(cast_pos_abs)
                            self.select_tp()
                            self.move(node, force_tp = True)
                            self._secondary_skill(atk_len)
                            return True
                        return False
                delta = time.time() - curr_time
                if delta < 1.85:
                    time.sleep(1.85 - delta)
            else:
                time.sleep(0.2)

        if self._ranged_secondary:
            self._secondary_skill(cast_pos_abs, atk_len * 0.5)
        self._pather.traverse_nodes(end_nodes, self, timeout=0.8)
        if not self._ranged_secondary:
            self._secondary_skill(atk_len)
        return True

    def kill_summoner(self) -> bool:
        # Attack
        cast_pos_abs = np.array([0, 0])
        pos_m = convert_abs_to_monitor((-20, 20))
        mouse.move(*pos_m, randomize=80, delay_factor=[0.5, 0.7])
        for _ in range(int(Config().char["atk_len_arc"])):
            self._blizzard(cast_pos_abs, spray=11)
            self._ice_blast(cast_pos_abs, spray=11)
        wait(self._cast_duration, self._cast_duration + 0.2)
        return True


if __name__ == "__main__":
    import os
    import keyboard
    import template_finder
    from pather import Pather
    keyboard.add_hotkey('f12', lambda: Logger.info('Force Exit (f12)') or os._exit(1))
    keyboard.wait("f11")
    from config import Config
    pather = Pather()
    char = BlizzSorc(Config().blizz_sorc, Config().char, pather)
    char.kill_council()
