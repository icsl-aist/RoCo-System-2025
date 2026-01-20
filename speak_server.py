from flask import Flask
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('speak')
def speak_event(eventData):
    if isinstance(eventData, dict):
        sender = eventData.get('sender')
        msg = eventData.get('msg')
        data = {'sender': sender, 'msg': msg}
        
        socketio.emit('log_msg', data)
        
        emit('speak_response', {'status': 'received', 'data': data}, broadcast=False)
        
        # print(data)
    else:
        emit('speak_response', {'status': 'error', 'message': 'Invalid data format'}, broadcast=False)

if __name__ == '__main__':
    socketio.run(app, host='localhost', port=5001)
