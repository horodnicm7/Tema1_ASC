"""
This module represents a device.

Computer Systems Architecture Course
Assignment 1
March 2019
"""

from threading import Event, Thread, Condition, Lock
from Queue import Queue


class ThreadPool(object):
    def __init__(self, num_threads, device):
        self.__device = device
        self.__queue = Queue(num_threads)
        self.__threads = [Thread(target=self.work) for _ in range(num_threads)]

        for thread in self.__threads:
            thread.start()

    def work(self):
        while True:
            script, location, neighbours = self.__queue.get()

            if not script and not neighbours:
                self.__queue.task_done()
                break

            script_data = []

            # collect data from current neighbours
            for device in neighbours:
                if self.__device.device_id != device.device_id:
                    data = device.get_data(location)
                    if data is not None:
                        script_data.append(data)

            # add our data, if any
            data = self.__device.get_data(location)
            if data is not None:
                script_data.append(data)

            if script_data != []:
                # run script on data
                result = script.run(script_data)

                # update data of neighbours
                for device in neighbours:
                    if self.__device.device_id != device.device_id:
                        device.set_data(location, result)

                # update our data
                self.__device.set_data(location, result)
            self.__queue.task_done()

    def add_task(self, script, location, neighbours):
        self.__queue.put((script, location, neighbours))

    def wait_threads(self):
        self.__queue.join()

    def stop_threads(self):
        self.__queue.join()

        for thread in self.__threads:
            self.__queue.put((None, None, None))

        for thread in self.__threads:
            thread.join()


class ReusableBarrierCond():
    """ Bariera reentranta, implementata folosind o variabila conditie """

    def __init__(self, num_threads):
        self.num_threads = num_threads
        self.count_threads = self.num_threads
        self.cond = Condition()  # blocheaza/deblocheaza thread-urile
        # protejeaza modificarea contorului

    def wait(self):
        self.cond.acquire()  # intra in regiunea critica
        self.count_threads -= 1
        if self.count_threads == 0:
            self.cond.notify_all()  # deblocheaza toate thread-urile
            self.count_threads = self.num_threads
        else:
            self.cond.wait()  # blocheaza thread-ul eliberand in acelasi timp lock-ul
        self.cond.release()  # iese din regiunea critica


class Device(object):
    """
    Class that represents a device.
    """
    num_threads = 8

    def __init__(self, device_id, sensor_data, supervisor):
        """
        Constructor.
        @type device_id: Integer
        @param device_id: the unique id of this node; between 0 and N-1
        @type sensor_data: List of (Integer, Float)
        @param sensor_data: a list containing (location, data) as measured by this device
        @type supervisor: Supervisor
        @param supervisor: the testing infrastructure's control and validation component
        """
        self.device_id = device_id
        self.sensor_data = sensor_data
        self.supervisor = supervisor
        self.script_received = Event()
        self.script_received.clear()
        self.scripts = []
        self.timepoint_done = Event()
        self.thread = DeviceThread(self)
        self.thread.start()
        self.barrier = None

    def __str__(self):
        """
        Pretty prints this device.
        @rtype: String
        @return: a string containing the id of this device
        """
        return "Device %d" % self.device_id

    def setup_devices(self, devices):
        """
        Setup the devices before simulation begins.
        @type devices: List of Device
        @param devices: list containing all devices
        """
        # we don't need no stinkin' setup
        if self.device_id == 0:
            self.barrier = ReusableBarrierCond(len(devices))
            for device in devices:
                if device.device_id != 0:
                    device.barrier = self.barrier

    def assign_script(self, script, location):
        """
        Provide a script for the device to execute.
        @type script: Script
        @param script: the script to execute from now on at each timepoint; None if the
            current timepoint has ended
        @type location: Integer
        @param location: the location for which the script is interested in
        """
        if script is not None:
            self.scripts.append((script, location))
            self.script_received.set()
        else:
            self.timepoint_done.set()

    def get_data(self, location):
        """
        Returns the pollution value this device has for the given location.
        @type location: Integer
        @param location: a location for which obtain the data
        @rtype: Float
        @return: the pollution value
        """
        return self.sensor_data[location] if location in self.sensor_data else None

    def set_data(self, location, data):
        """
        Sets the pollution value stored by this device for the given location.
        @type location: Integer
        @param location: a location for which to set the data
        @type data: Float
        @param data: the pollution value
        """
        if location in self.sensor_data:
            self.sensor_data[location] = data

    def shutdown(self):
        """
        Instructs the device to shutdown (terminate all threads). This method
        is invoked by the tester. This method must block until all the threads
        started by this device terminate.
        """
        self.thread.join()


class DeviceThread(Thread):
    """
    Class that implements the device's worker thread.
    """

    def __init__(self, device):
        """
        Constructor.
        @type device: Device
        @param device: the device which owns this thread
        """
        Thread.__init__(self, name="Device Thread %d" % device.device_id)
        self.device = device
        self.pool = ThreadPool(Device.num_threads, device)

    def run(self):
        # hope there is only one timepoint, as multiple iterations of the loop are not supported
        while True:
            # get the current neighbourhood
            neighbours = self.device.supervisor.get_neighbours()
            if neighbours is None:
                break

            while True:
                if self.device.script_received.is_set():
                    for script, location in self.device.scripts:
                        self.pool.add_task(script, location, neighbours)

                    self.device.script_received.clear()

                if self.device.timepoint_done.is_set():
                    self.device.timepoint_done.clear()
                    self.device.script_received.set()
                    break

            self.pool.wait_threads()
            self.device.barrier.wait()

        self.pool.stop_threads()
