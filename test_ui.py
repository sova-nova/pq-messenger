# Try this in a test file first

from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings


# Message display area (read only)
message_area = TextArea(
    text="Welcome to PQ-Messenger\n",
    read_only=True,
    scrollbar=True,
)

# Input area
input_area = TextArea(
    height=3,
    prompt=">>> ",
    multiline=False,
)

# Stack them vertically
layout = Layout(
    HSplit([
        Frame(message_area, title="Messages"),
        Frame(input_area, title="Input"),
    ])
)

# Key bindings
kb = KeyBindings()

@kb.add("enter")
def on_enter(event):
    # Get what the user typed
    text = input_area.text
    
    # Add it to the message display
    message_area.text += f"You: {text}\n"
    
    # Clear the input
    input_area.text = ""

@kb.add("c-c")
def on_exit(event):
    event.app.exit()

# Create and run the app
app = Application(
    layout=layout,
    key_bindings=kb,
    full_screen=True,
)

app.run()