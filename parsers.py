import re


class TapParser():
    def __init__(self, source):
        self.source = source
        self.signal = {
            'line': Signal(),
            'version': Signal(),
            'comment': Signal(),
            'tests_planned': Signal(),
            'test_case': Signal(),
            'test_case_detail': Signal(),
            'tests_completed': Signal()
        }

    def advance(self):
        if self.source is None:
            return

        self.current_line = self.source.readline()

        if len(self.current_line) > 0:
            eof = False
            self.signal['line'].dispatch(self.current_line)
        else:
            eof = True

        return (not eof)

    def parse(self):
        self.advance()

        self.parse_version()
        self.parse_tests_planned()
        ok = True
        while ok:
            test_case = self.parse_test_case()
            if test_case:
                self.parse_test_case_detail()
            else:
                ok = self.advance()

        self.signal['tests_completed'].dispatch()

    def skip_empty(self):
        regex = re.compile(r'^\s+$', re.X | re.I)
        while regex.match(self.current_line):
            self.advance()

    def parse_comments(self):
        self.skip_empty()

        regex = re.compile(r'^\s*\#(?P<comment>.+)\s*$', re.X | re.I)

        comment = ''
        match = regex.match(self.current_line)
        while match:
            comment += match.group('comment')
            self.advance()
            self.skip_empty()
            match = regex.match(self.current_line)

        if len(comment) > 0:
            result = {'comment': comment}
            self.signal['comment'].dispatch(**result)
            return result

    def parse_version(self):
        self.parse_comments()

        regex = re.compile(r'''^    \s*
            TAP\s*version\s*(?P<version>\d+)   \s*
            $''', re.X | re.I)

        match = regex.match(self.current_line)
        if match:
            self.advance()
            version = int(match.group('version'))
        else:
            version = 12

        result = {'version': version}
        self.signal['version'].dispatch(**result)
        return result

    def parse_tests_planned(self):
        self.parse_comments()

        regex = re.compile(r'''             \s*
            (?P<start>\d+)..(?P<end>\d+)    \s*
            $''', re.X | re.I)

        match = regex.match(self.current_line)
        if match:
            self.advance()
            result = {
                'start': int(match.group('start')),
                'end': int(match.group('end'))
            }
            self.signal['tests_planned'].dispatch(**result)
            return result

    def parse_test_case(self):
        self.parse_comments()

        regex = re.compile(r'''^                                                                \s*
            (?P<status>ok|not\sok)                                                              \s*
            (?P<number>\d+)?                                                                    \s*
            (?:-\s*)?(?P<description>.+?)                                                       \s*
            (?:\#\s*(?:(?P<directive_type>TODO|SKIP)\s)?\s*(?P<directive_description>.*))?      \s*
            $''', re.X | re.I)

        def isok(s):
            return (s.upper() == 'OK')

        match = regex.match(self.current_line)
        if match:
            self.advance()
            directive_type = None
            if match.group('directive_type'):
                directive_type = match.group('directive_type').upper()
            result = {
                'status': isok(match.group('status')),
                'number': int(match.group('number')),
                'description': match.group('description'),
                'directive': {
                    'type': directive_type,
                    'description': match.group('directive_description')
                }
            }
            self.signal['test_case'].dispatch(**result)
            #time.sleep(1) # for the lulz
            return result

    def parse_test_case_detail(self):
        self.parse_comments()

        yaml_start = re.compile(r'\s*---\s*$', re.X | re.I)
        yaml_end = re.compile(r'\s*...\s*$', re.X | re.I)

        yaml = ''
        match = yaml_start.match(self.current_line)
        if match:
            self.advance()
            while not yaml_end.match(self.current_line):
                yaml += self.current_line
                self.advance()

        if len(yaml) > 0:
            result = {'yaml': yaml}
            self.signal['test_case_detail'].dispatch(**result)
            return result


class LineParser():
    def __init__(self, source):
        self.source = source
        self.signal = {
            'line': Signal(),
            'completed': Signal()
        }

    def advance(self):
        if self.source is None:
            return

        self.current_line = self.source.readline()
        self.signal['line'].dispatch(self.current_line)

        return (not len(self.current_line) == 0)

    def parse(self):
        self.advance()

        while self.advance():
            pass

        self.signal['completed'].dispatch()


class Signal(list):
    def __init__(self, *args):
        list.__init__(self, *args)

    def add(self, listener):
        list.append(self, listener)

    def dispatch(self, *args, **kwargs):
        for listener in self:
            listener(*args, **kwargs)
