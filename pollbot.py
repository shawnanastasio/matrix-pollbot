from matrix_bot_api.matrix_bot_api import MatrixBotAPI
from matrix_bot_api.mhandler import MHandler
from matrix_bot_api.mregex_handler import MRegexHandler
from matrix_bot_api.mcommand_handler import MCommandHandler

import configparser

# Bot's Matrix credentials
M_USERNAME = ""
M_PASSWORD = ""
M_SERVER = ""

# List of ongoing polls. One per room
ONGOING_POLLS = []

# List of incomplete poll objects that are being created
ONGOING_POLLCREATIONS = []

# List of ended polls. Only stores one per room
ENDED_POLLS = []

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


def newpoll_callback(room, event):
    # Make sure we don't have an ongoing poll for this room
    for poll in ONGOING_POLLS:
        if poll.room_id == room.room_id:
            room.send_text("There's already an ongoing poll in this room! Please end it before starting a new one.")
            return

    # Make sure we don't have an ongoing poll creation for this room
    for poll in ONGOING_POLLCREATIONS:
        if poll.room_id == room_id:
            room.send_text("There's already an ongoing poll in this room! Please end it before starting a new one.")
            return


    # Create an incomplete Poll object and add it to ONGOING_POLLCREATIONS
    new_poll = Poll(room.room_id, event['sender'], None, None)
    ONGOING_POLLCREATIONS.append(new_poll)

    # Prompt the user for a question
    room.send_text("Creating a new poll. Please send the question.")

    # When they respond, it will be handled by the ongoing handler

# Handles ongoing poll creations
def ongoing_poll_callback(room, event):
    # Make sure this room has an ongoing poll creation and it was created by the message sender
    if event['content']['body'][0] == '!':
        return

    poll =  None
    for p in ONGOING_POLLCREATIONS:
        if p.room_id == room.room_id and p.creator == event['sender']:
            poll = p
            break
    if poll is None:
        return

    # See which part to handle
    if poll.question is None:
        poll.question = event['content']['body']
        room.send_text("Okay, now send me the choices one by one. Type !startpoll to start the poll.")
    else:
        # Handle message as a choice
        if poll.choices is None:
            poll.choices = []

        poll.choices.append(event['content']['body'])
        room.send_text("Response added. Send another choice or type !startpoll to start the poll")


# Starts a poll (moves from an ongoing poll creation to an ongoing poll)
def startpoll_callback(room, event):
    # Make sure there's an ongoing poll creation and it was created by the message sender
    poll =  None
    for p in ONGOING_POLLCREATIONS:
        if p.room_id == room.room_id and p.creator == event['sender']:
            poll = p
            break
    if poll is None:
        room.send_text("There are no polls you can start!")
        return

    # Confirm that the poll is ready and move it from ONGOING_POLLCREATIONS to ONGOING_POLLS
    if poll.question is None:
        room.send_text("You need to send a question first!")
        return

    if poll.choices is None or len(poll.choices) < 2:
        room.send_text("You need to send at least two choices first!")
        return

    # Remove the poll from ONGOING_POLLCREATIONS and add to ONGOING_POLLS
    ONGOING_POLLCREATIONS.remove(poll)
    ONGOING_POLLS.append(poll)

    room.send_text("Poll started! Repeat the question with !info")
    info_callback(room, event)

# Display ongoing poll/choices and results
def info_callback(room, event):
    # Make sure there's an ongoing poll in the room
    poll = None
    for p in ONGOING_POLLS:
        if p.room_id == room.room_id:
            poll = p
            break
    if poll is None:
        room.send_text("There are no currently ongoing polls! Start a new one with !newpoll")
        return

    response_str = ""

    # Add the question
    response_str += poll.question + "\n"
    response_str += "-" * len(poll.question) + "\n"

    # Add each choice along with its votes
    for i in range(0, len(poll.choices), 1):
        # Add this choice along with the number of votes it recieved
        num_votes = len([x for x in poll.votes if x.choice_idx == i])
        response_str += "%d. %s: %d votes\n" % (i+1, poll.choices[i], num_votes)

    # Add the ending message
    response_str += "To vote, do !vote <number>\n"
    response_str += "To end the poll, run !endpoll"

    room.send_text(response_str)

# End a poll and move it from ONGOING_POLLS to ENDED_POLLS
def endpoll_callback(room, event):
    # Make sure there's an ongoing poll in the room
    poll = None
    for p in ONGOING_POLLS:
        if p.room_id == room.room_id:
            poll = p
            break
    if poll is None:
        room.send_text("There are no currently ongoing polls! Start a new one with !newpoll")
        return

    # Make sure the sender is the creator of the poll
    if poll.creator != event['sender']:
        room.send_text("You can only end polls that you have created!")
        return

    # Remove the poll from ONGOING_POLLS and add to ENDED_POLLS
    ONGOING_POLLS.remove(poll)

    # Remove all ended polls that belong to this room
    global ENDED_POLLS
    ENDED_POLLS = [x for x in ENDED_POLLS if x.room_id != room.room_id]
    ENDED_POLLS.append(poll)

    room.send_text("Poll ended! See results with !results")
    results_callback(room, event)

# Display the results for an ended poll
def results_callback(room, event):
    # Make sure this room has an ended poll
    poll = None
    for p in ENDED_POLLS:
        if p.room_id == room.room_id:
            poll = p
            break
    if poll is None:
        room.send_text("There are no previous polls to view!")
        return

    response_str = ""

    # Add the question
    response_str += poll.question + "\n"
    response_str += "-" * len(poll.question) + "\n"

    # Add each choice along with its votes
    for i in range(0, len(poll.choices), 1):
        # Add this choice along with the number of votes it recieved
        num_votes = len([x for x in poll.votes if x.choice_idx == i])
        response_str += "%d. %s: %d votes\n" % (i+1, poll.choices[i], num_votes)

    # Add the ending message
    response_str += "To start a new poll, run !newpoll\n"
    room.send_text(response_str)

# Vote for an ongoing poll
def vote_callback(room, event):
    # Make sure that this room has an ongoing poll
    poll = None
    for p in ONGOING_POLLS:
        if p.room_id == room.room_id:
            poll = p
            break
    if poll is None:
        room.send_text("There are no currently ongoing polls! Start a new one with !newpoll")
        return

    # Verify arguments
    args = event['content']['body'].split(' ')
    if len(args) != 2:
        room.send_text("Usage: !vote <number>")
        return


    # If this user has already voted, remove their previous vote
    poll.votes = [x for x in poll.votes if x.user_id != event['sender']]

    # Get the index of their choice
    choice_idx = 0
    try:
        choice_idx = int(args[1]) - 1
    except:
        room.send_text("Usage: !vote <number>")
        return

    # Verify that the given number corresponds to a choice
    if choice_idx < 0 or choice_idx >= len(poll.choices):
        room.send_text("Please pick a valid choice! Run !info to repeat the poll")
        return

    # Add this vote
    poll.votes.append(Vote(event['sender'], choice_idx))

    # Get this user's short name (not including server)
    short_name = event['sender'][:event['sender'].index(':')]

    # Get the choice they voted for
    choice = poll.choices[choice_idx]

    room.send_text("%s has voted for '%s'!\n!info - Show current results" % (short_name, choice))


# Print help
def pollhelp_callback(room, event):
    help_str =  "!newpoll   - Create a new poll\n"
    help_str += "!startpoll - Start a poll\n"
    help_str += "!info      - View an ongoing poll\n"
    help_str += "!vote      - Vote in an ongoing poll\n"
    help_str += "!endpoll   - End an ongoing poll\n"
    help_str += "!results   - View the results of the last ended poll"
    room.send_text(help_str)


def main():
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


    bot.start_polling()
    print("Pollbot started!")

    while True:
        input()




if __name__ == "__main__":
    main()
