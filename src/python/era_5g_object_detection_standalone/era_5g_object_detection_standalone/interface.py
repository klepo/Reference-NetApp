#!/usr/bin/env python3

import logging
import secrets
from queue import Queue
import cv2

import numpy as np
# select the desired detector to be imported
#from era_5g_object_detection_standalone.worker_face import FaceDetectorWorker as DetectorWorker
#from era_5g_object_detection_standalone.worker_mmdet import MMDetectorWorker as DetectorWorker
from era_5g_object_detection_standalone.worker_fps import FpsDetectorWorker as DetectorWorker

from era_5g_object_detection_common.image_detector import ImageDetectorInitializationFailed

import flask_socketio
from era_5g_netapp_interface.task_handler_gstreamer_internal_q import \
    TaskHandlerGstreamerInternalQ
from era_5g_netapp_interface.task_handler_internal_q import TaskHandlerInternalQ
from era_5g_netapp_interface.common import get_logger
from flask import Flask, Response, request, session

from flask_session import Session

# flask initialization
app = Flask(__name__)
app.secret_key = secrets.token_hex()
app.config['SESSION_TYPE'] = 'filesystem'

# socketio initialization for sending results to the client
Session(app)
socketio = flask_socketio.SocketIO(app, manage_session=False, async_mode='threading') 

# list of available ports for gstreamer communication - they needs to be exposed when running in docker / k8s
free_ports = [5001, 5002, 5003]

# list of registered tasks
tasks = dict()

# queue with received images
# TODO: adjust the queue length
image_queue = Queue(30)

logger = get_logger(log_level=logging.INFO)

# the image detector to be used
detector_thread = None

@app.route('/register', methods=['GET'])
def register():
    """
    Needs to be called before an attempt to open WS is made.

    Returns:
        _type_: The port used for gstreamer communication.
    """
    global logger
    if not free_ports:
        return {"error": "Not enough resources"}, 503
    
    session['registered'] = True

    args = request.args.to_dict()
    gstreamer = args.get("gstreamer", False)
    # select the appropriete task hander, depends on whether the client wants to use 
    # gstreamer to pass the images or not 
    if gstreamer:
        port = free_ports.pop(0)  
        task = TaskHandlerGstreamerInternalQ(logger, session.sid, port, image_queue)
    else:
        task = TaskHandlerInternalQ(logger, session.sid, image_queue)
     
    tasks[session.sid] = task
    print(f"Client registered: {session.sid}")
    if gstreamer:
        return {"port": port}, 200
    else:
        return Response(status=204)


@app.route('/unregister', methods=['GET'])
def unregister():
    """_
    Disconnects the websocket and removes the task from the memory.

    Returns:
        _type_: 204 status
    """
    session_id = session.sid

    if session.pop('registered', None):
        task = tasks.pop(session.sid)
        flask_socketio.disconnect(task.websocket_id, namespace="/results")
        free_ports.append(task.port)
        task.stop()
        print(f"Client unregistered: {session_id}")

        
    return Response(status=204)

@app.route('/image', methods=['POST'])
def post_image():
    """
    Allows to send jpg-encoded image using the HTTP transport

    
    """
    sid = session.sid
    task = tasks[sid]
    # convert string of image data to uint8
    nparr = np.fromstring(request.data, np.uint8)
    # decode image
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR) 
    if "timestamp" in request.args:
        timestamp = request.args["timestamp"]
    else:
        timestamp = None
    # store the image to the appropriate task
    task.store_image({"sid": sid, "websocket_id": task.websocket_id, "timestamp": timestamp}, img)
    return Response(status=204)


@socketio.on('connect', namespace='/results')
def connect(auth):
    """
    Creates a websocket connection to the client for passing the results.


    Raises:
        ConnectionRefusedError: Raised when attempt for connection were made
            without registering first.
    """
    if 'registered' not in session:
        raise ConnectionRefusedError('Need to call /register first.')

    sid = request.sid

    print('connect ', sid)
    print(f"Connected. Session id: {session.sid}, ws_sid: {sid}")
    tasks[session.sid].websocket_id = sid
    tasks[session.sid].start(daemon=True)
    flask_socketio.send("you are connected", namespace='/results', to=sid)


@socketio.event
def disconnect(sid):
    print('disconnect ', sid)


def main(args=None):
    global image_queue

    
    # Creates detector and runs it as thread, listening to image_queue
    try:
        detector_thread = DetectorWorker(logger, "Detector", image_queue, app)
        detector_thread.start(daemon=True)
    except ImageDetectorInitializationFailed as ex:
        print(ex)
        exit()
    
    # Estimate new queue size based on maximum latency
    """avg_latency = latency_measurements.get_avg_latency() # obtained from detector init warmup
    if avg_latency != 0:  # warmup can be skipped
        new_queue_size = int(max_latency / avg_latency)
        image_queue = Queue(new_queue_size)
        detector_thread.input_queue = image_queue"""
    
   
    # runs the flask server
    # allow_unsafe_werkzeug needs to be true to run inside the docker
    # TODO: use better webserver
    socketio.run(app, port=5896, host='0.0.0.0', allow_unsafe_werkzeug=True)
    


if __name__ == '__main__':
    main()