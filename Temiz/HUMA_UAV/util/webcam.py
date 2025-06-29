import cv2
import sys
import threading

class WebcamVideoStream:
    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src)
        if not self.stream.isOpened():
            print("Could not open video stream")
            sys.exit()
        (self.grabbed, self.frame) = self.stream.read()
        self.stopped = False

    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            (self.grabbed, self.frame) = self.stream.read()
            if not self.grabbed:
                self.stop()
                break

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()
