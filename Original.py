import cv2
import mediapipe as mp
import numpy as np
import winsound
import threading
import os
import time
from PIL import Image, ImageDraw, ImageFont

class ElementGame:
    def __init__(self, cap, width, height):
        self.cap = cap
        self.width = width
        self.height = height
        self.square_size = min(width, height) // 4
        
        # Initialize MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(static_image_mode=False, max_num_hands=2, min_detection_confidence=0.5)
        
        # Initialize MediaPipe Selfie Segmentation
        self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
        self.selfie_segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=0)
        
        # Initialize drawing utilities
        self.mp_drawing = mp.solutions.drawing_utils
        
        self.squares = {
            '🔥': {'color': (255, 0, 0), 'position': (0, 0), 'sound': 'C:/Users/dsrus/Desktop/Workspace/4elements/Sounds/fireplace-6160.wav'},
            '💨': {'color': (0, 215, 255), 'position': (width - self.square_size, 0), 'sound': 'C:/Users/dsrus/Desktop/Workspace/4elements/Sounds/air.wav'},
            '🌊': {'color': (0, 0, 255), 'position': (0, height - self.square_size), 'sound': 'C:/Users/dsrus/Desktop/Workspace/4elements/Sounds/water.wav'},
            '🌱': {'color': (0, 128, 128), 'position': (width - self.square_size, height - self.square_size), 'sound': 'C:/Users/dsrus/Desktop/Workspace/4elements/Sounds/earth.wav'}
        }
        
        self.gold_box = {'color': (255, 255, 0), 'position': ((width - self.square_size) // 2, height - self.square_size)}
        self.eureka_sound = 'C:/Users/dsrus/Desktop/Workspace/4elements/Sounds/Eureka.wav'
        
        self.sound_played = {element: False for element in self.squares}
        self.finger_in_box = {element: False for element in self.squares}
        self.last_sound_time = {element: 0 for element in self.squares}
        
        self.grabbed_word = None
        self.gold_achieved = False
        self.mask_color = None
        
        self.current_sound = None
        self.fire_sound_playing = False
        
        self.emoji_font = ImageFont.truetype("seguiemj.ttf", 48)
        
        self.reset_word_positions()

    def reset_word_positions(self):
        self.word_positions = {element: (info['position'][0] + self.square_size // 2, info['position'][1] + self.square_size // 2) 
                               for element, info in self.squares.items()}
        self.gold_achieved = False
        self.grabbed_word = None
        self.mask_color = None
        self.stop_fire_sound()

    def is_hand_closed(self, hand_landmarks):
        thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
        index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
        return (thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2 < 0.01

    def is_point_in_box(self, point, box_position, box_size):
        return (box_position[0] < point[0] < box_position[0] + box_size and
                box_position[1] < point[1] < box_position[1] + box_size)

    def play_sound(self, sound_file):
        def play():
            try:
                if not os.path.exists(sound_file):
                    print(f"Error: Sound file not found: {sound_file}")
                    return
                if sound_file == self.squares['🔥']['sound']:
                    winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
                    self.fire_sound_playing = True
                else:
                    winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
                print(f"Played sound: {sound_file}")
            except Exception as e:
                print(f"Error playing sound {sound_file}: {e}")

        if self.current_sound:
            winsound.PlaySound(None, winsound.SND_PURGE)
            self.fire_sound_playing = False
        self.current_sound = sound_file
        threading.Thread(target=play, daemon=True).start()

    def stop_fire_sound(self):
        if self.fire_sound_playing:
            winsound.PlaySound(None, winsound.SND_PURGE)
            self.fire_sound_playing = False
            self.current_sound = None

    def apply_mask(self, image_rgb):
        results = self.selfie_segmentation.process(image_rgb)
        condition = np.stack((results.segmentation_mask,) * 3, axis=-1) > 0.1
        if self.mask_color is not None:
            overlay = np.zeros(image_rgb.shape, dtype=np.uint8)
            overlay[:] = self.mask_color
            overlay = cv2.addWeighted(image_rgb, 0.8, overlay, 0.2, 0)
            image_rgb = np.where(condition, overlay, image_rgb)
        return image_rgb

    def process_frame(self, frame):
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(image_rgb)

        # Apply mask first
        image_rgb = self.apply_mask(image_rgb)

        overlay = image_rgb.copy()
        for element, info in self.squares.items():
            cv2.rectangle(overlay, info['position'], 
                          (info['position'][0] + self.square_size, info['position'][1] + self.square_size), 
                          info['color'], -1)
        cv2.addWeighted(overlay, 0.25, image_rgb, 0.75, 0, image_rgb)

        cv2.rectangle(overlay, self.gold_box['position'], 
                      (self.gold_box['position'][0] + self.square_size, self.gold_box['position'][1] + self.square_size), 
                      self.gold_box['color'], -1)
        cv2.addWeighted(overlay, 0.25, image_rgb, 0.75, 0, image_rgb)

        pil_image = Image.fromarray(image_rgb)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    image_rgb, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=4),
                    self.mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=2)
                )
                
                index_finger_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
                x, y = int(index_finger_tip.x * self.width), int(index_finger_tip.y * self.height)

                hand_closed = self.is_hand_closed(hand_landmarks)

                if self.grabbed_word:
                    if hand_closed:
                        self.word_positions[self.grabbed_word] = (x, y)
                    else:
                        if self.is_point_in_box((x, y), self.gold_box['position'], self.square_size):
                            self.mask_color = self.squares[self.grabbed_word]['color']
                            if self.grabbed_word == '🔥':
                                self.play_sound(self.squares['🔥']['sound'])
                            else:
                                self.stop_fire_sound()
                            
                            # Check if all emojis are in the gold box
                            emojis_in_gold = sum(1 for pos in self.word_positions.values() 
                                                 if self.is_point_in_box(pos, self.gold_box['position'], self.square_size))
                            if emojis_in_gold == 4:
                                self.gold_achieved = True
                                self.gold_box['color'] = (255, 255, 0)  # Gold color
                                self.play_sound(self.eureka_sound)
                            else:
                                self.gold_box['color'] = self.mask_color
                        self.grabbed_word = None
                else:
                    for element, info in self.squares.items():
                        if self.is_point_in_box((x, y), info['position'], self.square_size):
                            current_time = time.time()
                            if not self.finger_in_box[element]:
                                print(f"Touch detected in {element} square")
                                self.finger_in_box[element] = True
                                if current_time - self.last_sound_time[element] > 1:  # 1 second cooldown
                                    print(f"Attempting to play sound for {element}")
                                    if element != '🔥':
                                        self.play_sound(info['sound'])
                                    self.last_sound_time[element] = current_time
                            if hand_closed and not self.grabbed_word:
                                self.grabbed_word = element
                        else:
                            self.finger_in_box[element] = False

        for element, position in self.word_positions.items():
            draw = ImageDraw.Draw(pil_image)
            draw.text((position[0], position[1]), element, font=self.emoji_font, fill=(255, 255, 255), anchor="mm")

        return np.array(pil_image)

class CameraManager:
    def __init__(self, cap):
        self.cap = cap
        self.is_game_view = True

    def switch_view(self):
        self.is_game_view = not self.is_game_view
        print(f"Switched to {'game' if self.is_game_view else 'mask'} view")

class MainProgram:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        ret, frame = self.cap.read()
        self.height, self.width = frame.shape[:2]
        self.game = ElementGame(self.cap, self.width, self.height)
        self.camera_manager = CameraManager(self.cap)

    def run(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to capture frame")
                break

            frame = cv2.flip(frame, 1)

            if self.camera_manager.is_game_view:
                image_rgb = self.game.process_frame(frame)
            else:
                image_rgb = self.game.apply_mask(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
            cv2.imshow('Camera View', image_bgr)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                self.game.reset_word_positions()
                print("Game reset!")
            elif key == ord('s'):
                self.camera_manager.switch_view()

        self.game.stop_fire_sound()
        self.cap.release()
        cv2.destroyAllWindows()
        winsound.PlaySound(None, winsound.SND_PURGE)

if __name__ == "__main__":
    program = MainProgram()
    program.run()