# Copyright 2023 The MediaPipe Authors. All Rights Reserved.
# ... (License header omitted) ...

import argparse
import sys
import time
import cv2
import mediapipe as mp
import serial  # UART 통신을 위한 라이브러리

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Global variables
COUNTER, FPS = 0, 0
START_TIME = time.time()
IS_PROCESSING = False
recognition_result_list = []

# --- [설정] 제스처 별 명령어 매핑 ---
# None 제외, 실제 동작 제스처만 정의
GESTURE_MAP = {
    "Thumb_Up":    (60, 0),     # 전진
    "Thumb_Down":  (-60, 0),    # 후진
    "Closed_Fist": (0, 0),      # 멈춤
    "Pointing_Up": (0, -100),   # 왼쪽
    "Victory":     (0, 100),    # 오른쪽
    "Open_Palm":   (0, 0)       # 가운데 (중립)
}

def make_packet(throttle, steer):
    """
    Protocol: $CMD,THROTTLE,STEER\n
    """
    return f"$CMD,{throttle},{steer}\n"

def run(model: str, num_hands: int,
        min_hand_detection_confidence: float,
        min_hand_presence_confidence: float, min_tracking_confidence: float,
        camera_id: int, width: int, height: int) -> None:
    
    global IS_PROCESSING, FPS, COUNTER, START_TIME

    # 1. UART 시리얼 포트 초기화
    try:
        # Raspberry Pi 기본 시리얼 포트: /dev/serial0
        # Baudrate: 115200 (명세서 기준)
        ser = serial.Serial('/dev/serial0', 115200, timeout=1)
        ser.flush() # 버퍼 비우기
        print(f"Success: Serial port opened (/dev/serial0, 115200bps)")
    except Exception as e:
        print(f"Error: Failed to open serial port. {e}")
        sys.exit(1)

    # 2. 카메라 초기화
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    fps_avg_frame_count = 10

    # UART 전송 헬퍼 함수 (내부 함수로 정의하여 ser 객체 사용)
    def send_command_via_uart(category_name):
        if category_name in GESTURE_MAP:
            throttle, steer = GESTURE_MAP[category_name]
            packet = make_packet(throttle, steer)
            
            try:
                # 패킷 전송 (Encode to bytes)
                ser.write(packet.encode())
                
                # 로그 출력
                print(f"Detect: {category_name:12} >> TX: {packet.strip()}")
            except serial.SerialException as e:
                print(f"UART Error: {e}")

    # MediaPipe 결과 콜백
    def save_result(result: vision.GestureRecognizerResult,
                    unused_output_image: mp.Image, timestamp_ms: int):
        global FPS, COUNTER, START_TIME, IS_PROCESSING

        if COUNTER % fps_avg_frame_count == 0:
            FPS = fps_avg_frame_count / (time.time() - START_TIME)
            START_TIME = time.time()

        recognition_result_list.append(result)
        COUNTER += 1
        IS_PROCESSING = False

    # MediaPipe 초기화
    base_options = python.BaseOptions(model_asset_path=model)
    options = vision.GestureRecognizerOptions(base_options=base_options,
                                            running_mode=vision.RunningMode.LIVE_STREAM,
                                            num_hands=num_hands,
                                            min_hand_detection_confidence=min_hand_detection_confidence,
                                            min_hand_presence_confidence=min_hand_presence_confidence,
                                            min_tracking_confidence=min_tracking_confidence,
                                            result_callback=save_result)
    recognizer = vision.GestureRecognizer.create_from_options(options)

    print("=== Gesture Control Started (UART: ON) ===")
    
    try:
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                sys.exit('ERROR: Unable to read from webcam.')

            image = cv2.flip(image, 1)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

            # 비동기 추론 요청
            if not IS_PROCESSING:
                IS_PROCESSING = True
                recognizer.recognize_async(mp_image, time.time_ns() // 1_000_000)

            # 결과 처리
            if recognition_result_list:
                result = recognition_result_list[0]
                
                if result.gestures:
                    gesture = result.gestures[0][0]
                    category_name = gesture.category_name
                    
                    # None이 아니고, 정의된 제스처인 경우에만 전송
                    if category_name != "None" and category_name in GESTURE_MAP:
                        send_command_via_uart(category_name)
                    
                recognition_result_list.clear()
            
            # CPU 부하 감소
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    
    finally:
        recognizer.close()
        cap.release()
        if ser.is_open:
            ser.close()
        print("Resources released.")

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--model', required=False, default='gesture_recognizer.task')
    parser.add_argument('--numHands', required=False, default=1)
    parser.add_argument('--minHandDetectionConfidence', required=False, default=0.5)
    parser.add_argument('--minHandPresenceConfidence', required=False, default=0.5)
    parser.add_argument('--minTrackingConfidence', required=False, default=0.5)
    parser.add_argument('--cameraId', required=False, default=0)
    # 성능 최적화를 위해 해상도는 낮게 유지
    parser.add_argument('--frameWidth', required=False, default=320)
    parser.add_argument('--frameHeight', required=False, default=240)
    args = parser.parse_args()

    run(args.model, int(args.numHands), float(args.minHandDetectionConfidence),
        float(args.minHandPresenceConfidence), float(args.minTrackingConfidence),
        int(args.cameraId), int(args.frameWidth), int(args.frameHeight))

if __name__ == '__main__':
    main()
