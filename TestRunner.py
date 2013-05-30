import sys, os.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threading
import subprocess
import traceback
import time
import re
import parsers
from decorators import throttle

import sublime, sublime_plugin


class Settings():
    def __init__(self):
        self.s = None

    def load(self):
        if self.s is None:
            self.s = sublime.load_settings('TestRunner.sublime-settings')        

    def get(self, key, default=None):
        self.load()

        return self.s.get(key, default)

    def set(self, key, value):
        self.load()

        return self.s.set(key)

settings = Settings()


def project_directory(path):
    path = os.path.normpath(os.path.dirname(path))
    path_parts = path.split(os.path.sep)
    spec_directories = ['test', 'tests', 'spec', 'specs']

    while path_parts:
        for spec_directory in spec_directories:
            joined = os.path.normpath(os.path.sep.join(path_parts + [spec_directory]))

            if os.path.exists(joined) and os.path.isdir(joined):
                return os.path.normpath(os.path.sep.join(path_parts))

        path_parts.pop()


class RunTestsCommand(sublime_plugin.TextCommand):
    description = 'Runs the configured test command on save.'

    def run(self, *args, **kwargs):
        #print('RunTestsCommand.run', args, kwargs)
        command = settings.get('test_command')
        if 'with_coverage' in kwargs and kwargs['with_coverage']:
            command = settings.get('test_with_coverage_command')

        working_directory = project_directory(self.view.file_name())
        if working_directory:
            TestRunner.start(self.view, working_directory, command)


class TestRunner():
    worker = None
    @classmethod
    def start(self, view, working_directory, command):
        if self.worker and self.worker.is_alive():
            if (settings.get('test_override')):
                self.worker.stop()
            else:
                return

        self.worker = TestRunnerWorker(view, working_directory, command)


class TestRunnerWorker(threading.Thread):
    def __init__(self, view, working_directory, command):
        self.view = view
        self.working_directory = working_directory
        self.command = command
        self.process = None
        self.start_time = time.time()
        self.timeout = settings.get('test_timeout', 60)
        self.result = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'todo': 0,
            'executed': 0,
            'missing': 0,
            'total': 0,
            'status': 'running',
            'message': ''
        }

        threading.Thread.__init__(self)
        self.start()

    def run(self):
        try:
            self.check_timeout()
            self.update_status()
            self.update_panel()

            self.process = subprocess.Popen(self.command, shell=True, cwd=self.working_directory, universal_newlines=True, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            tapParser = parsers.TapParser(self.process.stdout)
            #tapParser.signal['line'].add(self.stdout_line)
            tapParser.signal['tests_planned'].add(self.tests_planned)
            tapParser.signal['test_case'].add(self.test_case)
            tapParser.signal['tests_completed'].add(self.tests_completed)
            tapParser.parse()

            #lineParser = parsers.LineParser(self.process.stderr)
            #lineParser.signal['line'].add(self.stderr_line)
            #lineParser.parse()

            #print('Tests completed!')

        except RuntimeError:
            print('Unexpected error running tests:')
            traceback.print_exc()
        except Exception:
            print('Unexpected error running tests:')
            traceback.print_exc()

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process = None
        #self.join(5)
        #if self.is_alive():
        #    print('Well, this is embarasing... A worker thread refuses to die.')

    def tests_planned(self, start, end):
        self.result['total'] = end

        self.update_status()

    def tests_completed(self):
        self.result['missing'] = self.result['total'] - self.result['executed']
        self.result['total'] = self.result['executed']
        self.result['status'] = 'executed'

        self.update_panel()
        self.update_status()

    def test_case(self, status, number, description, directive):
        if status:
            self.result['passed'] += 1
            status_message = 'PASSED'
        elif directive['type'] == 'TODO':
            self.result['todo'] += 1
            status_message = 'TODO'
        elif directive['type'] == 'SKIP':
            self.result['skipped'] += 1
            status_message = 'SKIPPED'
        else:
            self.result['failed'] += 1
            status_message = 'FAILED'
        self.result['executed'] += 1

        self.result['message'] += '[{status}] {description}\n'.format(
            status = status_message,
            number = number,
            description = description)

        self.update_status()
        self.update_panel()

    def stdout_line(self, line):
        sys.stdout.write('STDOUT: {line}'.format(line=line))

    def stderr_line(self, line):
        sys.stdout.write('STDERR: {line}'.format(line=line))

    @throttle(1 / 25)
    def update_status(self):
        if self.result['total'] > 0:
            parts = [ '{executed}/{total} {status}' ]
        elif self.result['executed'] > 0:
            parts = [ '{executed}/? {status}' ]
        else:
            parts = [ '{status}' ]

        for status in ('passed', 'failed', 'missing', 'skipped', 'todo'):
            if self.result[status] > 0:
                parts.append('{{{status}}} {status}'.format(status=status))

        spinner = settings.get('progress_spinner', '-\|/')
        ticks = int((time.time() - self.start_time)  * 5)

        message = '[ '+ ' | '.join(parts) +' ]'
        if self.result['status'] == 'running':
            message = spinner[ticks % len(spinner)] +' '+ message

        self.view.set_status('Test Runner', 
            message.format(
                status = self.result['status'],
                passed = self.result['passed'], 
                failed = self.result['failed'], 
                skipped = self.result['skipped'], 
                todo = self.result['todo'], 
                executed = self.result['executed'], 
                missing = self.result['missing'], 
                total = self.result['total']))

        if self.is_alive():
            self.update_status()

    @throttle(0.1)
    def update_panel(self):
        window = sublime.active_window() # self.view.window() would be None if self.view is not active
        if window is None:
            sublime.active_window().run_command('hide_panel', {'panel': 'output.test_runner'})
            return

        try:
            result_panel = window.create_output_panel('test_runner')
        except:
            result_panel = window.get_output_panel('test_runner')

        result_panel.run_command('update_panel', { 'message': self.result['message'] })

        if self.result['failed'] > 0 or settings.get('show_panel_default', False):
            window.run_command('show_panel', {'panel': 'output.test_runner'})
        elif self.result['status'] == 'executed':
            window.run_command('hide_panel', {'panel': 'output.test_runner'})

        if self.is_alive():
            self.update_panel()

    @throttle(0.5)
    def check_timeout(self):
        current_time = time.time()
        if current_time > self.start_time + self.timeout:
            self.stop()

        if self.is_alive():
            self.check_timeout()


class UpdatePanelCommand(sublime_plugin.TextCommand):
    description = 'Updates panel with test results.'

    def run(self, edit, message, *args, **kwargs):
        #print('UpdatePanelCommand.run', args, kwargs)

        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, self.view.size(), message)

        self.view.show(self.view.size())


class PostSaveListener(sublime_plugin.EventListener):
    def on_post_save(self, view): # on_post_save_async?
        #print('PostSaveListener.on_post_save')

        if not settings.get('test_on_save', True):
            return

        if settings.get('test_with_coverage_default', False):
            view.run_command('run_tests', {'with_coverage': True})
        else:
            view.run_command('run_tests')
