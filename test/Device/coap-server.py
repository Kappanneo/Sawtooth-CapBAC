import datetime
import logging
import time
import json

import asyncio

import aiocoap.resource as resource
import aiocoap

from colorlog import ColoredFormatter # version 2.6

from subprocess import check_output

def print(string:str): # true printf() debugging
    logging.getLogger(__name__).debug(msg=string)

class SimpleResource(resource.Resource):
    """Example resource which supports the GET and PUT methods."""

    def __init__(self):
        super().__init__()
        self.content= b"this is an important string\n"

    async def render_get(self, request):
        logging.getLogger(__name__).info(msg="GET resource")
        requested_action = "GET"

        valid, ation, payload = request.payload.decode("utf-8").partition('}')
        validation = valid + ation
        print("Validation request: " + validation)
        print("Actual payload: " + payload)

        try:
            validation_json = json.loads(validation)
            assert validation_json["AC"] == requested_action , "Invalid Token"
            result = check_output(['capbac','validate',validation]).decode("utf-8")
            print('Validation result: %s' % result)
            assert json.loads(result)['authorized'], "Unauthorized"
        except Exception as e:
            print(e)
            return aiocoap.Message(code=aiocoap.UNAUTHORIZED)

        return aiocoap.Message(payload=self.content)

    async def render_put(self, request):
        logging.getLogger(__name__).info(msg="PUT resource")
        requested_action = "PUT"

        valid, ation, payload = request.payload.decode("utf-8").partition('}')
        validation = valid + ation
        print("Validation request: " + validation)
        print("Actual payload: " + payload)

        try:
            validation_json = json.loads(validation)
            assert validation_json["AC"] == requested_action , "Invalid Token"
            result = check_output(['capbac','validate',validation]).decode("utf-8")
            print('Validation result: %s' % result)
            assert json.loads(result)['authorized'], "Unauthorized"
        except Exception as e:
            print(e)
            return aiocoap.Message(code=aiocoap.UNAUTHORIZED)

        self.content= payload.encode("utf-8") + b"\n"
        return aiocoap.Message(code=aiocoap.CHANGED, payload=self.content)

class TimeResource(resource.ObservableResource):
    """Example resource that can be observed. The `notify` method keeps
    scheduling itself, and calles `update_state` to trigger sending
    notifications."""

    def __init__(self):
        super().__init__()

        self.handle = None

    def notify(self):
        self.updated_state()
        self.reschedule()

    def reschedule(self):
        self.handle = asyncio.get_event_loop().call_later(5, self.notify)

    def update_observation_count(self, count):
        if count and self.handle is None:
            print("Starting the clock")
            self.reschedule()
        if count == 0 and self.handle:
            print("Stopping the clock")
            self.handle.cancel()
            self.handle = None

    async def render_get(self, request):
        logging.getLogger(__name__).info(msg="GET time")
        requested_action = "GET"

        valid, ation, payload = request.payload.decode("utf-8").partition('}')
        validation = valid + ation
        print("Validation request: " + validation)
        print("Actual payload: " + payload)

        try:
            validation_json = json.loads(validation)
            assert validation_json["AC"] == requested_action , "Invalid Token"
            result = check_output(['capbac','validate',validation]).decode("utf-8")
            print('Validation result: %s' % result)
            assert json.loads(result)['authorized'], "Unauthorized"
        except Exception as e:
            print(e)
            return aiocoap.Message(code=aiocoap.UNAUTHORIZED)

        payload = datetime.datetime.now().\
                strftime("%Y-%m-%d %H:%M\n").encode('ascii')
        return aiocoap.Message(payload=payload)

# logging setup

    clog = logging.StreamHandler()
    formatter = ColoredFormatter(
        "%(log_color)s[%(asctime)s.%(msecs)03d %(levelname)-8s %(module)s]%(reset)s "
        "%(white)s%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        })

    clog.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(clog)

def main():

    logging.getLogger(__name__).info(msg="Starting server...")

    capability_token = {
        "ID":"0000000000000000",
        "DE": "coap://device",    
        "AR": [{
            "AC": "GET",
            "RE": "time",
            "DD": 100
        }, {
            "AC": "GET",
            "RE": "resource",
            "DD": 100
        }, {
            "AC": "PUT",
            "RE": "resource",
            "DD": 100
        }],
        "NB": str(int(time.time())),
        "NA": "2000000000"
    }

    revocation = {
        "ID":"0000000000000000",
        "IC":"0000000000000000",
        "DE":"coap://device",
        "RT":"ALL"
    }

    try:

        print("Issuing root token...")
        response = check_output(["capbac","issue","--root",json.dumps(capability_token)]).decode("utf-8") 
        link = json.loads(response)["link"]

        time.sleep(5)

        print('Checking result...')
        response = check_output(["curl","--silent",link]).decode("utf-8")
        status = json.loads(response)["data"][0]["status"]

        if(status == "COMMITTED"):
            print("Root token committed.")
        else:
            raise Exception("Token status: {}.".format(status))

    except Exception as e:
        logging.getLogger(__name__).error(msg="Unexpected error: {} Server not started.".format(str(e)))
        while True:
            time.sleep(360)

    # Resource tree creation
    root = resource.Site()

    root.add_resource(('.well-known', 'core'),
            resource.WKCResource(root.get_resources_as_linkheader))
    root.add_resource(('time',), TimeResource())
    root.add_resource(('resource',), SimpleResource())
    
    asyncio.Task(aiocoap.Context.create_server_context(root))

    logging.getLogger(__name__).info(msg="Server started.")
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()