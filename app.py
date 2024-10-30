from flask import Flask, render_template, request, jsonify
import cv2
import mediapipe as mp
import numpy as np
import base64
import io
import logging
from PIL import Image, ImageDraw, ImageFont
import time
import os

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class WebElementGame:
    def __init__(self):
        self.width = 640  # Standard webcam width
        self.height = 480  # Standard webcam height
        self.square_size = min(self.width, self.height) // 4
        
        # Initialize MediaPipe
        logger.debug("Setting up MediaPipe")
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5
        )
        
        # Initialize MediaPipe Selfie Segmentation
        self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
        self.selfie_segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=0)
        
        self.mp_drawing = mp.solutions.drawing_utils
        
        # Initialize squares with same colors and positions as original
        self.squares = {
            '🔥': {
                'color': (255, 0, 0),
                'position': (0, 0),
                'sound': 'fireplace-6160.wav'
            },
            '💨': {
                'color': (0, 215, 255),
                'position': (self.width - self.square_size, 0),
                'sound': 'air.wav'
            },
            '🌊': {
                'color': (0, 0, 255),
                'position': (0, self.height - self.square_size),
                'sound': 'water.wav'
            },
            '🌱': {
                'color': (0, 128, 128),
                'position': (self.width - self.square_size, self.height - self.square_size),
                'sound': 'earth.wav'
            }
        }
        
        self.gold_box = {
            'color': (255, 255, 0),
            'position': ((self.width - self.square_size) // 2, self.height - self.square_size)
        }
        
        # Initialize state tracking
        self.finger_in_box = {element: False for element in self.squares}
        self.last_sound_time = {element: 0 for element in self.squares}
        self.grabbed_word = None
        self.gold_achieved = False
        self.mask_color = None
        
        # Load emoji font
        logger.debug("Loading emoji font")
        try:
            self.emoji_font = ImageFont.truetype("seguiemj.ttf", 48)
            logger.debug("Emoji font loaded successfully")
        except Exception as e:
            logger.error(f"Error loading emoji font: {e}")
            raise
            
        self.reset_word_positions()

    def reset_word_positions(self):
        self.word_positions = {
            element: (info['position'][0] + self.square_size // 2,
                     info['position'][1] + self.square_size // 2)
            for element, info in self.squares.items()
        }
        self.gold_achieved = False
        self.grabbed_word = None
        self.mask_color = None

    def is_hand_closed(self, hand_landmarks):
        thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
        index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
        return (thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2 < 0.01

    def is_point_in_box(self, point, box_position, box_size):
        return (box_position[0] < point[0] < box_position[0] + box_size and
                box_position[1] < point[1] < box_position[1] + box_size)

    def apply_mask(self, image_rgb):
        results = self.selfie_segmentation.process(image_rgb)
        condition = np.stack((results.segmentation_mask,) * 3, axis=-1) > 0.1
        if self.mask_color is not None:
            overlay = np.zeros(image_rgb.shape, dtype=np.uint8)
            overlay[:] = self.mask_color
            overlay = cv2.addWeighted(image_rgb, 0.8, overlay, 0.2, 0)
            image_rgb = np.where(condition, overlay, image_rgb)
        return image_rgb

    def process_frame(self, frame_data):
        try:
            # Decode base64 image
            image_data = base64.b64decode(frame_data.split(',')[1])
            nparr = np.frombuffer(image_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(image_rgb)
            
            # Apply mask first
            image_rgb = self.apply_mask(image_rgb)
            
            # Draw squares
            overlay = image_rgb.copy()
            for element, info in self.squares.items():
                cv2.rectangle(overlay, info['position'],
                            (info['position'][0] + self.square_size,
                             info['position'][1] + self.square_size),
                            info['color'], -1)
            cv2.addWeighted(overlay, 0.25, image_rgb, 0.75, 0, image_rgb)
            
            # Draw gold box
            cv2.rectangle(overlay, self.gold_box['position'],
                         (self.gold_box['position'][0] + self.square_size,
                          self.gold_box['position'][1] + self.square_size),
                         self.gold_box['color'], -1)
            cv2.addWeighted(overlay, 0.25, image_rgb, 0.75, 0, image_rgb)
            
            sound_events = []
            current_time = time.time()

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
                                    sound_events.append(self.squares['🔥']['sound'])
                                
                                # Check if all emojis are in gold box
                                emojis_in_gold = sum(1 for pos in self.word_positions.values()
                                                   if self.is_point_in_box(pos, self.gold_box['position'], self.square_size))
                                if emojis_in_gold == 4:
                                    self.gold_achieved = True
                                    self.gold_box['color'] = (255, 255, 0)
                                    sound_events.append('Eureka.wav')
                                else:
                                    self.gold_box['color'] = self.mask_color
                            self.grabbed_word = None
                    else:
                        for element, info in self.squares.items():
                            if self.is_point_in_box((x, y), info['position'], self.square_size):
                                if not self.finger_in_box[element]:
                                    self.finger_in_box[element] = True
                                    if current_time - self.last_sound_time[element] > 1:
                                        if element != '🔥':
                                            sound_events.append(info['sound'])
                                        self.last_sound_time[element] = current_time
                                if hand_closed and not self.grabbed_word:
                                    self.grabbed_word = element
                            else:
                                self.finger_in_box[element] = False

            # Draw emojis
            pil_image = Image.fromarray(image_rgb)
            draw = ImageDraw.Draw(pil_image)
            for element, position in self.word_positions.items():
                draw.text((position[0], position[1]), element,
                         font=self.emoji_font, fill=(255, 255, 255), anchor="mm")

            # Convert back to base64
            buffered = io.BytesIO()
            pil_image.save(buffered, format="JPEG", quality=95)
            img_str = base64.b64encode(buffered.getvalue()).decode()

            return {
                'success': True,
                'image': f'data:image/jpeg;base64,{img_str}',
                'sound_events': sound_events,
                'gold_achieved': self.gold_achieved
            }

        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return {'success': False, 'error': str(e)}

app = Flask(__name__)
game = WebElementGame()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_frame', methods=['POST'])
def process_frame():
    try:
        data = request.get_json()
        if not data or 'frame' not in data:
            return jsonify({'success': False, 'error': 'No frame data received'})
        
        result = game.process_frame(data['frame'])
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in process_frame route: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/reset_game', methods=['POST'])
def reset_game():
    try:
        game.reset_word_positions()
        # Reset additional game state if needed
        game.mask_color = None
        game.gold_achieved = False
        game.grabbed_word = None
        game.finger_in_box = {element: False for element in game.squares}
        game.last_sound_time = {element: 0 for element in game.squares}
        
        return jsonify({
            'success': True,
            'message': 'Game reset successfully'
        })
    except Exception as e:
        logger.error(f"Error resetting game: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True)