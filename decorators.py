import time
import sublime

class LazyDecorator():
    def __init__(self, seconds, limit):
        self.last_time = time.time() - seconds
        self.queue = []
        self.processing_queue = False
        self.seconds = seconds
        self.limit = limit

    def call(self, fn):
        def decorated_fn(*params):
            if len(self.queue) < self.limit:
                self.queue.append((fn, params))
                if not self.processing_queue:
                    self.process_queue()

        return decorated_fn

    def call_now(self, fn, *params):
        self.last_time = time.time()
        rv = fn(*params)
        self.process_queue()
        return rv

    def process_queue(self):
        curr_time = time.time()
        elapsed = curr_time - self.last_time

        if elapsed < self.seconds:
            wait_time = int(1000 * (self.seconds - elapsed))
        else:
            wait_time = 0

        try:
            (fn, params) = self.queue.pop(0)
            self.processing_queue = True
            sublime.set_timeout(lambda: self.call_now(fn, *params), wait_time)
        except IndexError:
            self.processing_queue = False

class ThrottleDecorator(LazyDecorator):
    def __init__(self, seconds):
        LazyDecorator.__init__(self, seconds, 1)


def lazy(seconds, limit):
    """Lazy policy, will queue up to {limit} executions and wait {seconds} milliseconds for each one."""
    decorator = LazyDecorator(seconds, limit)
    return decorator.call

def throttle(seconds):
    """Throttling policy, will only be executed once per {seconds} milliseconds"""
    decorator = ThrottleDecorator(seconds)
    return decorator.call
