from matrix_bot_api.matrix_bot_api import MatrixBotAPI
from matrix_bot_api.mhandler import MHandler
from matrix_bot_api.mregex_handler import MRegexHandler
from matrix_bot_api.mcommand_handler import MCommandHandler

import configparser
import pickle
import time
from functools import wraps

# Bot's Matrix credentials
M_USERNAME = ""
M_PASSWORD = ""
M_SERVER = ""

bot = None

def checkEventTime(f):
    @wraps(f)
    def decorated(*args,**kwargs):
        event = args[1]
        if int(time.time()) - int((event['origin_server_ts']/1000))  < 5:
            return f(*args,**kwargs)
    return decorated


class AllMessageHandler(MHandler):
    def __init__(self, handle_callback):
        MHandler.__init__(self, self.check_update, handle_callback)

    def check_update(self, room, event):
        if event['type'] == "m.room.message":
            return True
        return False


class Vote(object):
    def __init__(self, user_id, choice_idx):
        self.user_id = user_id
        self.choice_idx = choice_idx


class Poll(object):
    def __init__(self, room_id, creator, question, choices):
        self.room_id = room_id
        self.creator = creator
        self.question = question
        self.choices = choices
        self.votes = []


# Load from existing pickle database, create if unable to load
try:
    DB = pickle.load(open("pollbot.pickledb", "rb"))
except (OSError, IOError):
    # Ongoing, Incomplete. Ended
    DB = [[], [], []]
    pickle.dump(DB, open("pollbot.pickledb", "wb"), 4)

# List of ongoing polls. One per room
ONGOING_POLLS = DB[0]

# List of incomplete poll objects that are being created
ONGOING_POLLCREATIONS = DB[1]

# List of ended polls. Only stores one per room
ENDED_POLLS = DB[2]

@checkEventTime
def newpoll_callback(room, event):
    # Make sure we don't have an ongoing poll for this room
    for poll in ONGOING_POLLS:
        if poll.room_id == room.room_id:
            room.send_notice(
                "There's already an ongoing poll \
                in this room! Please end it before \
                starting a new one."
            )
            return

    # Make sure we don't have an ongoing poll creation for this room
    for poll in ONGOING_POLLCREATIONS:
        if poll.room_id == room.room_id:
            room.send_notice(
                "There's already an ongoing poll\
                in this room! Please end it before \
                starting a new one."
            )
            return

    # Create an incomplete Poll object and add it to ONGOING_POLLCREATIONS
    new_poll = Poll(room.room_id, event['sender'], None, None)
    ONGOING_POLLCREATIONS.append(new_poll)

    # Prompt the user for a question
    room.send_notice("Creating a new poll. Please send the question.")

    # When they respond, it will be handled by the ongoing handler

    # Update database on disk
    pickle.dump([ONGOING_POLLS, ONGOING_POLLCREATIONS, ENDED_POLLS],
                open("pollbot.pickledb", "wb"),
                4)


# Handles ongoing poll creations
@checkEventTime
def ongoing_poll_callback(room, event):
    # Make sure this room has an ongoing poll creation and
    # it was created by the message sender
    if event['content']['body'][0] == '!':
        return

    poll = None
    for p in ONGOING_POLLCREATIONS:
        if p.room_id == room.room_id and p.creator == event['sender']:
            poll = p
            break
    if poll is None:
        return

    # See which part to handle
    if poll.question is None:
        poll.question = event['content']['body']
        room.send_notice(
            "Okay, now send me the choices one by one. \
            Type !startpoll to start the poll."
        )
    else:
        # Handle message as a choice
        if poll.choices is None:
            poll.choices = []

        poll.choices.append(event['content']['body'])
        room.send_notice(
            "Response added. Send another choice or \
            type !startpoll to start the poll"
        )

    # Update database on disk
    pickle.dump([ONGOING_POLLS, ONGOING_POLLCREATIONS, ENDED_POLLS],
                open("pollbot.pickledb", "wb"),
                4)


# Add new response to current poll
# The command is like !add burger
@checkEventTime
def add_response_to_poll(room, event):
    if len(event['content']['body']) <= 5:
        room.send_notice("No choice was given")
        return

    poll = None
    for p in ONGOING_POLLS:
        if p.room_id == room.room_id:
            poll = p
            break
    if poll is None:
        room.send_notice("There are no polls!")
        return
    poll.choices.append(event['content']['body'][5:])
    room.send_notice("Response added.")

    # Update database on disk
    pickle.dump([ONGOING_POLLS, ONGOING_POLLCREATIONS, ENDED_POLLS],
                open("pollbot.pickledb", "wb"),
                4)


# Starts a poll (moves from an ongoing poll creation to an ongoing poll)
@checkEventTime
def startpoll_callback(room, event):
    # Make sure there's an ongoing poll creation and
    # it was created by the message sender
    poll = None
    for p in ONGOING_POLLCREATIONS:
        if p.room_id == room.room_id and p.creator == event['sender']:
            poll = p
            break
    if poll is None:
        room.send_notice("There are no polls you can start!")
        return

    # Confirm that the poll is ready and
    # move it from ONGOING_POLLCREATIONS to ONGOING_POLLS
    if poll.question is None:
        room.send_notice("You need to send a question first!")
        return

    if poll.choices is None or len(poll.choices) < 2:
        room.send_notice("You need to send at least two choices first!")
        return

    # Remove the poll from ONGOING_POLLCREATIONS and add to ONGOING_POLLS
    ONGOING_POLLCREATIONS.remove(poll)
    ONGOING_POLLS.append(poll)

    room.send_notice("Poll started! Repeat the question with !info")
    info_callback(room, event)

    # Update database on disk
    pickle.dump([ONGOING_POLLS, ONGOING_POLLCREATIONS, ENDED_POLLS],
                open("pollbot.pickledb", "wb"),
                4)


# Display ongoing poll/choices and results
@checkEventTime
def info_callback(room, event):
    # Make sure there's an ongoing poll in the room
    poll = None
    for p in ONGOING_POLLS:
        if p.room_id == room.room_id:
            poll = p
            break
    if poll is None:
        room.send_notice(
            "There are no currently ongoing polls! \
            Start a new one with !newpoll"
        )
        return

    response_str = ""

    # Add the question
    response_str += poll.question + "\n"
    response_str += "-" * len(poll.question) + "\n"

    # Add each choice along with its votes
    for i in range(0, len(poll.choices), 1):
        # Add this choice along with the number of votes it recieved
        num_votes = len([x for x in poll.votes if x.choice_idx == i])
        response_str += "%d. %s: %d votes\n" % \
                        (i+1, poll.choices[i], num_votes)

    # Add the ending message
    response_str += "To vote, do !vote <number>\n"
    response_str += "To end the poll, run !endpoll"

    room.send_notice(response_str)


# End a poll and move it from ONGOING_POLLS to ENDED_POLLS
@checkEventTime
def endpoll_callback(room, event):
    # Make sure there's an ongoing poll in the room
    poll = None
    for p in ONGOING_POLLS:
        if p.room_id == room.room_id:
            poll = p
            break
    if poll is None:
        room.send_notice(
            "There are no currently ongoing polls! \
            Start a new one with !newpoll"
        )
        return

    # Make sure the sender is the creator of the poll
    if poll.creator != event['sender']:
        room.send_notice("You can only end polls that you have created!")
        return

    # Remove the poll from ONGOING_POLLS and add to ENDED_POLLS
    ONGOING_POLLS.remove(poll)

    # Remove all ended polls that belong to this room
    global ENDED_POLLS
    ENDED_POLLS = [x for x in ENDED_POLLS if x.room_id != room.room_id]
    ENDED_POLLS.append(poll)

    room.send_notice("Poll ended! See results with !results")
    results_callback(room, event)

    # Update database on disk
    pickle.dump([ONGOING_POLLS, ONGOING_POLLCREATIONS, ENDED_POLLS],
                open("pollbot.pickledb", "wb"),
                4)


# Display the results for an ended poll
@checkEventTime
def results_callback(room, event):
    # Make sure this room has an ended poll
    poll = None
    for p in ENDED_POLLS:
        if p.room_id == room.room_id:
            poll = p
            break
    if poll is None:
        room.send_notice("There are no previous polls to view!")
        return

    response_str = ""

    # Add the question
    response_str += poll.question + "\n"
    response_str += "-" * len(poll.question) + "\n"

    # Add each choice along with its votes
    for i in range(0, len(poll.choices), 1):
        # Add this choice along with the number of votes it recieved
        num_votes = len([x for x in poll.votes if x.choice_idx == i])
        response_str += "%d. %s: %d votes\n" %\
                        (i+1, poll.choices[i], num_votes)

    # Add the ending message
    response_str += "To start a new poll, run !newpoll\n"
    room.send_notice(response_str)

    
# Vote for an ongoing poll
@checkEventTime
def vote_callback(room, event):
    # Make sure that this room has an ongoing poll
    poll = None
    for p in ONGOING_POLLS:
        if p.room_id == room.room_id:
            poll = p
            break
    if poll is None:
        room.send_notice(
            "There are no currently ongoing polls!\
            Start a new one with !newpoll"
        )
        return

    # Verify arguments
    args = event['content']['body'].split(' ')
    if len(args) != 2:
        room.send_notice("Usage: !vote <number>")
        return

    # If this user has already voted, remove their previous vote
    poll.votes = [x for x in poll.votes if x.user_id != event['sender']]

    # Get the index of their choice
    try:
        choice_idx = int(args[1]) - 1
    except ValueError:
        room.send_notice("Usage: !vote <number>")
        return

    # Verify that the given number corresponds to a choice
    if choice_idx < 0 or choice_idx >= len(poll.choices):
        room.send_notice(
            "Please pick a valid choice! \
            Run !info to repeat the poll"
        )
        return

    # Add this vote
    poll.votes.append(Vote(event['sender'], choice_idx))

    # Get this user's short name (not including server)
    short_name = event['sender'][:event['sender'].index(':')]

    # Get the choice they voted for
    choice = poll.choices[choice_idx]

    room.send_notice("%s has voted for '%s'!\n!info - Show current results" %
                     (short_name, choice))

    # Update database on disk
    pickle.dump([ONGOING_POLLS, ONGOING_POLLCREATIONS, ENDED_POLLS],
                open("pollbot.pickledb", "wb"),
                4)

def leave_callback(room,event):
    global bot
    room.send_notice("Bye bye all. In Love your pollbot")
    bot.client.api.leave_room(room.room_id)

# Print help
@checkEventTime
def pollhelp_callback(room, event):
    help_str = "!newpoll       - Create a new poll\n"
    help_str += "!startpoll    - Start a poll\n"
    help_str += "!info         - View an ongoing poll\n"
    help_str += "!vote         - Vote in an ongoing poll\n"
    help_str += "!endpoll      - End an ongoing poll\n"
    help_str += "!results      - View the results of the last ended poll\n"
    help_str += "!add <choice> - To add the choice to the current poll\n"
    help_str += "!leave        - Pollbot leaves the room"
    room.send_notice(help_str)


def main():
    global bot
    # Load configuration
    config = configparser.ConfigParser()
    config.read("config.ini")
    username = config.get("Matrix", "Username")
    password = config.get("Matrix", "Password")
    server = config.get("Matrix", "Homeserver")

    # Start bot
    bot = MatrixBotAPI(username, password, server)

    m_newpoll_handler = MCommandHandler('newpoll', newpoll_callback)
    bot.add_handler(m_newpoll_handler)

    m_ongoing_poll_handler = AllMessageHandler(ongoing_poll_callback)
    bot.add_handler(m_ongoing_poll_handler)

    m_startpoll_handler = MCommandHandler('startpoll', startpoll_callback)
    bot.add_handler(m_startpoll_handler)

    m_add_response_handler = MCommandHandler('add', add_response_to_poll)
    bot.add_handler(m_add_response_handler)

    m_info_handler = MCommandHandler('info', info_callback)
    bot.add_handler(m_info_handler)

    m_endpoll_handler = MCommandHandler('endpoll', endpoll_callback)
    bot.add_handler(m_endpoll_handler)

    m_results_handler = MCommandHandler('results', results_callback)
    bot.add_handler(m_results_handler)

    m_vote_handler = MCommandHandler('vote', vote_callback)
    bot.add_handler(m_vote_handler)

    m_pollhelp_handler = MCommandHandler('pollhelp', pollhelp_callback)
    bot.add_handler(m_pollhelp_handler)

    m_leave_handler = MCommandHandler('leave', leave_callback)
    bot.add_handler(m_leave_handler)

    bot.start_polling()
    print("Pollbot started!")

    while True:
        try:
            input()
        except EOFError:
            print("EOF access")


if __name__ == "__main__":
    main()
