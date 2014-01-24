import sys
import os.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threading
import subprocess
import time

import sublime
import sublime_plugin

import logging
import logging.handlers

logger = logging.getLogger('test_runner')

logger.handlers = []

formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')
hdlr = logging.handlers.TimedRotatingFileHandler(__name__ + '.log', interval=1, backupCount=4)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)

logger.debug('> loading python file "%s"', __name__)


try:
    # Python 3
    from .test_runner import parsers
    from .test_runner.decorators import throttle
except (ValueError):
    # Python 2
    from test_runner import parsers
    from test_runner.decorators import throttle


def plugin_loaded():
    global logger

    setup_settings()
    setup_logger()

def setup_settings():
    global settings
    settings = Settings()

def setup_logger():
    global logger

    log_levels = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG
    }

    settings.clear_on_change('log_level')

    log_level = settings.get('log_level', 'WARNING').upper()
    logger.setLevel(log_levels[log_level])
    logger.info('setting log level to %s' % log_level)

    settings.add_on_change('log_level', setup_logger)


class Settings():
    def __init__(self):
        self.s = None

    def load(self):
        if self.s is None:
            self.s = sublime.load_settings('TestRunner.sublime-settings')

    def get(self, key, default=None):
        self.load()
        value = self.s.get(key, default)

        return value or default

    def set(self, key, value):
        self.load()

        return self.s.set(key, value)

    def add_on_change(self, key, on_change):
        self.load()

        self.s.add_on_change(key, on_change)

    def clear_on_change(self, key):
        self.load()

        self.s.clear_on_change(key)


def project_directory(path):
    path = os.path.normpath(os.path.dirname(path))
    path_parts = path.split(os.path.sep)
    spec_filenames = settings.get('test_spec_filenames', [])

    while path_parts:
        for spec_directory in spec_filenames:
            joined = os.path.normpath(
                os.path.sep.join(path_parts + [spec_directory])
            )

            if os.path.exists(joined):
                project_directory_path = os.path.normpath(os.path.sep.join(path_parts))
                return project_directory_path

        path_parts.pop()


class RunTestsCommand(sublime_plugin.TextCommand):
    description = 'Runs the configured test command on save.'

    def run(self, *args, **kwargs):
        #print('RunTestsCommand.run', args, kwargs)
        logger.debug('RunTestsCommand was triggered with arguments: %s' % (kwargs))
        command = settings.get('test_command')
        if 'with_coverage' in kwargs and kwargs['with_coverage']:
            command = settings.get('test_with_coverage_command')

        logger.debug(' |- command to execute is "%s"' % command)

        working_directory = project_directory(self.view.file_name())
        logger.debug('  |- working directory is "%s"' % working_directory)

        if working_directory:
            TestRunner.start(self.view, working_directory, command)


class TestRunner():
    worker = None

    @classmethod
    def start(self, view, working_directory, command):
        logger.debug('TestRunner start requested')
        if self.worker and self.worker.is_alive():
            logger.debug(' |- there is another worker alive...')
            if (settings.get('test_override')):
                logger.debug('  |- overriding current worker...')
                self.worker.stop()
            else:
                logger.debug('  |- ignoring request')
                return

        logger.debug(' |- starting a new worker for tests')
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
        self.logger = logging.getLogger('test_runner.%s' % self.name)
        self.start()

    def run(self):
        self.logger.debug('Testing thread started')
        try:
            self.check_timeout()
            self.update_status()
            self.update_panel()

            self.logger.debug(' |- spawning subprocess with command "%s"', self.command)
            self.logger.debug(' ||- working directory is "%s"', self.working_directory)
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                cwd=self.working_directory,
                universal_newlines=True,
                bufsize=1,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            tapParser = parsers.TapParser(self.process.stdout)
            tapParser.signal['line'].add(self.stdout_line)
            tapParser.signal['tests_planned'].add(self.tests_planned)
            tapParser.signal['test_case'].add(self.test_case)
            tapParser.signal['tests_completed'].add(self.tests_completed)
            tapParser.parse()

            lineParser = parsers.LineParser(self.process.stderr)
            lineParser.signal['line'].add(self.stderr_line)
            lineParser.parse()

            self.logger.debug(' |- subprocess finished!')


        except RuntimeError:
            print('Unexpected error running tests:')
            self.logger.exception('Unexpected error running tests')
        except Exception:
            print('Unexpected error running tests:')
            self.logger.exception('Unexpected error running tests')

        self.logger.debug('Testing thread finished')

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process = None
            self.logger.debug('Testing thread stopped')

    def tests_planned(self, start, end):
        self.logger.debug(' ||- subprocess reported %s..%s planned tests' % (start, end))
        self.result['total'] = end

        self.update_status()

    def tests_completed(self):
        self.logger.debug(' ||- subprocess reported tests completed!')
        self.result['missing'] = self.result['total'] - self.result['executed']
        self.result['total'] = self.result['executed']
        self.result['status'] = 'executed'

        self.update_panel()
        self.update_status()

    def test_case(self, status, number, description, directive):
        if status:
            self.result['passed'] += 1
            status_message = 'PASS'
        elif directive['type'] == 'TODO':
            self.result['todo'] += 1
            status_message = 'TODO'
        elif directive['type'] == 'SKIP':
            self.result['skipped'] += 1
            status_message = 'SKIP'
        else:
            self.result['failed'] += 1
            status_message = 'FAIL'

        self.logger.debug(' ||- subprocess reported test case #%d result: %s' % (number, status_message))
        self.result['executed'] += 1

        self.result['message'] += '[{status}] {description}\n'.format(
            status=status_message,
            number=number,
            description=description
        )

        self.update_status()
        self.update_panel()

    def stdout_line(self, line):
        self.logger.debug(' ||- subprocess stdout: %s', line.rstrip())

    def stderr_line(self, line):
        self.logger.debug(' ||- subprocess stderr: %s', line.rstrip())

    @throttle(1 / 25)
    def update_status(self):
        #self.logger.debug(' |- updating status')
        if self.result['total'] > 0:
            parts = ['{executed}/{total} {status}']
        elif self.result['executed'] > 0:
            parts = ['{executed}/? {status}']
        else:
            parts = ['{status}']

        for status in ('passed', 'failed', 'missing', 'skipped', 'todo'):
            if self.result[status] > 0:
                parts.append('{{{status}}} {status}'.format(status=status))

        spinner = settings.get('progress_spinner', '-\|/')
        ticks = int((time.time() - self.start_time) * 5)

        message = '[ ' + ' | '.join(parts) + ' ]'
        if self.result['status'] == 'running':
            message = spinner[ticks % len(spinner)] + ' ' + message

        self.view.set_status('Test Runner', message.format(
            status=self.result['status'],
            passed=self.result['passed'],
            failed=self.result['failed'],
            skipped=self.result['skipped'],
            todo=self.result['todo'],
            executed=self.result['executed'],
            missing=self.result['missing'],
            total=self.result['total'])
        )

        if self.is_alive():
            self.update_status()

    @throttle(0.1)
    def update_panel(self):
        #self.logger.debug(' |- updating report panel')
        window = sublime.active_window()

        try:
            result_panel = window.create_output_panel('test_runner')
        except:
            result_panel = window.get_output_panel('test_runner')

        result_panel.set_syntax_file('Packages/Test Runner/TestRunnerOutput.tmLanguage')

        result_panel.run_command(
            'update_panel',
            {'message': self.result['message']}
        )

        if (self.result['failed'] > 0 or
                settings.get('show_panel_default', False)):
            window.run_command('show_panel', {'panel': 'output.test_runner'})
        elif self.result['status'] == 'executed':
            window.run_command('hide_panel', {'panel': 'output.test_runner'})

        if self.is_alive():
            self.update_panel()

    @throttle(1)
    def check_timeout(self):
        current_time = time.time()
        elapsed_time = current_time - self.start_time

        if self.is_alive():
            self.logger.debug(' |- testing thread running for %d seconds' % elapsed_time)

        if elapsed_time > self.timeout:
            self.logger.debug(' |- testing thread timed out')
            self.stop()

        if self.is_alive():
            self.check_timeout()


class UpdatePanelCommand(sublime_plugin.TextCommand):
    description = 'Updates panel with test results.'

    def run(self, edit, message, *args, **kwargs):
        #print('UpdatePanelCommand.run', args, kwargs)
        #logger.debug('UpdatePanelCommand was triggered with arguments: %s' % (kwargs))

        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, self.view.size(), message)

        self.view.show(self.view.size())


class PostSaveListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        #print('PostSaveListener.on_post_save')
        logger.debug('PostSaveListener was triggered')

        if not settings.get('test_on_save', True):
            logger.debug(' |- testing on save is disabled')
            return

        if settings.get('test_with_coverage_default', False):
            logger.debug(' |- triggering [Run Tests with coverage] (enabled on settings)')
            view.run_command('run_tests', {'with_coverage': True})
        else:
            logger.debug(' |- triggering [Run Tests]')
            view.run_command('run_tests')

logger.debug('< loading python file "%s"', __name__)


st_version = 2

# Warn about out-dated versions of ST3
if sublime.version() == '':
    st_version = 3
    print('Package Control: Please upgrade to Sublime Text 3 build 3012 or newer')
elif int(sublime.version()) > 3000:
    st_version = 3

if st_version == 2:
    plugin_loaded()
