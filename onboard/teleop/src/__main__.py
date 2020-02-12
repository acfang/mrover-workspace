import asyncio
import math
from rover_common import heartbeatlib, aiolcm
from rover_common.aiohelper import run_coroutines
from rover_msgs import (Joystick, DriveMotors, KillSwitch,
                        Xbox, Temperature, ArmToggles,
                        RAOpenLoopCmd, SAOpenLoopCmd,
                        GimbalCmd, HandCmd, Keyboard)


class Toggle:

    def __init__(self, toggle):
        self.toggle = toggle
        self.previous = False
        self.input = False
        self.last_input = False

    def new_reading(self, reading):
        self.input = reading
        if self.input and not self.last_input:
            # just pushed
            self.last_input = True
            self.toggle = not self.toggle
        elif not self.input and self.last_input:
            # just released
            self.last_input = False

        self.previous = reading
        return self.toggle


lcm_ = aiolcm.AsyncLCM()
prev_killed = False
kill_motor = False
lock = asyncio.Lock()
front_drill_on = Toggle(False)
back_drill_on = Toggle(False)
connection = None
# front_drone_on = Toggle(False)
# back_drone_on = Toggle(False)
electromagnet_toggle = Toggle(False)
laser_toggle = Toggle(False)
solenoid_on = Toggle(False)
electromagnet_on = Toggle(False)
laser_on = Toggle(False)


def send_drive_kill():
    drive_motor = DriveMotors()
    drive_motor.left = 0.0
    drive_motor.right = 0.0

    lcm_.publish('/motor', drive_motor.encode())


def send_arm_kill():
    arm_motor = RAOpenLoopCmd()
    arm_motor.throttle = [0.0,0.0,0.0,0.0,0.0,0.0]
    lcm_.publish('/ra_openloop_cmd', arm_motor.encode())


def send_sa_kill():
    sa_motor = SAOpenLoopCmd()
    sa_motor.throttle = [0.0,0.0,0.0]

    lcm_.publish('/sa_openloop_cmd', sa_motor.encode())


def connection_state_changed(c, _):
    global kill_motor, prev_killed, connection
    if c:
        print("Connection established.")
        kill_motor = prev_killed
        connection = True
    else:
        connection = False
        print("Disconnected.")
        prev_killed = kill_motor
        send_drive_kill()
        send_arm_kill()
        send_sa_kill()


def quadratic(val):
    return math.copysign(val**2, val)


def deadzone(magnitude, threshold):
    temp_mag = abs(magnitude)
    if temp_mag <= threshold:
        temp_mag = 0
    else:
        temp_mag = (temp_mag - threshold)/(1 - threshold)

    return math.copysign(temp_mag, magnitude)


def joystick_math(new_motor, magnitude, theta):
    new_motor.left = abs(magnitude)
    new_motor.right = new_motor.left

    if theta > 0:
        new_motor.right *= 1 - (theta * 0.75)
    elif theta < 0:
        new_motor.left *= 1 + (theta * 0.75)

    if magnitude < 0:
        new_motor.left *= -1
        new_motor.right *= -1
    elif magnitude == 0:
        new_motor.left += theta
        new_motor.right -= theta


def drive_control_callback(channel, msg):
    global kill_motor, connection

    if not connection:
        return

    input_data = Joystick.decode(msg)

    if input_data.kill:
        kill_motor = True
    elif input_data.restart:
        kill_motor = False

    if kill_motor:
        send_drive_kill()
    else:
        new_motor = DriveMotors()
        input_data.forward_back = -quadratic(input_data.forward_back)
        magnitude = deadzone(input_data.forward_back, 0.04)
        theta = deadzone(input_data.left_right, 0.1)

        joystick_math(new_motor, magnitude, theta)

        damp = (input_data.dampen - 1)/(-2)
        new_motor.left *= damp
        new_motor.right *= damp

        lcm_.publish('/motor', new_motor.encode())


def ra_control_callback(channel, msg):
    xboxData = Xbox.decode(msg)

    motor_speeds = [-deadzone(quadratic(xboxData.left_js_x), 0.09)*0.5,
                    -deadzone(quadratic(xboxData.left_js_y), 0.09)*0.5,
                    quadratic(xboxData.left_trigger -
                              xboxData.right_trigger)*0.6,
                    deadzone(quadratic(xboxData.right_js_y), 0.09)*0.75,
                    deadzone(quadratic(xboxData.right_js_x), 0.09)*0.75,
                    (xboxData.d_pad_right-xboxData.d_pad_left)*0.6]

    openloop_msg = RAOpenLoopCmd()
    openloop_msg.throttle = motor_speeds

    lcm_.publish('/ra_openloop_cmd', openloop_msg.encode())

    hand_msg = HandCmd()
    hand_msg.finger = xboxData.y - xboxData.a
    hand_msg.grip = xboxData.b - xboxData.x

    lcm_.publish('/hand_openloop_cmd', hand_msg.encode())

    # send_arm_toggles = false
    # # if this.controlMode == 'arm':
    #     send_arm_toggles = true

    # elif this.controlMode == 'arm_ik':
    #     send_arm_toggles = true

    #     speed = 0.05;
    #     deltaPos = {
    #         'type': 'IkArmControl',
    #         'deltaX': -deadzone(quadratic(xboxData.left_js_y),
    #                             0.08)*speed*updateRate,
    #         'deltaY': -deadzone(quadratic(xboxData.left_js_x),
    #                             0.08)*speed*updateRate,
    #         'deltaZ': -deadzone(quadratic(xboxData.right_js_y),
    #                             0.08)*speed*updateRate
    #     }

    #     lcm_.publish('/ik_arm_control', deltaPos);

    #     openloop = {
    #         'type': 'OpenLoopRAMotor',
    #         'joint_id': 5,
    #         'speed': (xboxData.d_pad_right - xboxData.d_pad_left)*0.60,
    #     }
    #     lcm_.publish('/arm_motors', openloop)

    #     openloop.joint_id = 6
    #     openloop.speed = (xboxData.right_bumper - xboxData.left_bumper)
    #     lcm_.publish('/arm_motors', openloop)


def arm_toggles_button_callback(channel, msg):
    arm_toggles = ArmToggles.decode(msg)
    arm_toggles.solenoid = solenoid_on.new_reading(arm_toggles.solenoid)
    elec_value = electromagnet_on.new_reading(arm_toggles.electromagnet)
    arm_toggles.electromagnet = elec_value
    arm_toggles.laser = laser_on.new_reading(arm_toggles.laser)
    lcm_.publish('/arm_toggles_toggle_data', arm_toggles.encode())

    # arm_toggles = {
    #     'type': 'ArmToggles',
    #     'solenoid': xboxData.b,
    #     'electromagnet': electromagnet_toggle.new_reading(xboxData.a),
    #     'laser': laser_toggle.new_reading(xboxData.x)
    # }

    # if send_arm_toggles:
    #     lcm_.publish('/arm_toggles', arm_toggles)


def autonomous_callback(channel, msg):
    input_data = Joystick.decode(msg)
    new_motor = DriveMotors()

    joystick_math(new_motor, input_data.forward_back, input_data.left_right)

    lcm_.publish('/motor', new_motor.encode())


async def transmit_temperature():
    while True:
        new_temps = Temperature()

        try:
            with open("/sys/class/hwmon/hwmon0/temp1_input", "r") as bcpu_file:
                new_temps.bcpu_temp = int(bcpu_file.read())
            with open("/sys/class/hwmon/hwmon2/temp1_input", "r") as gpu_file:
                new_temps.gpu_temp = int(gpu_file.read())
            with open("/sys/class/hwmon/hwmon4/temp1_input", "r") \
                    as tboard_file:
                new_temps.tboard_temp = int(tboard_file.read())
        except FileNotFoundError:
            print("Temperature files not found")
            return

        with await lock:
            lcm_.publish('/temperature', new_temps.encode())

        # print("Published new tempertues")
        # print("bcpu temp: {} gpu temp: {} tboard temp: {} ".format(
        #     new_temps.bcpu_temp/1000, new_temps.gpu_temp/1000,
        #     new_temps.tboard_temp/1000))
        await asyncio.sleep(1)


async def transmit_drive_status():
    global kill_motor
    while True:
        new_kill = KillSwitch()
        new_kill.killed = kill_motor
        with await lock:
            lcm_.publish('/kill_switch', new_kill.encode())
        # print("Published new kill message: {}".format(kill_motor))
        await asyncio.sleep(1)


def sa_control_callback(channel, msg):
    xboxData = Xbox.decode(msg)

    saMotorsData = [-deadzone(quadratic(xboxData.left_js_x), 0.09)*0.5,
                    -deadzone(quadratic(xboxData.left_js_y), 0.09)*0.5,
                    quadratic(xboxData.left_trigger -
                              xboxData.right_trigger)*0.6]

    openloop_msg = SAOpenLoopCmd()
    openloop_msg.throttle = saMotorsData

    lcm_.publish('/sa_openloop_cmd', openloop_msg.encode())

    # lcm_.publish('/sa_openloop_cmd', saOpenLoopData)
    # Can only toggle either front or back drill
    # let front_drill_input = this.controlMode ==
    #   'front_drill' and xboxData.right_bumper
    # let back_drill_input = this.controlMode ==
    #   'back_drill' and xboxData.right_bumper


def gimbal_control_callback(channel, msg):
    keyboardData = Keyboard.decode(msg)

    pitchData = [keyboardData.w - keyboardData.s,
                 keyboardData.i - keyboardData.k]

    yawData = [keyboardData.a - keyboardData.d,
               keyboardData.j - keyboardData.l]

    gimbal_msg = GimbalCmd()
    gimbal_msg.pitch = pitchData
    gimbal_msg.yaw = yawData

    lcm_.publish('/gimbal_openloop_cmd', gimbal_msg.encode())


def main():
    hb = heartbeatlib.OnboardHeartbeater(connection_state_changed, 0)
    # look LCMSubscription.queue_capacity if messages are discarded
    lcm_.subscribe("/drive_control", drive_control_callback)
    lcm_.subscribe("/autonomous", autonomous_callback)
    lcm_.subscribe('/ra_control', ra_control_callback)
    lcm_.subscribe('/sa_control', sa_control_callback)
    lcm_.subscribe('/gimbal_control', gimbal_control_callback)
    # lcm_.subscribe('/arm_toggles_button_data', arm_toggles_button_callback)

    run_coroutines(hb.loop(), lcm_.loop(),
                   transmit_temperature(), transmit_drive_status())
