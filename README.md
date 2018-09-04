Pollbot
=======
Pollbot is a [Matrix](https://matrix.org) bot written using [python-matrix-bot-api](https://github.com/shawnanastasio/python-matrix-bot-api) that allows you to create and vote on polls.

Requirements
------------
* Python 3
* python-matrix-bot-api (matrix-bot-api on pip)

Docker
------------
First build the image with
     docker build -t pollbot .
 Now you can start the image
     docker run pollbot
 Just configure the config.ini to your own specs.

Usage
-----
Copy `config.ini.example` to `config.ini` and fill in your bot's Matrix credentials.

Then simply invite Pollbot to your room and use `!startpoll` to create a new poll.
See `!pollhelp` for more information

License
-------
GNU GPL v3

Pull requests welcome!
