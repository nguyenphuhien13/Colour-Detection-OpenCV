import json
import threading
import time
#import urllib.request as rq

import cv2
import numpy

WINDOW_NAME = "Gripper Car"

CAMERA_IP = "http://192.168.43.21:8080/video"
ESP8266_IP = "http://192.168.43.13/"

SAMPLE_SIZE = 10
TRIANGLE_SIZE = SAMPLE_SIZE

step_duration = 80      #one step duration
is_automatic = False    #automatic or manual mode
is_detecting = False    #detecting
is_pause = False           #pause screen
camera = cv2.VideoCapture(CAMERA_IP)  #connecting to camera
cv2.namedWindow(WINDOW_NAME)

current_command = ""
delay_time = 0
motor_speed = 1000      #speed (1-1023)
last_time = time.time()
screen_width = 0
screen_height = 0

upper_color = (0, 0, 0)
lower_color = (0, 0, 0)
hue = 0


def hex_to_bgr(colorStr):
    return int(colorStr[5:7], 16), int(colorStr[3:5], 16), int(colorStr[1:3], 16)


def to_opencv_hsv(h, s, v):
    return h / 2, s * 2.55, v * 2.55


def from_opencv_hsv(h, s, v):
    return h * 2, s / 2.55, v / 2.55


def bound(x, _min, _max):
    if x > _max:
        return _max
    if x < _min:
        return _min
    return x


LIGHT_BLUE = hex_to_bgr("#03A8F3")
RED = hex_to_bgr("#F34236")
PINK = hex_to_bgr("#E81E62")
PURPLE = hex_to_bgr("#9B27AF")
TEAL = hex_to_bgr("#009587")
YELLOW = hex_to_bgr("#FEEA3B")
GREEN = hex_to_bgr("#4BAE4F")

bgr_color = RED


def _left(l):
    global left_range
    left_range = l


def _right(r):
    global right_range
    right_range = r


def _duration(a):
    global step_duration
    step_duration = a


def _motor_speed(s):
    global motor_speed
    motor_speed = s
    request_command("speed?speed=" + str(s), 20)


def draw_triangle(img, x, y, color):
    cv2.line(img, (int(x - TRIANGLE_SIZE), int(y)), (int(x + TRIANGLE_SIZE), int(y)), color, 1, cv2.LINE_AA)
    cv2.line(img, (int(x), int(y - TRIANGLE_SIZE)), (int(x + TRIANGLE_SIZE), int(y)), color, 1, cv2.LINE_AA)
    cv2.line(img, (int(x - TRIANGLE_SIZE), int(y)), (int(x), int(y - TRIANGLE_SIZE)), color, 1, cv2.LINE_AA)


def setup_screen():
    global screen_width, screen_height, left_range, right_range
    _, frame = camera.read()
    screen_width = len(frame[0])
    screen_height = len(frame)
    RANGE = screen_width / 15
    left_range = screen_width / 2 - RANGE
    right_range = screen_width / 2 + RANGE
    cv2.createTrackbar('Left', WINDOW_NAME, int(left_range), int(screen_width), _left)
    cv2.createTrackbar('Right', WINDOW_NAME, int(right_range), int(screen_width), _right)
    cv2.createTrackbar('Speed', WINDOW_NAME, motor_speed, 1023, _motor_speed)
    cv2.createTrackbar('Duration', WINDOW_NAME, step_duration, step_duration * 3, _duration)


def bound_HSV(h, s, v):
    return numpy.array([bound(h, 1, 179), bound(s, 1, 255), bound(v, 1, 255)])


def toIntArray(a):
    return numpy.array(a, numpy.int32)


def get_average_color(img, contours, index):
    buffer = numpy.zeros_like(img)
    cv2.drawContours(buffer, contours, index, 255, thickness=-1)
    pts = numpy.where(buffer == 255)
    ls = img[pts[0], pts[1], 0]
    return numpy.average(ls)


def match(a, b):
    return abs(a - b)


def command_manager():
    global current_command, delay_time
    while True:
        if current_command != "":   #waiting for command
            print("Will send cmd", ESP8266_IP + current_command)
            try:
                rq.urlopen(ESP8266_IP + current_command).read() #send command
            except Exception as err:
                print("Not connected", err)
            current_command = ""
            curr = delay_time
            delay_time = 0
            time.sleep(curr / 1000 + 0.1)
        else:
            time.sleep(0.01)


def gripper_manager():
    global is_automatic
    while True:
        if is_automatic:
            try:
                data = rq.urlopen(ESP8266_IP + "fc51").read()   #read signal from sensor
                js = json.loads(data.decode())
                if js["detect"] == 0:       #dectected
                    rq.urlopen(ESP8266_IP + "close").read() #close grippers
                    is_automatic = False
                    time.sleep(0.2)
                    request_command("move?command=backward", 1000)  #move backwards in 1s
                    time.sleep(2)   #chờ 2s
                rq.urlopen(ESP8266_IP + "gripper?command=set&angle=100").read() #open grippers
            except Exception as err:
                print("Not connected", err)
        time.sleep(0.3)


def start_connects():
    threading.Thread(target=command_manager).start() #starting motors
    threading.Thread(target=gripper_manager).start() #starting grippers


def request_command(cmd, duration=-1):
    global current_command, delay_time
    if duration == -1:
        duration = step_duration
    delay_time = duration
    current_command = cmd + "&duration=" + str(delay_time)


def capture_color(frame):
    global bgr_color, upper_color, lower_color, hue
    sample = frame[int(screen_height / 2 - SAMPLE_SIZE):int(screen_height / 2 + SAMPLE_SIZE),
             int(screen_width / 2 - SAMPLE_SIZE):int(screen_width / 2 + SAMPLE_SIZE)]
    bgr_color = (numpy.average(sample[:, :, 0]), numpy.average(sample[:, :, 1]), numpy.average(sample[:, :, 2]))
    hsv_color = cv2.cvtColor(numpy.array([[bgr_color]], dtype=numpy.uint8), cv2.COLOR_BGR2HSV)[0][0]
    hue, s, v = hsv_color
    upper_color = bound_HSV(hue + 20, 255, 255)
    lower_color = bound_HSV(hue - 20, s - 40, v - 60)
    print("Capture color", from_opencv_hsv(hue, s, v))
    print("avg bgr", bgr_color, "avg hsv", from_opencv_hsv(*hsv_color))
    print("upper", from_opencv_hsv(*upper_color), "lower", from_opencv_hsv(*lower_color))
    print("hsv opencv", hue, s, v)
    print("upper opencv", upper_color, "lower opencv", lower_color)
    print("")


def process_keystroke(frame):
    global is_automatic, is_detecting, is_pause
    k = chr(cv2.waitKey(1) & 0xFF)
    if k == ' ':
        capture_color(frame)    
        is_detecting = True
    elif k == 'z':
        is_automatic = not is_automatic
    elif k == 'q':  
        finish()
    elif k == 'x':
        is_detecting = not is_detecting
    elif k == 'w':
        request_command("move?command=forward")
    elif k == 'a':
        request_command("move?command=left")
    elif k == 's':
        request_command("move?command=backward")
    elif k == 'd':
        request_command("move?command=right")
    elif k == 'o':
        rq.urlopen(ESP8266_IP + "gripper?command=set&angle=100").read()
    elif k == 'i':
        request_command("gripper?command=close")
    elif k == 'm':
        is_pause = not is_pause


def main_loop():
    frame = None
    while True:
        if not is_pause:
            _, frame = camera.read()    #get images from stream
            process_keystroke(frame)    #execute keystroke
            left_color = LIGHT_BLUE
            right_color = LIGHT_BLUE
            if is_detecting:
                best_contour = get_best_contour(frame) #finding object
                if best_contour is not None:
                    rect = cv2.minAreaRect(best_contour)    #finding rectangular shape on the object
                    draw_box(frame, rect)                   #drawing rectangular shape
                    x_pos = int(rect[0][0])                 #coordinates of rectangular shape
                    y_pos = int(rect[0][1])
                    cv2.line(frame, (int(screen_width / 2), int(screen_height / 2)), (x_pos, y_pos),
                             RED, 1, cv2.LINE_AA)

                    if x_pos < left_range:      #object is on the left => turn left
                        left_color = RED
                        if is_automatic:
                            request_command("move?command=left&mode2=1")
                    elif x_pos > right_range:   #object is on the right => turn right
                        if is_automatic:
                            request_command("move?command=right&mode2=1")
                        right_color = RED
                    else:                       #go straight
                        left_color = YELLOW
                        right_color = YELLOW
                        if is_automatic:
                            request_command("move?command=forward")
            draw_triangle(frame, left_range, screen_height / 2, left_color)     #drawing left triangle
            draw_triangle(frame, right_range, screen_height / 2, right_color) #drawing right triangle
            draw_reticle(frame) #drawing vertical and horizontal lines, central square box
            draw_info(frame)    #displaying 
        else:
            process_keystroke(frame)
            time.sleep(0.3)
        cv2.imshow(WINDOW_NAME, frame)      #displaying on windows


def draw_box(frame, rect):
    ps = toIntArray(cv2.boxPoints(rect))
    cv2.polylines(frame, [ps.reshape((-1, 1, 2))], True, RED, 1, cv2.LINE_AA)


def draw_info(frame):
    fps = camera.get(cv2.CAP_PROP_FPS)
    if is_automatic:
        connect = "Automatic"
    else:
        connect = "Manual"
    if is_detecting:
        detect = "Detecting"
    else:
        detect = "Not detecting"
    cv2.putText(frame,
                "%dx%dx%dFPS: - %s - %s - Step: %d ms " % (
                    screen_width, screen_height, int(fps), connect, detect, int(step_duration)),
                (20, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5, LIGHT_BLUE, 1, cv2.LINE_AA)


def draw_reticle(frame):
    cv2.line(frame, (0, int(screen_height / 2)), (screen_width, int(screen_height / 2)), LIGHT_BLUE, 1, cv2.LINE_AA)
    cv2.line(frame, (int(screen_width / 2), 0), (int(screen_width / 2), screen_height), LIGHT_BLUE, 1, cv2.LINE_AA)
    cv2.rectangle(frame, (int(screen_width / 2 - SAMPLE_SIZE), int(screen_height / 2 - SAMPLE_SIZE)),
                  (int(screen_width / 2 + SAMPLE_SIZE), int(screen_height / 2 + SAMPLE_SIZE)), LIGHT_BLUE, 1,
                  cv2.LINE_AA)


def get_best_contour(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)            #converting to HSV
    mask = cv2.inRange(hsv, lower_color, upper_color)       #obtaining the mask
    mask = cv2.erode(mask, None, iterations=SAMPLE_SIZE)    #lọc các điểm nhỏ hơn kích cỡ lấy mẫu (sieve out points that are unrelated)
    mask = cv2.dilate(mask, None, iterations=SAMPLE_SIZE)
    contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
    cv2.drawContours(frame, contours, -1, GREEN, 2, cv2.LINE_AA)

    biggest_area = -1
    biggest_contour = None

    for index, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        if (SAMPLE_SIZE * SAMPLE_SIZE * 4) < area > biggest_area:
            biggest_area = area
            biggest_contour = contour
    return biggest_contour


def finish(): 
    camera.release()
    cv2.destroyAllWindows()
    exit()

#program
setup_screen()
start_connects()
main_loop()
