Sublime Test Runner
===================

Installation
------------
**The easiest way to install is via the [Sublime Package Control](http://wbond.net/sublime_packages/package_control) plugin.**
Bring down your Command Palette (``Command+Shift+P`` on OS X, ``Control+Shift+P`` on Linux/Windows), open "Package Control: Install Package" (in your Command Palette) and search for "Test Runner". That's it!

To install it **manually without Git:** Download the latest source from [GitHub](http://github.com/accerqueira/sublime-test-runner), copy the whole directory into the Packages directory and rename it to "Test Runner".

To install it **manually with Git:** Clone the repository in your Sublime Text 2 Packages directory:

    git clone https://github.com/accerqueira/sublime-test-runner.git "Test Runner"


The "Packages" directory should be located at:

* OS X:

    ~/Library/Application\ Support/Sublime\ Text\ 2/Packages/

* Linux:

    ~/.Sublime\ Text\ 2/Packages/  
    or  
    ~/.config/sublime-text-2/Packages/

* Windows:

    %APPDATA%/Sublime Text 2/Packages/


The plugin should be picked up automatically. If not, restart Sublime Text.


Usage
-----

Test Runner will, by default, run ``make test REPORTER=tap`` whenever you save a file. You can also bring down the Command Palette and look for "Test Runner" available commands.

For test result coloring, you can add something like this to your color scheme file:

```xml
    <dict>
        <key>name</key>
        <string>Test PASS</string>
        <key>scope</key>
        <string>test.status.pass</string>
        <key>settings</key>
        <dict>
            <key>foreground</key>
            <string>#33FF33</string>
        </dict>
    </dict>
    <dict>
        <key>name</key>
        <string>Test FAIL</string>
        <key>scope</key>
        <string>test.status.fail</string>
        <key>settings</key>
        <dict>
            <key>foreground</key>
            <string>#FF3333</string>
        </dict>
    </dict>
    <dict>
        <key>name</key>
        <string>Test SKIP</string>
        <key>scope</key>
        <string>test.status.skip</string>
        <key>settings</key>
        <dict>
            <key>foreground</key>
            <string>#999999</string>
        </dict>
    </dict>
    <dict>
        <key>name</key>
        <string>Test TODO</string>
        <key>scope</key>
        <string>test.status.todo</string>
        <key>settings</key>
        <dict>
            <key>foreground</key>
            <string>#FFFF33</string>
        </dict>
    </dict>
```

For more customization, the following scopes are available...

 - ...for tests marked as passed:
    - ``test.result.pass``  
    - ``test.status.pass``  
    - ``test.description.pass``

 - ...for tests marked as failed:
    - ``test.result.fail``  
    - ``test.status.fail``  
    - ``test.description.fail``

 - ...for tests marked as skipped:
    - ``test.result.skip``  
    - ``test.status.skip``  
    - ``test.description.skip``

 - ...for tests marked as todo:
    - ``test.result.todo``  
    - ``test.status.todo``  
    - ``test.description.todo``
