#!/usr/bin/env python3
# Borrowed extensivly from https://github.com/scottalford75/Remora-NVEM/tree/main/LinuxCNC/Components/NVMPG
# the pendant supports 6 axis in this file axis-b abd axis-c are commented out
# loadusr -Wn nvmpg-usb /home/martin/nvmpg
# https://www.amazon.com/USB-Serial-Adapter-Prolific-Retention/dp/B000HVHDJ8
# http://www.oz1jhm.dk/content/linuxcnc-and-arduino
# WARNING this is ugly I do not do Python

import os, sys
import serial
import hal
import time
import struct
import linuxcnc
from ctypes import *

stat = linuxcnc.stat()
cmd = linuxcnc.command()
## Constants
JOINTCOUNT=3
JOGSCALE=0.001 # on my machine mpg-jogscale is mm per one click of jog wheel in x1 mode. So on x1000 mode one full rotation moves 100mm
MPGSCALEx1=0.00025
MPGSCALEx10=0.0025
MPGSCALEx100=0.025
MPGSCALEx1000=0.25

print('starting')
# inifile = linuxcnc.ini(os.environ['INI_FILE_NAME'])
# trajcoordinates = inifile.find("TRAJ", "COORDINATES").lower().replace(" ","")
# JOINTCOUNT = int(inifile.find("KINS","JOINTS"))

### HAL Function Examples
# value = hal.get_value("iocontrol.0.emc-enable-in")

# hal.set_p("pinname","10")

# you can make a signal name in python with:
# hal.new_sig.(SIGNAME,hal.HAL_PIN_TYPE)
# hal.new_sig("signalname",hal.HAL_BIT)

# you can connect pin to signal in python with:
# hal.connect(PINNAME,SIGNAME)

###

### TODO
# hold spindle and jog to change override?
# 



def is_all_homed():
    stat.poll()
    homed_count = 0
    for i,h in enumerate(stat.homed):
        #Don't worry about joint to axis mapping
        if h: homed_count +=1
    if homed_count == stat.joints:
        return True
    return False


PORT = "/dev/ttyUSB0"
try:
      ser = serial.Serial(PORT, 115200, timeout=15)
except:
    print("Serial connection failed port: " + PORT)
    raise SystemExit    

c = hal.component("nvmpg")
c.newpin("spindleEnable",hal.HAL_BIT,hal.HAL_IN)
c.newpin("stop",hal.HAL_BIT,hal.HAL_IN)
c.newpin("speed",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("x-pos",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("x-pos-offset",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("y-pos",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("z-pos",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("a-pos",hal.HAL_FLOAT,hal.HAL_IN)
#c.newpin("b-pos",hal.HAL_FLOAT,hal.HAL_IN)
#c.newpin("c-pos",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("reset",hal.HAL_BIT,hal.HAL_IN)
c.newpin("spindle-rpm",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("spindle-on",hal.HAL_BIT,hal.HAL_IN)
c.newpin("rapid-override",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("feed-override",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("spindle-override",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("parameter-inc",hal.HAL_BIT,hal.HAL_IN)
c.newpin("axis-up",hal.HAL_BIT,hal.HAL_IN)
c.newpin("axis-down",hal.HAL_BIT,hal.HAL_IN)
c.newpin("multiplier-inc",hal.HAL_BIT,hal.HAL_IN)
c.newpin("x-select",hal.HAL_BIT,hal.HAL_IO)
c.newpin("y-select",hal.HAL_BIT,hal.HAL_IO)
c.newpin("z-select",hal.HAL_BIT,hal.HAL_IO)
c.newpin("a-select",hal.HAL_BIT,hal.HAL_OUT)
#c.newpin("b-select",hal.HAL_BIT,hal.HAL_OUT)
#c.newpin("c-select",hal.HAL_BIT,hal.HAL_OUT)
c.newpin("mpg-jogscale",hal.HAL_FLOAT,hal.HAL_IN)
c.newpin("mpg-scale",hal.HAL_FLOAT,hal.HAL_OUT)
time.sleep(1)
c.ready()

def ok_for_mdi():
    stat.poll()
    return not stat.estop and stat.enabled and stat.homed and (stat.interp_state == linuxcnc.INTERP_IDLE)

def get_handlers(linuxcnc_stat, linucnc_cmd, commands, master):
    return [HandlerClass(linuxcnc_stat, linucnc_cmd, commands, master)]


NVMPGinputs = ""
# INITIAL OUTPUT VALUES
selectedAxis = 0
c['x-select'] = 1; c['y-select'] = 0; c['z-select'] = 0; #c['a-select'] = 0

# Jog scale
selectedMultiplier = 2 # x100 mode
c['mpg-jogscale']=JOGSCALE
c['mpg-scale'] = MPGSCALEx100 * c['mpg-jogscale']

# INPUTS
spindle_rpm = int(c['spindle-rpm'])
spindle_on = c['spindle-on']
feed_rate_override = int( 100 * c['feed-override'])
spindle_rate_override =  int(100 * c['spindle-override'])
slowJogRate =  int(100 * c['rapid-override']) 
parameter_select =  0
reset = c['reset']

xPosOld = xPos = int(c['x-pos'] * 1000)
yPosOld = yPos = int(c['y-pos'] * 1000)
zPosOld = zPos = int(c['z-pos'] * 1000)
aPosOld = aPos = int(c['a-pos'] * 1000)
#bPosOld = bPos = int(c['b-pos'] * 1000)
#cPosOld = cPos = int(c['c-pos'] * 1000)

# STATE
updateFlag=1
counter=0

# SERIAL DATA
class mpgTxStruct(Structure):
    _fields_ = [('byte0', c_byte),
                ('byte1', c_byte),
                ('xPos', c_int),
                ('yPos', c_int),
                ('zPos', c_int),
                ('aPos', c_int),
                ('bPos', c_int),
                ('cPos', c_int),
                ('byte24', c_byte),
                ('reset', c_ubyte),
                ('byte26', c_byte),	
                ('spindle_rpm', c_int),
                ('spindle_on', c_ubyte),
                ('feed_rate_override', c_ubyte),
                ('slow_jog_rate', c_ubyte),
                ('spindle_rate_override', c_ubyte),
                ('spare35', c_byte),
                ('parameter_select', c_ubyte),
                ('axis_select', c_ubyte),
                ('mpg_multiplier', c_byte),
                ('spare39', c_byte),
                ('spare40', c_byte),
                ('spare41', c_byte),
                ('spare42', c_byte),
                ('spare43', c_byte),
                ('spare44', c_byte),
                ('spare45', c_byte),
                ('spare46', c_byte),
                ('spare47', c_byte),
                ('spare48', c_byte),
                ('spare49', c_byte),
                ('spare50', c_byte)
                ]

mpgTxData = bytearray(55)
mpgTx = mpgTxStruct()
mpgTx.byte0 = 0x5a
mpgTx.byte1 = 0x5a

#FUNCTIONS
def parse_byte(byte):
    return byte[0] & 0x80

def updateState():
    global spindle_rpm,spindle_on,feed_rate_override,spindle_rate_override,parameter_select,reset,slowJogRate
    global xPos,yPos,zPos,aPos
    #stat.poll()
    spindle_rpm = int(c['spindle-rpm'])
    spindle_on = c['spindle-on']
    feed_rate_override = int( 100 * c['feed-override'])
    spindle_rate_override =  int(100 * c['spindle-override'])
    slowJogRate =  int(100 * c['rapid-override']) 
    parameter_select =  c['parameter-inc']
    reset = c['reset']
    xPos = int(c['x-pos'] * 1000)
    yPos = int(c['y-pos'] * 1000)
    zPos = int(c['z-pos'] * 1000)
    aPos = int(c['a-pos'] * 1000)
    #bPos = int(c['b-pos'] * 1000)
    #cPos = int(c['c-pos'] * 1000)
   

def updateMPG():
    mpgTx.xPos = xPos
    mpgTx.yPos = yPos
    mpgTx.zPos = zPos
    mpgTx.aPos = aPos
    #mpgTx.bPos = bPos
    #mpgTx.cPos = cPos
    mpgTx.reset = reset
    mpgTx.spindle_rpm = spindle_rpm
    mpgTx.spindle_on = spindle_on
    mpgTx.feed_rate_override =  feed_rate_override
    mpgTx.spindle_rate_override =  spindle_rate_override
    mpgTx.parameter_select = parameter_select
    mpgTx.axis_select = selectedAxis if selectedAxis>-1 else 6  # 1-5  -1=all (6)
    mpgTx.slow_jog_rate = slowJogRate
    mpgTx.mpg_multiplier = selectedMultiplier # 1-3 
     # pack into struct to send to mpg integers are little endian 
    struct.pack_into("<BBiiiiiiBBBI19B", mpgTxData, 0, 
            mpgTx.byte0, mpgTx.byte1, mpgTx.xPos, mpgTx.yPos, mpgTx.zPos, mpgTx.aPos, mpgTx.bPos, mpgTx.cPos,
            mpgTx.byte24, mpgTx.reset, mpgTx.byte26, mpgTx.spindle_rpm, 
            mpgTx.spindle_on, mpgTx.feed_rate_override, mpgTx.slow_jog_rate, mpgTx.spindle_rate_override,
            mpgTx.spare35,mpgTx.parameter_select,mpgTx.axis_select,mpgTx.mpg_multiplier,
            mpgTx.spare39,mpgTx.spare41, mpgTx.spare42, mpgTx.spare43, mpgTx.spare44,
            mpgTx.spare45, mpgTx.spare46, mpgTx.spare47, mpgTx.spare48, mpgTx.spare49, mpgTx.spare50
    )
    ser.write(mpgTxData)
    #print(struct.unpack_from("BBffffffBBBI19B", mpgTxData, 0))   

def StartTest():
    global spindle_rpm,spindle_on,feed_rate_override,spindle_rate_override,parameter_select,reset,slowJogRate
    global xPos,yPos,zPos,aPos
    completed=0
    t=0
    while not completed: 

        parameter_select = t
        parameter_select = parameter_select % 4
        reset = t
        selectedAxis =t
        print("Time: ", t, " Joint ", )
        updateMPG()
        t = t + 1
        if t==12:t=250
        if t > 255: completed=1
        time.sleep(.5)  

 # This restarts the program at the line specified directly (without cyscle start push)
# def re_start(self, wname, line):
#             cmd.mode(linuxcnc.MODE_AUTO)
#             cmd.wait_complete()
#             cmd.auto(linuxcnc.AUTO_RUN, line)
#             restart_line_number = restart_reset_line

def isRunning():
    stat.poll()
    """Returns TRUE if machine is moving due to MDI, program execution, etc."""
    if stat.state == linuxcnc.RCS_EXEC:
        return True
    else:
        return stat.task_mode == linuxcnc.MODE_AUTO \
            and stat.interp_state != linuxcnc.INTERP_IDLE

def waithomed(joint):
    stat.poll()
    t = 0.0
    i = 0
    homed = stat.joint[joint]["homed"]
    while not homed and t < 30:
        time.sleep(0.1)
        t = t + 0.1
        i = i + 1
        stat.poll()
        homed = stat.joint[joint]["homed"]
        if i == 10:
            i = 0
            print("Time: ", t, " Joint ", joint, " homed: ", homed)

print("NVMPG loaded")
#MAIN LOOP
try:
  while 1:
    time.sleep(.05)
    counter += 1
    # get current postions
    updateState()
    updateMPG()
    
    if counter > 60:
        counter=0
        #print(stat.task_mode)
        
    #Check to see if we have a message waiting from the NVMPG
    while ser.inWaiting():
        mpgRxData = ser.read(1)
        #The NVMPG generates two different key events
        #One when the key is pressed down and another when it is released
        # button state is from the high nibble, x0_ is button down (logical 1), x8_ is button up (logical 0)
        buttonState = parse_byte(mpgRxData)
        #print(buttonState)
        #print(mpgRxData)

        # # left button start/pause 
        # if(mpgRxData.hex() == "0b"):
        #     if(isRunning()): # interp-run
        #        cmd.auto(linuxcnc.AUTO_PAUSE) 
            
        #   else: # THIS SEEMS LIKE A BAD IDEA
        #     if stat.paused():
        #         cmd.auto(linuxcnc.AUTO_RESUME)     
        #     else:
        #         print("stat:")
        #         print(stat)
        
        #eStop right button
        if(mpgRxData.hex() == "0a" or "0b"):
          cmd.abort()
          c['stop'] = 1

        # eStop button up 
        if(mpgRxData.hex() == "8a" or "8b"):
          c['stop'] = 0

        #axis down arrow
        if(mpgRxData.hex() == "03"):
          selectedAxis += 1
          if selectedAxis > JOINTCOUNT-1: selectedAxis = 0
          updateFlag = 1
        
        #axis up arrow -1 = none selected
        if(mpgRxData.hex() == "02"):
          selectedAxis -= 1
          if selectedAxis < -1: selectedAxis = JOINTCOUNT-1
          updateFlag = 1 
        
        if(updateFlag==1 and (mpgRxData.hex() == "02" or  mpgRxData.hex() == "03")):
            c['x-select']=0; c['y-select']=0; c['z-select']=0; c['a-select']=0;# c['b-select']=0; c['c-select']=0
            if selectedAxis == 0:
                c['x-select']=1
            if selectedAxis == 1:
                c['y-select']=1
            if selectedAxis == 2:
                c['z-select']=1
            if selectedAxis == 3:
                c['a-select']=1
            if selectedAxis == -1:
                c['x-select']=c['y-select']=c['z-select']=1

            # if selectedAxis == 4:
            #     c['b-select']=1   
            # if selectedAxis == 5:
            #     c['c-select']=1
        
        #spindleOn
        if(mpgRxData.hex() == "04"):
            if spindle_on == 0: spindle_on = 1 
            else: spindle_on = 0
            c['spindle-on'] = spindle_on
            cmd.spindle(linuxcnc.SPINDLE_FORWARD)
            updateFlag = 1

        # mulitplier
        if(mpgRxData.hex() == "05"):
            selectedMultiplier += 1
            if selectedMultiplier > 3:
                selectedMultiplier = 0
                c['mpg-scale'] = MPGSCALEx1 * c['mpg-jogscale']
            if selectedMultiplier == 1:
                c['mpg-scale'] = MPGSCALEx10 * c['mpg-jogscale']
            if selectedMultiplier == 2:
                c['mpg-scale'] = MPGSCALEx100 * c['mpg-jogscale']
            if selectedMultiplier == 3:
               c['mpg-scale'] = MPGSCALEx1000 * c['mpg-jogscale']
            updateFlag = 1
            print(selectedMultiplier)
        
        # goto machine location (e.g manual tool change)
        if(mpgRxData.hex() == "07"):
            if ok_for_mdi() and is_all_homed():
                cmd.mode(linuxcnc.MODE_MDI)
                cmd.wait_complete() # wait until mode switch executed
                cmd.mdi("G28") # use value stored with G28.1
                cmd.wait_complete()
                cmd.mode(linuxcnc.MODE_MANUAL)
                
            else:
                print("MDI OK:")
                print(ok_for_mdi())

        # Home selected axis
        if(mpgRxData.hex() == "06"):
            cmd.mode(linuxcnc.MODE_MANUAL)
            cmd.wait_complete() 
            cmd.teleop_enable(False)
           
            if selectedAxis > -1:
                try:
                    cmd.home(selectedAxis)
                    waithomed(selectedAxis)
                except:
                     print("Something else went wrong")
                     raise SystemExit

            else:            
                cmd.home(-1)
                cmd.wait_complete() 
                print("Home All")

        # Zero touchoff selected axis
        if(mpgRxData.hex() == "08"):
            if ok_for_mdi():
                cmd.mode(linuxcnc.MODE_MDI)
                cmd.wait_complete() # wait until mode switch executed
                if(selectedAxis==0):
                   cmd.mdi("G10 L20 P0 X0")
                if(selectedAxis==1):
                   cmd.mdi("G10 L20 P0 Y0")
                if(selectedAxis==2):
                   cmd.mdi("G10 L20 P0 Z0")
                if(selectedAxis==3):
                   cmd.mdi("G10 L20 P0 A0")
                if(selectedAxis==-1):
                   cmd.mdi("G10 L20 P0 X0Y0Z0")
                cmd.wait_complete()                 
                cmd.mode(linuxcnc.MODE_MANUAL)
            else:
                print("not ok for MDI")
            #cmd.mdi("G10 L2 P1 X0 Y0 Z0") #(clear offsets for X,Y & Z axes in coordinate system 1)
        
        # %halcmd setp axisui.refresh 1
        
        # 1/2 up
        if(mpgRxData.hex() == "89"):
            StartTest()
        # 

except KeyboardInterrupt:
    print("Exit\r\n")
    raise SystemExit
