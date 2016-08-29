# Licensed under a 3-clause BSD style license - see LICENSE.rst
from ctapipe.core import Component
from ctapipe.pipeline.zmqpipe.connexions import Connexions

from threading import Thread
from time import sleep
import zmq
import types
import pickle



class ProducerZmq(Thread, Component, Connexions):

    """`ProducerZmq` class represents a Producer pipeline Step.
    It is derived from Thread class.
    It gets a Python generator from its coroutine run method.
    It loops overs its generator and sends new input to its next stage,
    thanks to its ZMQ REQ socket,
    The Thread is launched by calling run method, after init() method
    has been called and has returned True.
    """

    def __init__(self, coroutine, name,main_connexion_name,
                connexions=dict(), gui_address=None):
        """
        Parameters
        ----------
        coroutine : Class instance that contains init, run and finish methods
        sock_consumer_port: str
            Port number for socket url
        """
        # Call mother class (threading.Thread) __init__ method
        Thread.__init__(self)
        self.name = name
        Connexions.__init__(self,main_connexion_name,connexions)

        self.identity = '{}{}'.format('id_', "producer")
        self.coroutine = coroutine
        self.running = False
        self.nb_job_done = 0
        self.gui_address = gui_address
        # Prepare our context and sockets
        self.context = zmq.Context.instance()
        self.other_requests=dict()
        self.done = False


    def init(self):
        """
        Initialise coroutine and socket

        Returns
                -------
                True if coroutine init method returns True, otherwise False
        """
        # Socket to talk to GUI
        self.socket_pub = self.context.socket(zmq.PUB)

        if self.gui_address is not None:
            try:
                self.socket_pub.connect("tcp://" + self.gui_address)
            except zmq.error.ZMQError as e:
                print("Error {} tcp://{}".format(e, self.gui_address))
                return False

        if self.coroutine is None:
            return False
        if self.coroutine.init() == False:
            return False


    def run(self):
        """
        Method representing the thread’s activity.
        It gets a Python generator from its coroutine run method.
        It loops overs its generator and sends new input to its next stage,
        thanks to its ZMQ REQ socket.
        """
        generator = self.coroutine.run()
        if isinstance(generator,types.GeneratorType):
            self.update_gui()
            for result in generator:
                self.running = False
                self.nb_job_done += 1
                if isinstance(result,tuple):
                    msg,destination = self.get_destination_msg_from_result(result)
                    self.send_msg(msg,destination)
                else:
                    self.send_msg(result)
                self.update_gui()
                self.running = True
                self.update_gui()
            self.running = False
            self.update_gui()
        else:
            print("Warning: Productor run method was not a python generator.")
            print("Warning: Pipeline worked, but number of jobs done for producer stayed at 0.")
            print("Warning: Add yield to end of run producer method.")
        self.socket_pub.close()
        self.done = True

    def finish(self):
        """
        Executes coroutine method
        """
        while self.done != True:
            return False
        self.coroutine.finish()
        return True

    def update_gui(self):
        msg = [self.name, self.running, self.nb_job_done]
        self.socket_pub.send_multipart(
            [b'GUI_PRODUCER_CHANGE', pickle.dumps(msg)])
