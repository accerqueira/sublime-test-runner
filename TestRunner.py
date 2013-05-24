import os
import sys
import threading
import subprocess
import traceback
import time
import re
import parser

import sublime, sublime_plugin

settings = sublime.load_settings('TestRunner.sublime-settings')

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
        self.check_timeout()

    def run(self):
        try:
            self.update_status()
            self.update_panel()

            self.process = subprocess.Popen(self.command, shell=True, cwd=self.working_directory, universal_newlines=True, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            tapParser = parser.TapParser(self.process.stdout)
            #tapParser.signal['line'].add(self.stdout_line)
            tapParser.signal['tests_planned'].add(self.tests_planned)
            tapParser.signal['test_case'].add(self.test_case)
            tapParser.signal['tests_completed'].add(self.tests_completed)
            tapParser.parse()

            #lineParser = parser.LineParser(self.process.stderr)
            #lineParser.signal['line'].add(self.stderr_line)
            #lineParser.parse()

            #print('Tests completed!')

        except RuntimeError, err:
            print 'Unexpected error running tests:', sys.exc_info()[0], str(err)
            traceback.print_tb(sys.last_traceback)
        except Exception, err:
            print 'Unexpected error running tests:', sys.exc_info()[0], str(err)
            traceback.print_tb(sys.last_traceback)

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process = None
        #self.join(5)
        #if self.is_alive():
        #    print('Well, this is embarasing... A worker thread refuses to die.')

    def tests_planned(self, start, end):
        self.result['total'] = end

        sublime.set_timeout(self.update_status, 50)

    def tests_completed(self):
        self.result['missing'] = self.result['total'] - self.result['executed']
        self.result['total'] = self.result['executed']
        self.result['status'] = 'executed'

        sublime.set_timeout(self.update_panel, 50)
        sublime.set_timeout(self.update_status, 50)

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

        sublime.set_timeout(self.update_status, 50)
        sublime.set_timeout(self.update_panel, 50)

    def stdout_line(self, line):
        sys.stdout.write('STDOUT: {line}'.format(line=line))

    def stderr_line(self, line):
        sys.stdout.write('STDERR: {line}'.format(line=line))

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

        self.view.set_status('Test Runner', 
            ('[ '+ ' | '.join(parts) +' ]').format(
                status = self.result['status'],
                passed = self.result['passed'], 
                failed = self.result['failed'], 
                skipped = self.result['skipped'], 
                todo = self.result['todo'], 
                executed = self.result['executed'], 
                missing = self.result['missing'], 
                total = self.result['total']))

    def update_panel(self):
        window = sublime.active_window() # self.view.window() would be None if self.view is not active
        if window is None:
            sublime.active_window().run_command('hide_panel', {'panel': 'output.test_runner'})
            return

        out = window.get_output_panel('test_runner')
        edit = out.begin_edit()

        out.erase(edit, sublime.Region(0, out.size()))

        out.insert(edit, out.size(), self.result['message'])

        out.show(out.size())
        out.end_edit(edit)

        if self.result['failed'] > 0 or settings.get('show_panel_default', False):
            window.run_command('show_panel', {'panel': 'output.test_runner'})
        elif self.result['status'] == 'executed':
            window.run_command('hide_panel', {'panel': 'output.test_runner'})

    def check_timeout(self):
        if not self.is_alive():
            return

        current_time = time.time()
        if current_time > self.start_time + self.timeout:
            self.stop()
        else:
            sublime.set_timeout(self.check_timeout, 500)



class PostSaveListener(sublime_plugin.EventListener):
    def on_post_save(self, view): # on_post_save_async?
        #print('PostSaveListener.on_post_save')

        if not settings.get('test_on_save', True):
            return

        if settings.get('test_with_coverage_default', False):
            view.run_command('run_tests', {'with_coverage': True})
        else:
            view.run_command('run_tests')
