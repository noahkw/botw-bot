class Job:
    def __init__(self, func, args, exec_time):
        self.func = func
        self.args = args
        self.exec_time = exec_time

    def __eq__(self, other):
        if not isinstance(other, Job):
            return NotImplemented
        return self.func == other.func and self.args == other.args and self.exec_time == other.exec_time

    def to_dict(self):
        return {
            'func': self.func,
            'args': self.args,
            'exec_time': self.exec_time
        }

    @staticmethod
    def from_dict(source):
        return Job(source['func'], source['args'], source['exec_time'])

    def __str__(self):
        return f'Job: {self.func} with arguments {self.args} at {self.exec_time}'