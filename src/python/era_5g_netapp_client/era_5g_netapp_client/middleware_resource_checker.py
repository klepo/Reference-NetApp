from typing import Callable
from era_5g_netapp_interface.common import ThreadBase
import requests
from requests import HTTPError
import time

class MiddlewareResourceChecker(ThreadBase):

    def __init__(self, logger, name, token, action_plan_id, status_endpoint:str, state_callback: Callable = None):
        super().__init__(logger, name)
        self.token = token
        self.action_plan_id = action_plan_id
        self.resource_state = None
        self.state_callback = state_callback
        self.status_endpoint = status_endpoint
        self.status = None
        self.url = None

    def _run(self):
        while True:
            resource_state = self.getResourceStatus()
            
            seq = resource_state.get('ActionSequence', [])
            if len(seq) > 0:
                services = seq[0].get("Services", [])
                if len(services) > 0:
                    self.resource_state = services[0]
                    self.status = self.resource_state.get("ServiceStatus", None)
                    self.url = self.resource_state.get("ServiceUrl", None)

            if self.state_callback:
                self.state_callback(self.resource_state)
            time.sleep(0.5) # TODO: adjust or use somehting similar to rospy.rate.sleep()
    
    def getResourceStatus(self):
        try:  # query orchestrator for latest information regarding the status of resources.
            hed = {'Authorization': 'Bearer ' + str(self.token)}
            url = f"{self.status_endpoint}/{str(self.action_plan_id)}"
            response = requests.get(url, headers=hed)
            return response.json()
        except HTTPError as e:
            print(e.response.status_code)
            return 'Error, could not get the resource status, revisit the log files for more details.'

    def wait_until_resource_ready(self, timeout: int = -1):
        while True:
            #if timeout < 0 and time.time() < timeout:
            #    raise TimeoutError
            
            if self.is_ready():
                return
            time.sleep(0.1)

    def is_ready(self):
        return self.status == "Active"


