"""
This module represents a device.

Computer Systems Architecture Course
Assignment 1
March 2019
"""

from threading import Event, Thread, Lock, Semaphore, Condition
from time import sleep


class ReusableBarrierCond():
    """ Bariera reentranta, implementata folosind o variabila conditie """

    def __init__(self, num_threads):
        self.num_threads = num_threads
        self.count_threads = self.num_threads
        self.cond = Condition()  # blocheaza/deblocheaza thread-urile
        # protejeaza modificarea contorului

    def wait(self):
        self.cond.acquire()  # intra in regiunea critica
        self.count_threads -= 1;
        if self.count_threads == 0:
            self.cond.notify_all()  # deblocheaza toate thread-urile
            self.count_threads = self.num_threads
        else:
            self.cond.wait()  # blocheaza thread-ul eliberand in acelasi timp lock-ul
        self.cond.release()  # iese din regiunea critica


class DeviceBarrier():
    def __init__(self):
        self.num_threads = 0
        self.count_threads = 0
        self.cond = Condition()  # blocheaza/deblocheaza thread-urile

    def add_thread(self):
        self.num_threads += 1
        self.count_threads += 1

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
    update_data = Lock()
    wait_devs = DeviceBarrier()
    thread_limit = 8

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
        self.scripts = []
        self.tmp = 0
        self.timepoint_done = Event()
        Device.wait_devs.add_thread()
        self.__start_threads()

    def __start_threads(self):
        self.nr_threads = self.thread_limit if len(self.sensor_data) > self.thread_limit\
                            else len(self.sensor_data)
        barrier = ReusableBarrierCond(self.nr_threads) #SimpleBarrier(self.nr_threads)
        print("Number of threads: {0} for {1}".format(self.nr_threads, self))
        print("{0} has {1}".format(self, self.sensor_data))
        self.threads = []
        for i in range(self.nr_threads):
            self.threads.append(DeviceThread(self, i, barrier))

        for thread in self.threads:
            thread.start()

    def __stop_threads(self):
        for thread in self.threads:
            thread.join()

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
        pass

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
            self.script_received.clear()
            self.timepoint_done.clear()
        else:
            self.timepoint_done.set()
            self.tmp += 1

    def get_data(self, location):
        """
        Returns the pollution value this device has for the given location.

        @type location: Integer
        @param location: a location for which obtain the data

        @rtype: Float
        @return: the pollution value
        """
        print("{0} returns {1} for location {2}".format(self, self.sensor_data[location], location))
        return self.sensor_data[location] if location in self.sensor_data else None

    def set_data(self, location, data):
        """
        Sets the pollution value stored by this device for the given location.

        @type location: Integer
        @param location: a location for which to set the data

        @type data: Float
        @param data: the pollution value
        """
        #self.update_data.set()
        if location in self.sensor_data:
            self.sensor_data[location] = data
        #self.update_data.clear()

    def shutdown(self):
        """
        Instructs the device to shutdown (terminate all threads). This method
        is invoked by the tester. This method must block until all the threads
        started by this device terminate.
        """
        #self.thread.join()
        self.__stop_threads()


class DeviceThread(Thread):
    def __init__(self, device, th_id, tmp_barrier):
        """
        Constructor.

        @type device: Device
        @param device: the device which owns this thread
        """
        Thread.__init__(self, name="Device Thread %d" % device.device_id)
        self.device = device
        self.thread_id = th_id
        self.tmp_barrier = tmp_barrier

    def run(self):
        while True:
            #print("{0} {1}".format(self.device, self.thread_id))
            # get the current neighbourhood
            neighbours = self.device.supervisor.get_neighbours()
            if neighbours is None:
                break

            #self.device.script_received.wait()
            #print("{0} {1} passed script waiting".format(self.device, self.thread_id))
            scripts = self.device.scripts

            start, end = 0, 0
            if self.device.nr_threads == len(scripts):
                start, end = self.thread_id, self.thread_id + 1
            if self.device.nr_threads > len(scripts):
                start = self.thread_id
                if self.thread_id + 1 > len(scripts):
                    end = start - 1

            if self.device.nr_threads < len(scripts):
                per_th = len(scripts) / self.device.nr_threads
                start, end = per_th * self.thread_id, per_th * (self.thread_id + 1)
                if self.thread_id == self.device.nr_threads - 1:
                    end = len(scripts)

            # run scripts received until now
            #for (script, location) in self.device.scripts:
            for (script, location) in scripts[start: end]:
                script_data = []
                # collect data from current neighbours
                for device in neighbours:
                    data = device.get_data(location)
                    if data is not None:
                        script_data.append(data)
                # add our data, if any
                data = self.device.get_data(location)
                if data is not None:
                    script_data.append(data)

                if script_data != []:
                    # run script on data
                    result = script.run(script_data)

                    Device.update_data.acquire()
                    # update data of neighbours, hope no one is updating at the same time
                    for device in neighbours:
                        device.set_data(location, result)
                    # update our data, hope no one is updating at the same time
                    self.device.set_data(location, result)
                    Device.update_data.release()

            #print("{0} {1} Waiting".format(self.device, self.thread_id))
            #self.device.script_received.set()
            self.tmp_barrier.wait()
            self.device.wait_devs.wait()

'''
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

    def run(self):
        # hope there is only one timepoint, as multiple iterations of the loop are not supported
        while True:
            # get the current neighbourhood
            neighbours = self.device.supervisor.get_neighbours()
            if neighbours is None:
                break

            self.device.script_received.wait()

            # run scripts received until now
            for (script, location) in self.device.scripts:
                script_data = []
                # collect data from current neighbours
                for device in neighbours:
                    data = device.get_data(location)
                    if data is not None:
                        script_data.append(data)
                # add our data, if any
                data = self.device.get_data(location)
                if data is not None:
                    script_data.append(data)

                if script_data != []:
                    # run script on data
                    result = script.run(script_data)

                    self.device.update_data.acquire()
                    print("Blocked like a cunt {0}".format(self))
                    # update data of neighbours, hope no one is updating at the same time
                    for device in neighbours:
                        device.set_data(location, result)
                    # update our data, hope no one is updating at the same time
                    self.device.set_data(location, result)
                    self.device.update_data.release()

            # hope we don't get more than one script
            print("{0} has timepoint {1}. Timepoint done {2}".format(self.device, self.device.tmp, self.device.timepoint_done.is_set()))
            #self.device.timepoint_done.wait()
            self.device.barrier.wait()'''