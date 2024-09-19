import cv2


def check_camera(last_index):
    ok_camera_ids = []

    for camera_id in range(last_index):
        try:
            camera = cv2.VideoCapture(camera_id)
            if camera is None or not camera.isOpened():
                raise ConnectionError
            
            ok_camera_ids.append(camera_id)
            print(f"-*- DEVICE_ID: {camera_id} -*-")
            camera_info = camera.getBackendName()
            frame_width = int(camera.get(3))
            frame_height = int(camera.get(4))
            
            print(f"Camera ID: {camera_id}")
            print(f"Backend Name: {camera_info}")
            print(f"Resolution: {frame_width}x{frame_height}")

            display_camera_feed(camera, camera_id, frame_width, frame_height)

        except ConnectionError:
            print(f"Camera {camera_id} is not available.")
            continue

    return ok_camera_ids


def display_camera_feed(camera, camera_id, frame_width, frame_height):
    try:
        while True:
            ret, frame = camera.read()

            if not ret:
                print(f"Failed to capture from camera {camera_id}.")
                break

            cv2.imshow(f"Camera {camera_id} (W:{frame_width} x H:{frame_height})", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('s'):
                cv2.imwrite(f"captured_photo_camera_{camera_id}.jpg", frame)
                print(f"Photo captured from Camera {camera_id} and saved.")
                break
            elif key == ord('q'):
                print(f"Exiting from Camera {camera_id}.")
                break
    finally:
        camera.release()
        cv2.destroyWindow(f"Camera {camera_id} (W:{frame_width} x H:{frame_height})")


if __name__ == "__main__":
    max_camera_num = 2
    ok_camera_ids = check_camera(max_camera_num)

    # すべてのウィンドウを閉じる
    cv2.destroyAllWindows()