import socket
import logging
from struct import *
import sys
import time
import numpy as np
from fractions import Fraction
import os

from PyQt5.QtWidgets import QDialog, QApplication, QSpinBox, QFileDialog
from PyQt5.QtGui import QImage, QPainter,QPixmap
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt

from TelecineDialogUI import Ui_TelecineDialog
from ImageThread import ImageThread

sys.path.append('../Common')
from Constants import *
from MessageSocket import *

localSettings = ('ip_pi', 'root_directory')

#Generic methods to set/get object attributes from a dictionary
def getSettings(object, keys):
    settings = {}
    for k in keys :
        value = getattr(object, k)
        settings[k] = value
    return settings

def setSettings(object, settings) :
    for k in settings : 
        setattr(object, k, settings[k])        


class TelecineDialog(QDialog, Ui_TelecineDialog):

    def __init__(self):
        super(TelecineDialog, self).__init__()
        self.setupUi(self)
        self.sock = None
        self.connected = False
        self.saveTofile = False
        self.directory = ''
        self.imageThread = None
        self.connectButton.setStyleSheet("background-color: red")
        self.ip_pi = ''
        self.cameraVersion = ''
        self.root_directory = 'images'
        self.captureStopButton.setEnabled(False)
        self.cameraControlGroupBox.setEnabled(False)
        self.bracketControlGroupBox.setEnabled(False)
        self.frameProcessingGroupBox.setEnabled(False)
        self.motorControlGroupBox.setEnabled(False)
        self.cameraSettingsGroupBox.setEnabled(False)
        self.motorSettingsGroupBox.setEnabled(False)
        self.cameraGroupBox.setEnabled(False)
        self.closeCameraButton.setEnabled(False)
        self.motorStopButton.setEnabled(False)
        self.motorOffButton.setEnabled(False)
        
#Lamp
    def setLamp(self):
        if self.lampCheckBox.isChecked() :
            self.sock.sendObject((SET_LAMP, LAMP_ON))
        else :
            self.sock.sendObject((SET_LAMP, LAMP_OFF))
        
#Motor Control
    def motorOn(self) :
        self.sock.sendObject((MOTOR_ON,))
        self.motorControlGroupBox.setEnabled(True)
        self.motorOnButton.setEnabled(False)
        self.motorOffButton.setEnabled(True)
    def motorOff(self) :
        self.sock.sendObject((MOTOR_OFF,))
        self.motorControlGroupBox.setEnabled(False)
        self.motorOnButton.setEnabled(True)
        self.motorOffButton.setEnabled(False)
    def forwardOne(self):
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((MOTOR_ADVANCE_ONE,MOTOR_FORWARD))
    def backwardOne(self) :
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((MOTOR_ADVANCE_ONE,MOTOR_BACKWARD))
    def forward(self):
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((MOTOR_ADVANCE, MOTOR_FORWARD))
        self.motorStopButton.setEnabled(True)
        self.forwardOneButton.setEnabled(False)
        self.backwardOneButton.setEnabled(False)
        self.forwardButton.setEnabled(False)
        self.backwardButton.setEnabled(False)
    def backward(self):
        self.setMotorSettings({'speed':self.motorSpeedBox.value()})
        self.sock.sendObject((MOTOR_ADVANCE, MOTOR_BACKWARD))
        self.motorStopButton.setEnabled(True)
        self.forwardOneButton.setEnabled(False)
        self.backwardOneButton.setEnabled(False)
        self.forwardButton.setEnabled(False)
        self.backwardButton.setEnabled(False)
    def motorStop(self):
        self.sock.sendObject((MOTOR_STOP,))
        self.motorStopButton.setEnabled(False)
        self.forwardOneButton.setEnabled(True)
        self.backwardOneButton.setEnabled(True)
        self.forwardButton.setEnabled(True)
        self.backwardButton.setEnabled(True)


    def setMotorSettings(self, settings) :
        self.sock.sendObject((SET_MOTOR_SETTINGS, settings))
        
    def setMotorInitSettings(self) :
        self.sock.sendObject((SET_MOTOR_SETTINGS, {\
            'steps_per_rev':self.stepsPerRevBox.value(),\
            'ena_pin':int(self.enaEdit.text()),\
            'dir_pin':int(self.dirEdit.text()),\
            'pulse_pin':int(self.pulseEdit.text()),\
            'trigger_pin':int(self.triggerEdit.text()),\
            'dir_level': 1 if self.dirLevelCheckBox.isChecked() else 0 ,\
            'pulse_level': 1 if self.pulseLevelCheckBox.isChecked() else 0, \
            'ena_level': 1 if self.enaLevelCheckBox.isChecked() else 0, \
            'trigger_level': 1 if self.triggerLevelCheckBox.isChecked() else 0, \
            }))
        
#Get and display motor settings
    def getMotorSettings(self) :
        self.sock.sendObject((GET_MOTOR_SETTINGS,))
        settings = self.sock.receiveObject()
        self.stepsPerRevBox.setValue(settings['steps_per_rev'])
        self.pulleyRatioBox.setValue(settings['pulley_ratio'])
        self.enaEdit.setText(str(settings['ena_pin']))
        self.dirEdit.setText(str(settings['dir_pin']))
        self.pulseEdit.setText(str(settings['pulse_pin']))
        self.triggerEdit.setText(str(settings['trigger_pin']))
        self.enaLevelCheckBox.setChecked(settings['ena_level'] == 1)
        self.dirLevelCheckBox.setChecked(settings['dir_level'] == 1)
        self.pulseLevelCheckBox.setChecked(settings['pulse_level'] == 1)
        self.triggerLevelCheckBox.setChecked(settings['trigger_level'] == 1)
        return settings

        
#Camera control
    def openCamera(self):
        mode = int(self.modeBox.value())  #0 automatic
        hres = self.hresLineEdit.text()
        vres = self.vresLineEdit.text()
        requestedResolution = None
        if hres and vres :
            requestedResolution = (int(hres), int(vres))
        self.sock.sendObject((OPEN_CAMERA, mode, requestedResolution, self.useCalibrationCheckBox.isChecked()))
        self.getCameraSettings()
        maxResolution = self.getCameraSetting('MAX_RESOLUTION')
        if maxResolution[0] == 3280 :
            self.cameraVersion = 2
        else :
            self.cameraVersion = 1
        if not (hres and vres) and mode != 0 :
            if self.cameraVersion == 2 :
                res=V2_RESOLUTIONS[mode-1]
            else :
                res=V1_RESOLUTIONS[mode-1]
            self.sock.sendObject((SET_CAMERA_SETTINGS, {'resolution':res}))
        self.cameraVersionLabel.setText('Picamera V' + str(self.cameraVersion))
        self.resolution = self.getCameraSetting('resolution')
        self.hresLineEdit.setText(str(self.resolution[0]))
        self.vresLineEdit.setText(str(self.resolution[1]))
        self.cameraControlGroupBox.setEnabled(True)
        self.bracketControlGroupBox.setEnabled(True)
        self.frameProcessingGroupBox.setEnabled(True)
        self.cameraSettingsGroupBox.setEnabled(True)
        self.closeCameraButton.setEnabled(True)
        self.openCameraButton.setEnabled(False)
        self.calibrateButton.setEnabled(False)



    def closeCamera(self) :
        self.sock.sendObject((CLOSE_CAMERA,))
        self.cameraControlGroupBox.setEnabled(False)
        self.bracketControlGroupBox.setEnabled(False)
        self.frameProcessingGroupBox.setEnabled(False)
        self.cameraSettingsGroupBox.setEnabled(False)
        self.closeCameraButton.setEnabled(False)
        self.openCameraButton.setEnabled(True)
        self.calibrateButton.setEnabled(True)
    
    def calibrate(self) :
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.sock.sendObject((CALIBRATE_CAMERA,))
        done = self.sock.receiveObject()
        QApplication.restoreOverrideCursor()        
        print(done)
        
    def equalize(self) :
        self.imageThread.equalize = self.equalizeCheckBox.isChecked()
#Capture
#CAPTURE_BASIC play with ot without motor
#CAPTURE_ON_FRAME capture frame and advance motor
#CAPTURE_ON_TRIGGER lauchn motor and capture on trigger        
    def captureStart(self):
        brackets = 1
        frameRate = self.framerateBox.value()
        if self.bracketCheckBox.isChecked() :
            brackets = 3
        method = None
        if self.onFrameButton.isChecked() :
            method = CAPTURE_ON_FRAME
        elif self.onTriggerButton.isChecked() :
            method = CAPTURE_ON_TRIGGER
        else :
            method = CAPTURE_BASIC
            frameRate = self.playFramerateBox.value()
        if method != CAPTURE_BASIC :
            self.motorControlGroupBox.setEnabled(False)
            self.sock.sendObject((SET_MOTOR_SETTINGS, {'speed':self.captureMotorSpeedBox.value()}))

        self.setMerge()
        self.setSave()
        self.captureStopButton.setEnabled(True)
        self.captureStartButton.setEnabled(False)
        self.takeImageButton.setEnabled(False)
        self.sock.sendObject((SET_CAMERA_SETTINGS, {\
                                                    'framerate':frameRate,\
                                                    'bracket_steps':brackets, \
                                                    'bracket_dark_coefficient':self.darkCoefficientBox.value(),\
                                                    'bracket_light_coefficient':self.lightCoefficientBox.value(),\
#                                                    'use_video_port' : self.videoPortButton.isChecked(),\
                                                    'use_video_port' : True,\
                                                    'capture_method' : method\
                                                    })) 

        self.sock.sendObject((START_CAPTURE,))

    def setMerge(self) :
        merge = None
        if self.mergeNoneRadioButton.isChecked() :
            merge = MERGE_NONE
        elif self.mergeMertensRadioButton.isChecked() :
            merge = MERGE_MERTENS
        else :
            merge = MERGE_DEBEVEC
        self.imageThread.merge = merge
#        self.imageThread.linearize = self.linearizeCheckBox.isChecked()


        
#Stopping capture        
    def captureStop(self) :
        self.captureStopButton.setEnabled(False)
        self.captureStartButton.setEnabled(True)
        self.captureStartButton.setEnabled(True)
        self.takeImageButton.setEnabled(True)
        self.motorControlGroupBox.setEnabled(True)
        self.sock.sendObject((STOP_CAPTURE,))
        
#Take one image
    def takeImage(self):
#        self.sock.sendObject((SET_CAMERA_SETTINGS, {'use_video_port' : self.videoPortButton.isChecked(),})) 
        self.sock.sendObject((SET_CAMERA_SETTINGS, {'use_video_port' : True})) 
        self.sock.sendObject((TAKE_IMAGE,))

#Get all camera settings
    def getCameraSettings(self) :
        self.sock.sendObject((GET_CAMERA_SETTINGS,))
        settings = self.sock.receiveObject()
        self.redGainBox.setValue(float(settings['awb_gains'][0])*100.)
        self.blueGainBox.setValue(float(settings['awb_gains'][1])*100.)
        self.awbModeBox.setCurrentIndex(self.awbModeBox.findText(settings['awb_mode']))
        self.shutterSpeedBox.setValue(int(settings['shutter_speed']))
        self.framerateBox.setValue(int(settings['framerate']))
        exposureSpeed = self.getCameraSetting('exposure_speed')
        self.exposureSpeedLabel.setText(str(exposureSpeed))
        self.analogGainLabel.setText(str(float(settings['analog_gain'])))
        self.digitalGainLabel.setText(str(float(settings['digital_gain'])))
        self.exposureModeBox.setCurrentIndex(self.awbModeBox.findText(settings['exposure_mode']))
        self.brightnessBox.setValue(settings['brightness'])
        self.contrastBox.setValue(settings['contrast'])
        self.contrastBox.setValue(settings['saturation'])
        self.isoBox.setValue(settings['iso'])
        self.exposureCompensationBox.setValue(settings['exposure_compensation'])
        self.bracketCheckBox.setChecked(settings['bracket_steps'] != 0)
        self.lightCoefficientBox.setValue(settings['bracket_light_coefficient'])
        self.darkCoefficientBox.setValue(settings['bracket_dark_coefficient'])
#        self.videoPortButton.setChecked(settings['use_video_port'])
        self.onFrameButton.setChecked(settings['capture_method'] == CAPTURE_ON_FRAME)
        self.shutterSpeedWaitBox.setValue(settings['shutter_speed_wait'])
        self.shutterAutoWaitBox.setValue(settings['shutter_auto_wait'])
        return settings

#Get one camera setting
    def getCameraSetting(self, key):
        self.sock.sendObject((GET_CAMERA_SETTING, key))
        return self.sock.receiveObject()
        
    def saveSettings(self):
        self.sock.sendObject((SAVE_SETTINGS,))

    def setGains(self) :
        blue = self.blueGainBox.value()
        red = self.redGainBox.value()
        gains = (red/100., blue/100.)
        mode = str(self.awbModeBox.currentText())
        settings = {'awb_gains': gains, 'awb_mode':mode}
        self.sock.sendObject((SET_CAMERA_SETTINGS, settings))
    
    def setShutterSpeed(self):
         self.sock.sendObject((SET_CAMERA_SETTINGS, {'shutter_speed':self.shutterSpeedBox.value(), 'exposure_compensation':self.exposureCompensationBox.value()}))

    def setIso(self):
         self.sock.sendObject((SET_CAMERA_SETTINGS, {'iso':self.isoBox.value()}))

    def setFrameRate(self):
         self.sock.sendObject((SET_CAMERA_SETTINGS, {'framerate':self.framerateBox.value()}))
        
    def setSharpness(self) :
        self.imageThread.sharpness = self.sharpnessCheckBox.isChecked()

    def setHistos(self) :
        self.imageThread.histos = self.histosCheckBox.isChecked()

    def setReduce(self) :
        self.imageThread.reduceFactor = self.reduceFactorBox.value()
        
    def setAutoExposure(self):
        if self.autoExposureCheckBox.isChecked() :
            self.sock.sendObject((SET_CAMERA_SETTINGS, {'shutter_speed':0}))
            self.shutterSpeedBox.setValue(0)
        else :
            exposureSpeed = self.getCameraSetting('exposure_speed')
            self.exposureSpeedLabel.setText(str(exposureSpeed/1000))  # ms display
            self.sock.sendObject((SET_CAMERA_SETTINGS, {'shutter_speed':exposureSpeed}))
            self.shutterSpeedBox.setValue(exposureSpeed/1000)
            
    def setAutoGetSettings(self):
        if self.autoGetSettingsCheckBox.isChecked() :
            self.timer = QTimer()
            self.timer.timeout.connect(self.getSettings)
            self.timer.start(5000)
        else :
            self.timer.stop()
            
    def setCorrections(self):
        self.sock.sendObject((SET_CAMERA_SETTINGS, {'brightness':self.brightnessBox.value(), 'contrast':self.contrastBox.value(),'saturation':self.saturationBox.value()}))


        self.directory = root_directory  + "/%#02d_%#02d" % (tape, clip)
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        print(self.directory)

#Experimental not used
    def calibrateHDR(self):
        self.sock.sendObject((CALIBRATE_HDR,25) )
        
    def setSave(self) :
        self.imageThread.saveToFile(self.saveCheckBox.isChecked(), self.directory)

    def setDirectory(self) :
        self.directory = self.root_directory  + "/%#02d_%#02d" % (self.tapeBox.value(), self.clipBox.value())
        self.directoryDisplay.setText(self.directory)
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        
    def chooseDirectory(self) :
        self.root_directory = str(QFileDialog.getExistingDirectory(self, "Select Directory"))

    def displayHeader(self, header) :
        if header['type'] == HEADER_COUNT :
            self.lcdDisplayCount.display(header['count'])
        elif header['type'] == HEADER_MESSAGE :
            self.messageLabel.setText(str(header['msg']))

    def displaySharpness(self, sharpness) :
        self.sharpnessDisplay.setText(str(sharpness))
            
    def connectDisconnect(self) :
        if self.connected :
            self.disconnect()
            self.connectButton.setStyleSheet("background-color: red")
            self.connected = False
            self.connectButton.setText('Connect')
        else :
            self.connect()
            self.connectButton.setStyleSheet("background-color: green")
            self.connected = True
            self.connectButton.setText('Disconnect')

    
    def connect(self) :
        socke = socket.socket()
        self.ip_pi = self.ipLineEdit.text()
        socke.connect((self.ip_pi, 8000))
        self.sock = MessageSocket(socke)
        self.imageThread = ImageThread()
        self.imageThread.headerSignal.connect(self.displayHeader)
        self.imageThread.sharpnessSignal.connect(self.displaySharpness)
        self.imageThread.start()
        self.getMotorSettings()
        self.cameraGroupBox.setEnabled(True)
        self.openCameraButton.setEnabled(True)
        self.calibrateButton.setEnabled(True)
#        self.motorControlGroupBox.setEnabled(True)
        self.motorSettingsGroupBox.setEnabled(True)
        self.connected = True



    def disconnect(self) :
        if self.connected :
            self.sock.sendObject((TERMINATE,))
            self.sock.shutdown()
            self.sock.close()
            self.cameraGroupBox.setEnabled(False)
            self.cameraControlGroupBox.setEnabled(False)
            self.bracketControlGroupBox.setEnabled(False)
            self.frameProcessingGroupBox.setEnabled(False)
            self.motorControlGroupBox.setEnabled(False)
            self.cameraSettingsGroupBox.setEnabled(False)
            self.motorSettingsGroupBox.setEnabled(False)

    def saveLocalSettings(self) :
        np.savez('local.npz', local = getSettings(self, localSettings))

    def setLocalSettings(self) :
        try:
            npz = np.load("local.npz")
            setSettings(self, npz['local'][()])
            commandDialog.ipLineEdit.setText(self.ip_pi)
            commandDialog.directoryDisplay.setText(self.root_directory)
        except Exception as e:
            print(e)
        
        

commandDialog = None
#For getting exception while in QT        
def my_excepthook(type, value, tback):
    commandDialog.messageLabel.setText(str(value))
    print(type)
    print(value)
    print(tback)
    sys.__excepthook__(type, value, tback) 

#Local commandDialog settings
 
    
    
if __name__ == '__main__':
    try:
       # Create the Qt Application
        app = QApplication(sys.argv)
        commandDialog =  TelecineDialog()
        commandDialog.setLocalSettings()
        commandDialog.show()
        sys.excepthook = my_excepthook           
        sys.exit(app.exec_())


    finally:
        print('finally')
        if commandDialog != None :
            commandDialog.saveLocalSettings()
            commandDialog.disconnect()