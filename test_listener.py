from listener import Listener
import time

listener = Listener(record_timeout=5)

input("Press ENTER, then speak clearly... ")

listener.listen()

while listener.is_listening():
    time.sleep(0.1)

print("RESULT:", listener.recognize())
