from flask import Flask, render_template, Response, jsonify
import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import base64
import io
import json
import os
from datetime import datetime

app = Flask(__name__)

class WebElementGame:
    def __init__(self):
        self.width = 640  # Default width
        self.height = 480  # Default height
        self.square_size = min(self.width, self.height) // 4
        
        # Initialize MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(static_image_mode=False, max_num_hands=2, min_detection_confidence=0.5)
        
        # Initialize MediaPipe Selfie Segmentation
        self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
        self.selfie_segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=0)
        
        # Initialize drawing utilities
        self.mp_drawing = mp.solutions.drawing_utils
        
        self.squares = {
            '🔥': {'color': (255, 0, 0), 'position': (0, 0)},
            '💨': {'color': (0, 215, 255), 'position': (self.width - self.square_size, 0)},
            '🌊': {'color': (0, 0, 255), 'position': (0, self.height - self.square_size)},
            '🌱': {'color': (0, 128, 128), 'position': (self.width - self.square_size, self.height - self.square_size)}
        }
        
        self.gold_box = {
            'color': (255, 255, 0), 
            'position': ((self.width - self.square_size) // 2, self.height - self.square_size)
        }
        
        self.word_positions = {
            element: (info['position'][0] + self.square_size // 2, info['position'][1] + self.square_size // 2) 
            for element, info in self.squares.items()
        }
        
        self.grabbed_word = None
        self.gold_achieved = False
        self.mask_color = None
        
        # Load emoji font
        self.emoji_font = ImageFont.truetype("seguiemj.ttf", 48)

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
        # Decode base64 image
        image_data = base64.b64decode(frame_data.split(',')[1])
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
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
        draw = ImageDraw.Draw(pil_image)

        hand_data = []
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
                
                hand_data.append({
                    'position': {'x': x, 'y': y},
                    'closed': hand_closed
                })

        # Draw emojis
        for element, position in self.word_positions.items():
            draw.text((position[0], position[1]), element, font=self.emoji_font, fill=(255, 255, 255), anchor="mm")

        # Convert back to base64
        buffered = io.BytesIO()
        pil_image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return {
            'image': f'data:image/jpeg;base64,{img_str}',
            'hands': hand_data,
            'goldAchieved': self.gold_achieved
        }

# Initialize game
game = WebElementGame()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_frame', methods=['POST'])
def process_frame():
    data = request.get_json()
    frame_data = data['frame']
    result = game.process_frame(frame_data)
    return jsonify(result)

@app.route('/reset_game', methods=['POST'])
def reset_game():
    game.reset_word_positions()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
"""


# Modify app.py to add debug mode
if __name__ == '__main__':
    app.run(debug=True)
"""