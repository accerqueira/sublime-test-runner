Sublime Test Runner
===================

Installation
------------
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
